import pytest
from medscribe.schemas import (
    Transcript,
    TranscriptSegment,
    SpeakerRole,
    SOAPClaim,
    SOAPNoteDraft,
    VerificationStatus,
)


def test_transcript_schema():
    seg1 = TranscriptSegment(segment_id="seg-001", speaker=SpeakerRole.CLINICIAN, text="Hello")
    seg2 = TranscriptSegment(segment_id="seg-002", speaker=SpeakerRole.PATIENT, text="Hi doctor")
    t = Transcript(
        encounter_id="ENC-001",
        patient_synthetic_id="PAT-001",
        encounter_date="2026-10-09",
        segments=[seg1, seg2],
    )

    assert len(t.segments) == 2
    seg_map = t.get_segment_map()
    assert "seg-001" in seg_map
    assert seg_map["seg-002"].speaker == SpeakerRole.PATIENT


def test_soap_draft_defaults():
    draft = SOAPNoteDraft(
        encounter_id="ENC-001",
        patient_synthetic_id="PAT-001",
    )
    assert draft.is_draft is True
    assert draft.clinician_review_confirmed is False
    assert "DRAFT" in draft.disclaimer
    assert len(draft.all_claims()) == 0
