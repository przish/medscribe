import json
import re
from typing import Optional, Dict, Any, Union
from medscribe.schemas import Transcript, SOAPNoteDraft, TranscriptSegment, SpeakerRole
from medscribe.adapters.base import BaseModelAdapter
from medscribe.adapters.mock_adapter import DeterministicModelAdapter
from medscribe.validator import EvidenceValidator


class MedscribePipeline:
    """
    Main orchestration pipeline for Medscribe Local: Proof Mode.
    Takes a consultation transcript, generates draft notes via a local model adapter,
    and runs deterministic audit rules to verify evidence links and detect omissions/hallucinations.
    """

    def __init__(self, adapter: Optional[BaseModelAdapter] = None):
        self.adapter = adapter or DeterministicModelAdapter(mode="standard")

    def load_transcript_from_dict(self, data: Dict[str, Any]) -> Transcript:
        return Transcript(**data)

    def load_transcript_from_file(self, filepath: str) -> Transcript:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.load_transcript_from_dict(data)

    def parse_raw_text_to_transcript(
        self,
        raw_text: str,
        encounter_id: str = "ENC-MANUAL",
        patient_id: str = "SYN-PAT-CUSTOM",
        encounter_date: str = "2026-10-10",
    ) -> Transcript:
        """
        Splits newline-delimited transcript into structured turns.
        Format expected: 'Clinician: text' or 'Patient [00:15]: text' or '[UNCLEAR AUDIO]'.
        Extracts speech timestamps and flags acoustic clarity / model omission markers.
        """
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        segments = []
        for idx, line in enumerate(lines, start=1):
            seg_id = f"seg-{idx:03d}"
            speaker = SpeakerRole.PATIENT
            start_time = None
            is_unclear = False
            acoustic_warning = None

            # Extract timestamp if present e.g. [01:23]
            ts_match = re.search(r"\[(\d{1,2}:\d{2})\]", line)
            if ts_match:
                start_time = ts_match.group(1)

            # Detect acoustic ambiguity / inaudible markers
            if any(marker in line.lower() for marker in ["[unclear audio]", "[unclear]", "[inaudible]", "[low confidence]", "[omitted]"]):
                is_unclear = True
                acoustic_warning = f"Acoustic clarity issue at {start_time or f'Turn {idx}'}: STT detected low confidence or inaudible speech."

            match = re.match(r"^([a-zA-Z]+)(?:\s*\[[^\]]+\])*\s*:\s*(.*)$", line)
            if match:
                spk_str = match.group(1).lower()
                clean_text = match.group(2).strip()
                if spk_str in ("clinician", "doctor", "doc"):
                    speaker = SpeakerRole.CLINICIAN
                    text = clean_text
                elif spk_str == "patient":
                    speaker = SpeakerRole.PATIENT
                    text = clean_text
                elif spk_str == "caregiver":
                    speaker = SpeakerRole.CAREGIVER
                    text = clean_text
                else:
                    text = clean_text
            else:
                text = line

            segments.append(
                TranscriptSegment(
                    segment_id=seg_id,
                    speaker=speaker,
                    start_time=start_time,
                    text=text,
                    is_low_confidence=is_unclear,
                    acoustic_warning=acoustic_warning,
                )
            )

        return Transcript(
            encounter_id=encounter_id,
            patient_synthetic_id=patient_id,
            encounter_date=encounter_date,
            segments=segments,
        )

    def process_encounter(self, transcript: Transcript) -> SOAPNoteDraft:
        """
        End-to-end execution:
        1. Run local inference adapter.
        2. Run deterministic evidence validator.
        3. Return audited draft.
        """
        # Step 1: Model draft extraction
        raw_draft = self.adapter.generate_draft(transcript)

        # Step 2: Deterministic validation & audit
        validator = EvidenceValidator(transcript)
        audited_draft = validator.validate_note(raw_draft)

        return audited_draft

    def export_note_text(
        self,
        draft: SOAPNoteDraft,
        include_audit: bool = True,
        note_format: str = "soap",
        transcript: Optional[Transcript] = None,
    ) -> str:
        """
        Renders the final clinical note as a formatted document with review disclaimers.
        Supports standard SOAP, APSO (Epic/EHR standard), and General Clinical Summary.
        """
        status_banner = "VERIFIED BY CLINICIAN" if draft.clinician_review_confirmed else "UNVERIFIED DRAFT — CLINICIAN REVIEW REQUIRED"
        format_title = "APSO FORMAT (EHR STANDARD)" if note_format == "apso" else ("GENERAL CLINICAL SUMMARY" if note_format == "summary" else "SOAP DOCUMENTATION")
        lines = [
            f"=== MEDSCRIBE {format_title} [{status_banner}] ===",
            f"Encounter ID: {draft.encounter_id}",
            f"Patient ID:   {draft.patient_synthetic_id}",
            f"Notice:       {draft.disclaimer}",
            "",
        ]

        def add_field_claims(header: str, claims):
            if claims:
                lines.append(f"  {header}:")
                for c in claims:
                    status_badge = f"[{c.verification_status.value.upper()}]"
                    stmt = c.clinician_edited_statement or c.statement
                    cites = f"(Source: {', '.join(c.source_segment_ids)})" if c.source_segment_ids else "(NO CITATION)"
                    lines.append(f"    • {status_badge} {stmt} {cites}")
            else:
                lines.append(f"  {header}: [NOT DOCUMENTED / UNASSESSED]")

        if note_format == "apso":
            lines.append("--- ASSESSMENT ---")
            add_field_claims("Clinical Impressions", draft.assessment.clinical_impressions)
            lines.append("")
            lines.append("--- PLAN ---")
            add_field_claims("Medications Advised", draft.plan.medications_advised)
            add_field_claims("Non-Pharmacologic Care", draft.plan.non_pharmacologic_care)
            add_field_claims("Follow-up & Red Flags", draft.plan.follow_up_and_red_flags)
            lines.append("")
            lines.append("--- SUBJECTIVE ---")
            add_field_claims("Chief Complaint", draft.subjective.chief_complaint)
            add_field_claims("History of Present Illness", draft.subjective.history_of_present_illness)
            add_field_claims("Current Medications", draft.subjective.current_medications)
            add_field_claims("Allergies", draft.subjective.allergies)
            lines.append("")
            lines.append("--- OBJECTIVE ---")
            add_field_claims("Vital Signs", draft.objective.vital_signs)
            add_field_claims("Physical Examination", draft.objective.physical_exam)
            add_field_claims("Diagnostic Tests", draft.objective.diagnostic_tests)
        elif note_format == "summary":
            lines.append("--- REASON FOR VISIT & HISTORY ---")
            add_field_claims("Chief Complaint", draft.subjective.chief_complaint)
            add_field_claims("History of Present Illness", draft.subjective.history_of_present_illness)
            add_field_claims("Current Medications", draft.subjective.current_medications)
            add_field_claims("Allergies", draft.subjective.allergies)
            lines.append("")
            lines.append("--- CLINICAL EXAMINATION ---")
            add_field_claims("Vital Signs", draft.objective.vital_signs)
            add_field_claims("Physical Examination", draft.objective.physical_exam)
            add_field_claims("Diagnostic Tests", draft.objective.diagnostic_tests)
            lines.append("")
            lines.append("--- IMPRESSIONS & CARE PLAN ---")
            add_field_claims("Clinical Impressions", draft.assessment.clinical_impressions)
            add_field_claims("Medications Advised", draft.plan.medications_advised)
            add_field_claims("Non-Pharmacologic Care", draft.plan.non_pharmacologic_care)
            add_field_claims("Follow-up & Red Flags", draft.plan.follow_up_and_red_flags)
        else:
            lines.append("--- SUBJECTIVE ---")
            add_field_claims("Chief Complaint", draft.subjective.chief_complaint)
            add_field_claims("History of Present Illness", draft.subjective.history_of_present_illness)
            add_field_claims("Current Medications", draft.subjective.current_medications)
            add_field_claims("Allergies", draft.subjective.allergies)
            lines.append("")
            lines.append("--- OBJECTIVE ---")
            add_field_claims("Vital Signs", draft.objective.vital_signs)
            add_field_claims("Physical Examination", draft.objective.physical_exam)
            add_field_claims("Diagnostic Tests", draft.objective.diagnostic_tests)
            lines.append("")
            lines.append("--- ASSESSMENT ---")
            add_field_claims("Clinical Impressions", draft.assessment.clinical_impressions)
            lines.append("")
            lines.append("--- PLAN ---")
            add_field_claims("Medications Advised", draft.plan.medications_advised)
            add_field_claims("Non-Pharmacologic Care", draft.plan.non_pharmacologic_care)
            add_field_claims("Follow-up & Red Flags", draft.plan.follow_up_and_red_flags)

        # Local Clinician Clarifications (Audio Omissions / Inaudible Speech Resolved Locally)
        if transcript:
            clarified = [s for s in transcript.segments if s.clinician_clarification]
            if clarified:
                lines.append("")
                lines.append("--- LOCAL CLINICIAN ACOUSTIC CLARIFICATIONS ---")
                lines.append("Auditory dropouts / inaudible speech clarified on local device:")
                for cs in clarified:
                    ts = f"[{cs.start_time}] " if cs.start_time else ""
                    lines.append(f"  • {cs.segment_id} {ts}({cs.speaker.value}):")
                    lines.append(f"    Transcribed STT: “{cs.text}”")
                    lines.append(f"    Clinician Clarification: “{cs.clinician_clarification}”")

        if include_audit:
            lines.append("")
            lines.append("--- AUDIT & SAFETY SUMMARY ---")
            lines.append(f"Total Claims: {draft.audit_summary.total_claims}")
            lines.append(f"Supported Claims: {draft.audit_summary.supported_claims}")
            lines.append(f"Unsupported / Flagged Claims: {draft.audit_summary.unsupported_claims}")
            lines.append(f"Critical Safety Flags: {draft.audit_summary.critical_flags_count}")
            lines.append(f"Warnings: {draft.audit_summary.warning_flags_count}")
            if draft.audit_summary.missing_fields:
                lines.append("Missing / Unassessed Consultation Elements:")
                for mf in draft.audit_summary.missing_fields:
                    lines.append(f"  ! {mf}")

        return "\n".join(lines)
