"""Physician-facing wording for internal audit tags.

Internal enum values (e.g. ``uncertainty_upgraded``) must never be shown in the UI.
Templates only restate what the transcript/draft actually contain; they never add
clinical facts.
"""
import re
from typing import Dict, Optional

from medscribe.schemas import AuditFlag, AuditFlagType, SOAPClaim, Transcript

# title, plain-language explanation ({quote}/{statement} filled from the claim), reviewer prompt
FLAG_COPY: Dict[AuditFlagType, Dict[str, str]] = {
    AuditFlagType.UNSUPPORTED_CLAIM: {
        "title": "Not found in transcript",
        "why": "The draft states \u201c{statement}\u201d, but no transcript line supports it.",
        "prompt": "Confirm this from your own examination, edit it, or delete it from the note.",
    },
    AuditFlagType.INVALID_SEGMENT_ID: {
        "title": "Source reference invalid",
        "why": "The draft cites a transcript line that does not exist.",
        "prompt": "Treat this statement as unsourced until you verify it.",
    },
    AuditFlagType.QUOTE_MISMATCH: {
        "title": "Quote does not match transcript",
        "why": "The excerpt attached to this statement does not appear word-for-word in the cited line.",
        "prompt": "Compare against the transcript wording before relying on this statement.",
    },
    AuditFlagType.ALTERED_NEGATION: {
        "title": "Discrepancy detected: denied vs. reported",
        "why": "The transcript says \u201c{quote}\u201d, but the draft says \u201c{statement}\u201d. A denial may have been recorded as a finding, or the reverse.",
        "prompt": "Confirm whether the patient denied or reported this, then correct the statement.",
    },
    AuditFlagType.MISSING_CRITICAL_INFO: {
        "title": "Information missing",
        "why": "An item that is normally documented was not discussed in the transcript.",
        "prompt": "Document it only if it was assessed; otherwise leave it blank.",
    },
    AuditFlagType.ASSUMED_NEGATIVE: {
        "title": "Normal finding assumed",
        "why": "The draft records a negative or normal finding that the transcript never states.",
        "prompt": "Remove it unless you assessed it.",
    },
    AuditFlagType.MEDICATION_AMBIGUITY: {
        "title": "Medication details incomplete",
        "why": "The medication in \u201c{statement}\u201d lacks a clear name, dose, route or frequency in the transcript, or may belong to another person.",
        "prompt": "Clarify with the patient or the medication container before recording.",
    },
    AuditFlagType.UNCERTAINTY_UPGRADED: {
        "title": "Diagnostic certainty warning",
        "why": "The transcript uses a qualified wording (\u201c{quote}\u201d), but the draft states \u201c{statement}\u201d as established.",
        "prompt": "Keep the qualifier (suspected, possible, borderline) unless you have confirmed the diagnosis.",
    },
    AuditFlagType.TRANSCRIPT_CONTRADICTION: {
        "title": "Conflicting statements in transcript",
        "why": "The patient gave conflicting information about this item.",
        "prompt": "Resolve the conflict with the patient and document the confirmed version.",
    },
}

SEVERITY_LABEL = {"info": "Information", "warning": "Needs review", "critical": "Needs review \u2013 high priority"}

UNASSESSED_COPY = (
    "Not discussed in the transcript, so it is left blank. "
    "Complete it only if it was assessed."
)


def line_map(transcript: Optional[Transcript]) -> Dict[str, int]:
    """seg-203 -> 3: the visible line number is the turn's position in this transcript."""
    if not transcript:
        return {}
    return {seg.segment_id: i for i, seg in enumerate(transcript.segments, start=1)}


def line_label(segment_id: str, lines: Dict[str, int]) -> str:
    n = lines.get(segment_id)
    return f"Line {n:02d}" if n else "Unknown line"


def friendly(text: str, lines: Dict[str, int]) -> str:
    """Replace any raw segment IDs inside free text with 'Line NN'."""
    return re.sub(r"seg-\d+", lambda m: line_label(m.group(0), lines), text or "", flags=re.I)


def describe_flag(flag: AuditFlag, claim: SOAPClaim, lines: Dict[str, int]) -> Dict[str, str]:
    copy = FLAG_COPY.get(flag.flag_type, {
        "title": "Review required",
        "why": "This statement needs clinician review.",
        "prompt": "Check it against the transcript.",
    })
    why = copy["why"].format(
        quote=claim.source_exact_quote or "the transcript wording",
        statement=claim.clinician_edited_statement or claim.statement,
    )
    return {
        "title": copy["title"],
        "severity": SEVERITY_LABEL.get(flag.severity.value, "Needs review"),
        "why": why,
        "detail": friendly(flag.message, lines),
        "prompt": copy["prompt"],
    }


def unassessed_label(raw: str) -> str:
    """'Objective: Vital Signs (Unassessed / Not Measured)' -> 'Objective \u00b7 Vital Signs'."""
    section, _, field = raw.partition(":")
    field = re.sub(r"\s*\(.*?\)", "", field).strip() or section.strip()
    return f"{section.strip()} \u00b7 {field}" if field != section.strip() else field


def patient_display(patient_synthetic_id: str) -> str:
    m = re.search(r"\((.*?)\)", patient_synthetic_id or "")
    return m.group(1) if m else patient_synthetic_id
