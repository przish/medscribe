import pytest
from medscribe.schemas import (
    Transcript,
    TranscriptSegment,
    SpeakerRole,
    SOAPClaim,
    SOAPNoteDraft,
    SubjectiveSection,
    VerificationStatus,
    AuditFlagType,
    AuditFlagSeverity,
)
from medscribe.validator import EvidenceValidator


@pytest.fixture
def sample_transcript():
    return Transcript(
        encounter_id="ENC-TEST-001",
        patient_synthetic_id="SYN-PAT-TEST",
        encounter_date="2026-10-09",
        segments=[
            TranscriptSegment(segment_id="seg-001", speaker=SpeakerRole.CLINICIAN, text="Do you have any chest pain?"),
            TranscriptSegment(segment_id="seg-002", speaker=SpeakerRole.PATIENT, text="No, I deny any chest pain or tightness."),
            TranscriptSegment(segment_id="seg-003", speaker=SpeakerRole.PATIENT, text="I take half or one tablet of something white for cholesterol."),
        ],
    )


def test_validator_supported_claim(sample_transcript):
    validator = EvidenceValidator(sample_transcript)
    claim = SOAPClaim(
        claim_id="CLM-1",
        category="Subjective",
        field="hpi",
        statement="Patient denies chest pain or tightness.",
        source_segment_ids=["seg-002"],
        source_exact_quote="deny any chest pain or tightness",
    )
    validated = validator.validate_claim(claim)
    assert validated.verification_status == VerificationStatus.SUPPORTED
    assert len(validated.audit_flags) == 0


def test_validator_invalid_segment_id(sample_transcript):
    validator = EvidenceValidator(sample_transcript)
    claim = SOAPClaim(
        claim_id="CLM-2",
        category="Subjective",
        field="hpi",
        statement="Reports shortness of breath.",
        source_segment_ids=["seg-999"],  # Non-existent ID
        source_exact_quote="shortness of breath",
    )
    validated = validator.validate_claim(claim)
    assert validated.verification_status == VerificationStatus.UNSUPPORTED
    assert any(f.flag_type == AuditFlagType.INVALID_SEGMENT_ID for f in validated.audit_flags)


def test_validator_unsupported_claim_no_id(sample_transcript):
    validator = EvidenceValidator(sample_transcript)
    claim = SOAPClaim(
        claim_id="CLM-3",
        category="Subjective",
        field="hpi",
        statement="Takes Metformin 500mg BID.",
        source_segment_ids=[],  # No citation
    )
    validated = validator.validate_claim(claim)
    assert validated.verification_status == VerificationStatus.UNSUPPORTED
    assert any(f.flag_type == AuditFlagType.UNSUPPORTED_CLAIM for f in validated.audit_flags)


def test_validator_negation_flip_detection(sample_transcript):
    validator = EvidenceValidator(sample_transcript)
    # Transcript has "No, I deny any chest pain or tightness"
    # Note hallucinated that chest pain was present without negation marker:
    claim = SOAPClaim(
        claim_id="CLM-4",
        category="Subjective",
        field="hpi",
        statement="Patient reports persistent acute chest pain.",
        source_segment_ids=["seg-002"],
        source_exact_quote="chest pain",
    )
    validated = validator.validate_claim(claim)
    assert validated.verification_status == VerificationStatus.UNSUPPORTED
    assert any(f.flag_type == AuditFlagType.ALTERED_NEGATION for f in validated.audit_flags)


def test_validator_medication_ambiguity(sample_transcript):
    validator = EvidenceValidator(sample_transcript)
    claim = SOAPClaim(
        claim_id="CLM-5",
        category="Subjective",
        field="current_medications",
        statement="Takes half or one tablet of something white for cholesterol, unknown name.",
        source_segment_ids=["seg-003"],
        source_exact_quote="half or one tablet of something white for cholesterol",
    )
    validated = validator.validate_claim(claim)
    # Should trigger medication ambiguity warning
    assert any(f.flag_type == AuditFlagType.MEDICATION_AMBIGUITY for f in validated.audit_flags)


def test_validator_unclear_audio_omission():
    transcript = Transcript(
        encounter_id="ENC-AUDIO-01",
        patient_synthetic_id="SYN-PAT-01",
        encounter_date="2026-10-10",
        segments=[
            TranscriptSegment(
                segment_id="seg-001",
                speaker=SpeakerRole.PATIENT,
                start_time="01:14",
                text="Umiinom po ako ng... [inaudible dosage] ...bago matulog.",
                is_low_confidence=True,
                avg_logprob=-1.20,
            )
        ],
    )
    validator = EvidenceValidator(transcript)
    claim = SOAPClaim(
        claim_id="CLM-MED-01",
        category="Subjective",
        field="current_medications",
        statement="Takes medication at bedtime.",
        source_segment_ids=["seg-001"],
        source_exact_quote="bago matulog",
    )
    # 1. Unclarified low-confidence audio triggers UNCLEAR_AUDIO_OMISSION warning
    validated = validator.validate_claim(claim)
    assert any(f.flag_type == AuditFlagType.UNCLEAR_AUDIO_OMISSION for f in validated.audit_flags)
    assert validated.verification_status == VerificationStatus.AMBIGUOUS

    # 2. When clinician provides clarification, the flag resolves
    transcript.segments[0].clinician_clarification = "Atorvastatin 20mg once daily at bedtime"
    validator_clarified = EvidenceValidator(transcript)
    validated_cleared = validator_clarified.validate_claim(claim)
    assert not any(f.flag_type == AuditFlagType.UNCLEAR_AUDIO_OMISSION for f in validated_cleared.audit_flags)


def test_validator_acoustic_omission_note_level():
    transcript = Transcript(
        encounter_id="ENC-AUDIO-02",
        patient_synthetic_id="SYN-PAT-02",
        encounter_date="2026-10-10",
        segments=[
            TranscriptSegment(
                segment_id="seg-001",
                speaker=SpeakerRole.PATIENT,
                start_time="00:45",
                text="[unclear audio murmur]",
                is_low_confidence=True,
            )
        ],
    )
    validator = EvidenceValidator(transcript)
    draft = SOAPNoteDraft(encounter_id="ENC-AUDIO-02", patient_synthetic_id="SYN-PAT-02")
    audited = validator.validate_note(draft)
    assert any("Acoustic Omission: Unclear Audio" in mf for mf in audited.audit_summary.missing_fields)

    # Adding clarification resolves acoustic omission from missing fields
    transcript.segments[0].clinician_clarification = "Patient stated mild dizziness when standing quickly."
    audited_resolved = validator.validate_note(draft)
    assert not any("Acoustic Omission: Unclear Audio" in mf for mf in audited_resolved.audit_summary.missing_fields)

