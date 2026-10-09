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
