from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SpeakerRole(str, Enum):
    CLINICIAN = "Clinician"
    PATIENT = "Patient"
    CAREGIVER = "Caregiver"


class AuditFlagSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditFlagType(str, Enum):
    UNSUPPORTED_CLAIM = "unsupported_claim"             # No valid segment ID or citation hallucinated
    INVALID_SEGMENT_ID = "invalid_segment_id"           # Referenced segment ID does not exist in transcript
    QUOTE_MISMATCH = "quote_mismatch"                   # Claim quote not found in referenced segment text
    ALTERED_NEGATION = "altered_negation"               # Transcript denies symptom, note asserts it (or vice-versa)
    MISSING_CRITICAL_INFO = "missing_critical_info"     # Omitted vital signs, allergy check, or dosage
    ASSUMED_NEGATIVE = "assumed_negative"               # Model assumed negative/normal when not mentioned
    MEDICATION_AMBIGUITY = "medication_ambiguity"       # Missing dosage/route/frequency or family med conflation
    UNCERTAINTY_UPGRADED = "uncertainty_upgraded"       # "Possible/rule out" converted to definitive diagnosis
    TRANSCRIPT_CONTRADICTION = "contradiction"          # Patient gave conflicting statements in transcript


class TranscriptSegment(BaseModel):
    segment_id: str = Field(..., description="Unique deterministic identifier, e.g. seg-001")
    speaker: SpeakerRole
    start_time: Optional[str] = Field(None, description="HH:MM:SS or MM:SS format")
    end_time: Optional[str] = Field(None, description="HH:MM:SS or MM:SS format")
    text: str = Field(..., description="Transcript turn text verbatim")


class Transcript(BaseModel):
    encounter_id: str
    patient_synthetic_id: str
    encounter_date: str
    segments: List[TranscriptSegment]

    def get_segment_map(self) -> Dict[str, TranscriptSegment]:
        return {seg.segment_id: seg for seg in self.segments}

    def full_text(self) -> str:
        return "\n".join(f"[{seg.segment_id}] {seg.speaker.value}: {seg.text}" for seg in self.segments)


class VerificationStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    AMBIGUOUS = "ambiguous"


class AuditFlag(BaseModel):
    flag_type: AuditFlagType
    severity: AuditFlagSeverity
    message: str
    suggested_action: str


class SOAPClaim(BaseModel):
    claim_id: str = Field(..., description="Unique claim identifier, e.g. CLM-S-01")
    category: str = Field(..., description="Subjective, Objective, Assessment, or Plan")
    field: str = Field(..., description="e.g. chief_complaint, hpi, current_medications, allergies, vitals, physical_exam, assessment, plan")
    statement: str = Field(..., description="The clinical claim statement")
    verification_status: VerificationStatus = VerificationStatus.UNSUPPORTED
    source_segment_ids: List[str] = Field(default_factory=list, description="IDs of supporting transcript turns")
    source_exact_quote: Optional[str] = Field(None, description="Exact substring from transcript")
    audit_flags: List[AuditFlag] = Field(default_factory=list)
    clinician_reviewed: bool = False
    clinician_edited_statement: Optional[str] = None


class SubjectiveSection(BaseModel):
    chief_complaint: List[SOAPClaim] = Field(default_factory=list)
    history_of_present_illness: List[SOAPClaim] = Field(default_factory=list)
    current_medications: List[SOAPClaim] = Field(default_factory=list)
    allergies: List[SOAPClaim] = Field(default_factory=list)


class ObjectiveSection(BaseModel):
    vital_signs: List[SOAPClaim] = Field(default_factory=list)
    physical_exam: List[SOAPClaim] = Field(default_factory=list)
    diagnostic_tests: List[SOAPClaim] = Field(default_factory=list)


class AssessmentSection(BaseModel):
    clinical_impressions: List[SOAPClaim] = Field(default_factory=list)


class PlanSection(BaseModel):
    medications_advised: List[SOAPClaim] = Field(default_factory=list)
    non_pharmacologic_care: List[SOAPClaim] = Field(default_factory=list)
    follow_up_and_red_flags: List[SOAPClaim] = Field(default_factory=list)


class AuditSummary(BaseModel):
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    critical_flags_count: int = 0
    warning_flags_count: int = 0
    missing_fields: List[str] = Field(default_factory=list)


class SOAPNoteDraft(BaseModel):
    encounter_id: str
    patient_synthetic_id: str
    is_draft: bool = True
    clinician_review_confirmed: bool = False
    disclaimer: str = (
        "DRAFT CLINICAL DOCUMENTATION AID — NOT A MEDICAL DIAGNOSIS OR PRESCRIPTION. "
        "Strictly requires licensed clinician verification before clinical or legal reliance."
    )
    subjective: SubjectiveSection = Field(default_factory=SubjectiveSection)
    objective: ObjectiveSection = Field(default_factory=ObjectiveSection)
    assessment: AssessmentSection = Field(default_factory=AssessmentSection)
    plan: PlanSection = Field(default_factory=PlanSection)
    audit_summary: AuditSummary = Field(default_factory=AuditSummary)

    def all_claims(self) -> List[SOAPClaim]:
        claims = []
        for section in [self.subjective, self.objective, self.assessment, self.plan]:
            for field_name in type(section).model_fields.keys():
                claims.extend(getattr(section, field_name))
        return claims
