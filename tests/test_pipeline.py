import os
import pytest
from medscribe.pipeline import MedscribePipeline
from medscribe.adapters.mock_adapter import MockModelAdapter
from medscribe.schemas import VerificationStatus, AuditFlagType


def test_pipeline_encounter_01_hypertension():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "encounter_01_hypertension_followup.json")
    pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="standard"))
    transcript = pipeline.load_transcript_from_file(fixture_path)
    draft = pipeline.process_encounter(transcript)

    assert draft.encounter_id == "ENC-SYN-2026-001"
    assert draft.audit_summary.total_claims > 0
    assert draft.audit_summary.supported_claims == draft.audit_summary.total_claims
    assert draft.audit_summary.critical_flags_count == 0

    # Vitals check: BP was measured, but physical exam was empty in encounter
    assert "Objective: Physical Examination (Omitted)" in draft.audit_summary.missing_fields

    # Export check
    exported = pipeline.export_note_text(draft)
    assert "DRAFT CLINICAL DOCUMENTATION AID" in exported
    assert "Amlodipine 5mg PO daily" in exported


def test_pipeline_encounter_02_pediatric():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "encounter_02_pediatric_cough_edgecase.json")
    pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="standard"))
    transcript = pipeline.load_transcript_from_file(fixture_path)
    draft = pipeline.process_encounter(transcript)

    assert draft.encounter_id == "ENC-SYN-2026-002"
    # In encounter 02, vitals were omitted in the clinic turn
    assert "Objective: Vital Signs (Unassessed / Not Measured)" in draft.audit_summary.missing_fields

    # Check antibiotic hold
    med_adv = draft.plan.medications_advised[0]
    assert "Hold antibiotics" in med_adv.statement
    assert med_adv.verification_status == VerificationStatus.SUPPORTED


def test_pipeline_encounter_03_adversarial_traps():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "encounter_03_adversarial_hallucination_trap.json")
    # Using adversarial mock mode
    pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="adversarial"))
    transcript = pipeline.load_transcript_from_file(fixture_path)
    draft = pipeline.process_encounter(transcript)

    assert draft.encounter_id == "ENC-SYN-2026-003"
    # Must flag critical violations
    assert draft.audit_summary.critical_flags_count > 0
    assert draft.audit_summary.unsupported_claims > 0

    # Phantom physical exam check
    pe_claim = draft.objective.physical_exam[0]
    assert pe_claim.verification_status == VerificationStatus.UNSUPPORTED
    assert any(f.flag_type == AuditFlagType.INVALID_SEGMENT_ID for f in pe_claim.audit_flags)

    # Fabricated medication check (CLM-ADV-06 had empty source_segment_ids)
    med_claim = draft.plan.medications_advised[0]
    assert med_claim.verification_status == VerificationStatus.UNSUPPORTED
    assert any(f.flag_type == AuditFlagType.UNSUPPORTED_CLAIM for f in med_claim.audit_flags)


def test_pipeline_export_formats():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "encounter_01_hypertension_followup.json")
    pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="standard"))
    transcript = pipeline.load_transcript_from_file(fixture_path)
    draft = pipeline.process_encounter(transcript)

    # 1. Standard SOAP export
    soap_export = pipeline.export_note_text(draft, note_format="soap")
    assert "--- SUBJECTIVE ---" in soap_export
    assert "--- OBJECTIVE ---" in soap_export
    assert "--- ASSESSMENT ---" in soap_export
    assert "--- PLAN ---" in soap_export
    assert soap_export.index("--- SUBJECTIVE ---") < soap_export.index("--- ASSESSMENT ---")

    # 2. APSO (Epic EHR) export: Assessment & Plan first
    apso_export = pipeline.export_note_text(draft, note_format="apso")
    assert "--- ASSESSMENT ---" in apso_export
    assert "--- PLAN ---" in apso_export
    assert "--- SUBJECTIVE ---" in apso_export
    assert "--- OBJECTIVE ---" in apso_export
    assert apso_export.index("--- ASSESSMENT ---") < apso_export.index("--- SUBJECTIVE ---")

    # 3. General Clinical Summary export
    summary_export = pipeline.export_note_text(draft, note_format="summary")
    assert "--- REASON FOR VISIT & HISTORY ---" in summary_export
    assert "--- CLINICAL EXAMINATION ---" in summary_export
    assert "--- IMPRESSIONS & CARE PLAN ---" in summary_export


def test_pipeline_encounter_05_audio_omission():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "encounter_05_audio_omission_clarification.json")
    pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="standard"))
    transcript = pipeline.load_transcript_from_file(fixture_path)
    draft = pipeline.process_encounter(transcript)

    assert draft.encounter_id == "ENC-SYN-2026-005"
    # 1. Unclarified low-confidence audio turns detected in missing fields audit
    assert any("Acoustic Omission: Unclear Audio" in mf for mf in draft.audit_summary.missing_fields)

    # 2. Add clinician clarification on local device
    seg_006 = [s for s in transcript.segments if s.segment_id == "seg-006"][0]
    seg_006.clinician_clarification = "Atorvastatin 20mg once daily at bedtime"

    seg_008 = [s for s in transcript.segments if s.segment_id == "seg-008"][0]
    seg_008.clinician_clarification = "Skin rash with Amoxicillin in 2021"

    # 3. Re-process with clinician clarifications attached
    audited_resolved = pipeline.process_encounter(transcript)
    assert not any("Acoustic Omission: Unclear Audio" in mf for mf in audited_resolved.audit_summary.missing_fields)

    # 4. Verify local clinician acoustic clarifications are included in export
    export_txt = pipeline.export_note_text(audited_resolved, transcript=transcript)
    assert "--- LOCAL CLINICIAN ACOUSTIC CLARIFICATIONS ---" in export_txt
    assert "Atorvastatin 20mg once daily at bedtime" in export_txt
    assert "Skin rash with Amoxicillin in 2021" in export_txt


