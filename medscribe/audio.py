import os
import tempfile
from typing import Optional
from faster_whisper import WhisperModel

_MODEL_INSTANCE: Optional[WhisperModel] = None

def get_whisper_model(model_size: str = "tiny") -> WhisperModel:
    """Load or return the singleton local Whisper model on CPU with offline priority."""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        try:
            # First attempt: strictly offline from local cache
            _MODEL_INSTANCE = WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=True)
        except Exception:
            # Fallback if first run and model not yet cached locally
            _MODEL_INSTANCE = WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=False)
    return _MODEL_INSTANCE

def transcribe_audio_bytes(audio_bytes: bytes, language: Optional[str] = None) -> str:
    """
    Transcribes raw audio bytes (from st.audio_input or st.file_uploader)
    using on-device local Whisper.
    Supports English, Tagalog (tl), Taglish, and auto-language detection.
    Returns structured consultation transcript text with timestamps and speaker tags.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        model = get_whisper_model()
        lang_param = None if (not language or language in ("auto", "Auto-Detect")) else language
        segments, _ = model.transcribe(tmp_path, beam_size=1, language=lang_param)

        dialogue_lines = []
        # Clinician / Patient speaker alternation heuristic for clinical dialogue turns
        roles = ["Clinician", "Patient"]
        for i, segment in enumerate(segments):
            m_start = int(segment.start // 60)
            s_start = int(segment.start % 60)
            timestamp = f"{m_start:02d}:{s_start:02d}"
            role = roles[i % len(roles)]
            text = segment.text.strip()
            if text:
                dialogue_lines.append(f"{role} [{timestamp}]: {text}")

        # Fallback if audio was empty or silent
        if not dialogue_lines:
            return "Clinician [00:00]: Consultation recorded with no audible speech detected."

        return "\n".join(dialogue_lines)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
