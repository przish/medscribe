import re
from typing import List, Dict, Set
from medscribe.schemas import (
    Transcript,
    SOAPNoteDraft,
    SOAPClaim,
    VerificationStatus,
    AuditFlag,
    AuditFlagType,
    AuditFlagSeverity,
    AuditSummary,
)

# Negation and qualification tokens
NEGATION_PATTERNS = [
    r"\bno\b",
    r"\bnot\b",
    r"\bdenies\b",
    r"\bdenied\b",
    r"\bwithout\b",
    r"\bnever\b",
    r"\bnone\b",
    r"\bnegative\b",
]

HEDGES_UNCERTAINTY = [
    r"\bpossible\b",
    r"\bprobable\b",
    r"\bsuspected\b",
    r"\brule\s+out\b",
    r"\bborderline\b",
    r"\bmild\b",
    r"\bpotential\b",
    r"\bquestionable\b",
]


class EvidenceValidator:
    """
    Deterministic validator enforcing:
    1. Segment existence: All referenced IDs must be present in the transcript.
    2. Quote verification: Source quotes must be verifiable verbatim substrings of the segment.
    3. Negation preservation: Claims cannot reverse transcript negation.
    4. Missingness & Non-fabrication: Unassessed fields must not assume negative/normal defaults.
    5. Medication ambiguity & safety checks.
    """

    def __init__(self, transcript: Transcript):
        self.transcript = transcript
        self.segment_map = transcript.get_segment_map()
        self.full_transcript_lower = " ".join(seg.text.lower() for seg in transcript.segments)

    def validate_claim(self, claim: SOAPClaim) -> SOAPClaim:
        flags: List[AuditFlag] = []

        # 1. Segment Existence Check
        if not claim.source_segment_ids:
            flags.append(
                AuditFlag(
                    flag_type=AuditFlagType.UNSUPPORTED_CLAIM,
                    severity=AuditFlagSeverity.CRITICAL,
                    message=f"Claim '{claim.claim_id}' cites no source transcript turns.",
                    suggested_action="Review transcript or remove unsupported claim.",
                )
            )
            claim.verification_status = VerificationStatus.UNSUPPORTED
        else:
            invalid_ids = [sid for sid in claim.source_segment_ids if sid not in self.segment_map]
            if invalid_ids:
                flags.append(
                    AuditFlag(
                        flag_type=AuditFlagType.INVALID_SEGMENT_ID,
                        severity=AuditFlagSeverity.CRITICAL,
                        message=f"Referenced segment ID(s) {invalid_ids} do not exist in transcript.",
                        suggested_action="Correct reference to an existing segment ID.",
                    )
                )
                claim.verification_status = VerificationStatus.UNSUPPORTED

        # 2. Quote Fidelity Check
        valid_segments = [self.segment_map[sid] for sid in claim.source_segment_ids if sid in self.segment_map]
        if valid_segments and claim.source_exact_quote:
            quote_clean = " ".join(claim.source_exact_quote.strip().lower().split())
            combined_segment_text = " ".join(" ".join(seg.text.lower().split()) for seg in valid_segments)
            if quote_clean not in combined_segment_text:
                flags.append(
                    AuditFlag(
                        flag_type=AuditFlagType.QUOTE_MISMATCH,
                        severity=AuditFlagSeverity.WARNING,
                        message=f"Cited quote is not an exact substring of referenced turns: '{claim.source_exact_quote}'",
                        suggested_action="Verify verbatim quote against speaker turns.",
                    )
                )

        # 3. Negation Check: Detect if transcript denies a symptom but note claims positive (or vice versa)
        if valid_segments and claim.field in ("hpi", "chief_complaint", "physical_exam"):
            turn_text = " ".join(seg.text.lower() for seg in valid_segments)
            claim_text = claim.statement.lower()

            source_has_neg = any(re.search(pat, turn_text) for pat in NEGATION_PATTERNS)
            claim_has_neg = any(re.search(pat, claim_text) for pat in NEGATION_PATTERNS) or any(term in claim_text for term in ["denies", "denied", "no", "absent", "without", "none", "discontinued", "stopped"])

            if source_has_neg and not claim_has_neg:
                flags.append(
                    AuditFlag(
                        flag_type=AuditFlagType.ALTERED_NEGATION,
                        severity=AuditFlagSeverity.CRITICAL,
                        message=f"Potential negation flip: source turn contains denial/negative finding, but claim statement appears affirmative: '{claim.statement}'",
                        suggested_action="Confirm whether symptom was denied or confirmed by patient.",
                    )
                )

        # 4. Medication Ambiguity Check
        if claim.field == "current_medications" or claim.field == "medications_advised":
            stmt_lower = claim.statement.lower()
            if any(term in stmt_lower for term in ["half or", "unknown", "forgot", "something white", "pillbox"]):
                flags.append(
                    AuditFlag(
                        flag_type=AuditFlagType.MEDICATION_AMBIGUITY,
                        severity=AuditFlagSeverity.WARNING,
                        message=f"Medication statement has ambiguous dosage, frequency, or name: '{claim.statement}'",
                        suggested_action="Clarify medication brand, dose, and regimen with patient or pill bottle.",
                    )
                )

        # 5. Uncertainty Upgrading Check
        if claim.category == "Assessment":
            claim_lower = claim.statement.lower()
            combined_source = " ".join(seg.text.lower() for seg in valid_segments)
            source_has_hedge = any(re.search(h, combined_source) for h in HEDGES_UNCERTAINTY)
            claim_has_hedge = any(re.search(h, claim_lower) for h in HEDGES_UNCERTAINTY)
            if source_has_hedge and not claim_has_hedge:
                flags.append(
                    AuditFlag(
                        flag_type=AuditFlagType.UNCERTAINTY_UPGRADED,
                        severity=AuditFlagSeverity.WARNING,
                        message=f"Clinical impression upgraded tentative/hedged diagnosis to definitive: '{claim.statement}'",
                        suggested_action="Preserve diagnostic qualifier (suspected, possible, borderline).",
                    )
                )

        # Determine Final Status
        claim.audit_flags = flags
        has_critical = any(f.severity == AuditFlagSeverity.CRITICAL for f in flags)
        if not flags:
            claim.verification_status = VerificationStatus.SUPPORTED
        elif has_critical:
            claim.verification_status = VerificationStatus.UNSUPPORTED
        else:
            # Warnings like ambiguity or quote mismatch
            claim.verification_status = VerificationStatus.AMBIGUOUS

        return claim

    def validate_note(self, draft: SOAPNoteDraft) -> SOAPNoteDraft:
        """
        Validates all claims and performs note-level missingness audits.
        """
        all_claims: List[SOAPClaim] = []

        # Validate Subjective
        for field in ["chief_complaint", "history_of_present_illness", "current_medications", "allergies"]:
            claims_list = getattr(draft.subjective, field)
            validated = [self.validate_claim(c) for c in claims_list]
            setattr(draft.subjective, field, validated)
            all_claims.extend(validated)

        # Validate Objective
        for field in ["vital_signs", "physical_exam", "diagnostic_tests"]:
            claims_list = getattr(draft.objective, field)
            validated = [self.validate_claim(c) for c in claims_list]
            setattr(draft.objective, field, validated)
            all_claims.extend(validated)

        # Validate Assessment
        for field in ["clinical_impressions"]:
            claims_list = getattr(draft.assessment, field)
            validated = [self.validate_claim(c) for c in claims_list]
            setattr(draft.assessment, field, validated)
            all_claims.extend(validated)

        # Validate Plan
        for field in ["medications_advised", "non_pharmacologic_care", "follow_up_and_red_flags"]:
            claims_list = getattr(draft.plan, field)
            validated = [self.validate_claim(c) for c in claims_list]
            setattr(draft.plan, field, validated)
            all_claims.extend(validated)

        # Note-level Missingness Audit
        missing_fields: List[str] = []
        if not draft.subjective.chief_complaint:
            missing_fields.append("Subjective: Chief Complaint")
        if not draft.subjective.allergies:
            missing_fields.append("Subjective: Allergies (Not Documented)")
        if not draft.objective.vital_signs:
            missing_fields.append("Objective: Vital Signs (Unassessed / Not Measured)")
        if not draft.objective.physical_exam:
            missing_fields.append("Objective: Physical Examination (Omitted)")
        if not draft.assessment.clinical_impressions:
            missing_fields.append("Assessment: Clinical Impression")
        if not draft.plan.follow_up_and_red_flags:
            missing_fields.append("Plan: Follow-up & Red Flags")

        # Compile Summary
        supported_count = sum(1 for c in all_claims if c.verification_status == VerificationStatus.SUPPORTED)
        unsupported_count = sum(1 for c in all_claims if c.verification_status in (VerificationStatus.UNSUPPORTED, VerificationStatus.CONTRADICTED))
        critical_count = sum(1 for c in all_claims for f in c.audit_flags if f.severity == AuditFlagSeverity.CRITICAL)
        warning_count = sum(1 for c in all_claims for f in c.audit_flags if f.severity == AuditFlagSeverity.WARNING)

        draft.audit_summary = AuditSummary(
            total_claims=len(all_claims),
            supported_claims=supported_count,
            unsupported_claims=unsupported_count,
            critical_flags_count=critical_count,
            warning_flags_count=warning_count,
            missing_fields=missing_fields,
        )

        return draft
