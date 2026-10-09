import pytest
from medscribe.audio import get_whisper_model, transcribe_audio_bytes

def test_whisper_model_singleton():
    m1 = get_whisper_model("tiny")
    m2 = get_whisper_model("tiny")
    assert m1 is m2
    assert m1 is not None

def test_transcribe_audio_empty_bytes():
    # Empty or silent audio should safely return fallback dialogue without crashing
    text = transcribe_audio_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    assert "Clinician" in text

def test_transcribe_sample_wav_file():
    import os
    sample_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_consultation.wav")
    if os.path.exists(sample_path):
        with open(sample_path, "rb") as f:
            data = f.read()
        res = transcribe_audio_bytes(data)
        assert len(res) > 0
        assert "blood pressure" in res.lower() or "headache" in res.lower()

