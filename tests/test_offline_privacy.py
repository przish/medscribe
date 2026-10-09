import socket
import pytest
from medscribe.pipeline import MedscribePipeline
from medscribe.adapters.mock_adapter import MockModelAdapter
from medscribe.adapters.ollama_adapter import OllamaModelAdapter


def test_core_pipeline_pure_offline(monkeypatch):
    """
    Ensure the core pipeline makes zero network socket calls during execution.
    """
    def guarded_connect(*args, **kwargs):
        raise AssertionError("Network socket connection attempted during offline execution!")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="standard"))
    transcript = pipeline.parse_raw_text_to_transcript(
        "Clinician: How is your knee pain?\nPatient: It is much better with ice.",
        encounter_id="ENC-OFFLINE-001",
        patient_id="SYN-PAT-OFFLINE",
    )

    draft = pipeline.process_encounter(transcript)
    assert draft.encounter_id == "ENC-OFFLINE-001"
    assert len(draft.subjective.chief_complaint) > 0


def test_ollama_adapter_offline_graceful_handling():
    """
    Ollama adapter should gracefully handle unreachable local daemon without unhandled crash.
    """
    adapter = OllamaModelAdapter(host="http://127.0.0.1:9999")  # Unused port
    assert adapter.is_available() is False
    assert adapter.get_installed_models() == []
