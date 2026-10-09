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
