import os
import re
import tempfile
from typing import Dict, Optional
from faster_whisper import WhisperModel

_MODEL_CACHE: Dict[str, WhisperModel] = {}

TAGALOG_CLINICAL_PROMPT = (
    "Magandang araw po doktor. Ito ay medikal na konsultasyon sa wikang Filipino at Tagalog. "
    "Makinig nang mabuti sa sinasabi ng pasyente at doktor. "
    "Mga karaniwang salita: masakit po ang tiyan, sumasakit ang ulo, dibdib, lagnat, ubo, sipon, "
    "hilo, presyon ng dugo, BP, gamot, inumin, reseta, doktor, pasyente, kumusta po."
)

TAGALOG_SPEECH_REPLACEMENTS = [
    (r"\b[Bb]ofapag\b", "po kapag"),
    (r"\b[Bb]ofa\b", "po ba"),
    (r"\b[Bb]ofat\b", "po ba"),
    (r"\b[Ss]umasapit\b", "sumasakit"),
    (r"\b[Pp]ano\b", "Paano"),
    (r"\b([Hh]ello|[Hh]i),\s*do[!.]?\b", r"\1, doc!"),
    (r"\b([Hh]ello|[Hh]i)\s+do[!.]?\b", r"\1 doc!"),
    (r"\bdoc\s*do[!.]?\b", "doc!"),
]

def clean_tagalog_speech_text(text: str) -> str:
    """Normalize common speech-to-text token artifacts on colloquial Filipino dialogue."""
    for pattern, replacement in TAGALOG_SPEECH_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def get_whisper_model(model_size: str = "base") -> WhisperModel:
    """Load or return the singleton local Whisper model on CPU with offline priority."""
    global _MODEL_CACHE
    if model_size not in _MODEL_CACHE:
        try:
            # First attempt: strictly offline from local cache
            _MODEL_CACHE[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=True)
        except Exception:
            # Fallback if first run and model not yet cached locally
            _MODEL_CACHE[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=False)
    return _MODEL_CACHE[model_size]

def transcribe_audio_bytes(
    audio_bytes: bytes,
    language: Optional[str] = None,
    model_size: str = "base",
    initial_prompt: Optional[str] = None,
) -> str:
    """
    Transcribes raw audio bytes (from st.audio_input or st.file_uploader)
    using on-device local Whisper.
    Supports English, Tagalog (tl), Taglish, and auto-language detection with clinical priming.
    Returns structured consultation transcript text with timestamps and speaker tags.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        model = get_whisper_model(model_size=model_size)
        
        # Configure language and domain prompt
        is_tagalog = False
        if not language or language in ("auto", "Auto-Detect"):
            lang_param = None
            prompt = initial_prompt or TAGALOG_CLINICAL_PROMPT
            is_tagalog = True
        elif "tl" in language or "tagalog" in language.lower() or "filipino" in language.lower():
            lang_param = "tl"
            prompt = initial_prompt or TAGALOG_CLINICAL_PROMPT
            is_tagalog = True
        else:
            lang_param = language
            prompt = initial_prompt or "Medical clinical consultation between doctor and patient."

        segments, _ = model.transcribe(
            tmp_path,
            beam_size=5,
            language=lang_param,
            initial_prompt=prompt,
            vad_filter=True,
        )

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
                if is_tagalog:
                    text = clean_tagalog_speech_text(text)
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
