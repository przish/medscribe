"""
End-to-end Offline Smoke Test for Medscribe Local: Proof Mode
Executes the full pipeline on all 3 synthetic fixtures without network calls.
"""
import os
import sys

from medscribe.pipeline import MedscribePipeline
from medscribe.adapters.mock_adapter import MockModelAdapter
from medscribe.schemas import VerificationStatus


def run_smoke_test():
    print("=" * 60)
    print("🩺 MEDSCRIBE LOCAL — OFFLINE SMOKE TEST")
    print("=" * 60)

    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    fixture_files = [
        "encounter_01_hypertension_followup.json",
        "encounter_02_pediatric_cough_edgecase.json",
        "encounter_03_adversarial_hallucination_trap.json",
        "encounter_04_tagalog_consultation.json",
        "encounter_05_audio_omission_clarification.json",
    ]

    pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="standard"))

    for fname in fixture_files:
        path = os.path.join(fixtures_dir, fname)
        print(f"\n[TESTING FIXTURE]: {fname}")
        transcript = pipeline.load_transcript_from_file(path)
        print(f"  • Loaded encounter: {transcript.encounter_id} ({len(transcript.segments)} turns)")

        draft = pipeline.process_encounter(transcript)
        summary = draft.audit_summary

        print(f"  • Total claims extracted: {summary.total_claims}")
        print(f"  • Supported claims:       {summary.supported_claims}")
        print(f"  • Unsupported / flagged:  {summary.unsupported_claims}")
        print(f"  • Critical audit flags:   {summary.critical_flags_count}")
        print(f"  • Missing fields detected:{len(summary.missing_fields)}")

        if "003" in fname:
            # Adversarial trap should flag issues
            adv_pipeline = MedscribePipeline(adapter=MockModelAdapter(mode="adversarial"))
            adv_draft = adv_pipeline.process_encounter(transcript)
            print(f"  • Adversarial mode audit: {adv_draft.audit_summary.critical_flags_count} critical flags caught!")
            assert adv_draft.audit_summary.critical_flags_count > 0, "Adversarial flags failed to trigger!"

        if "005" in fname:
            # Acoustic omission fixture
            print("  • Verifying audio omission detection and clinician clarification...")
            assert any("Acoustic Omission: Unclear Audio" in mf for mf in draft.audit_summary.missing_fields)
            transcript.segments[5].clinician_clarification = "Atorvastatin 20mg at bedtime"
            resolved_draft = pipeline.process_encounter(transcript)
            exported_clarified = pipeline.export_note_text(resolved_draft, transcript=transcript)
            assert "--- LOCAL CLINICIAN ACOUSTIC CLARIFICATIONS ---" in exported_clarified
            print("  • Acoustic omission & local clinician clarification: SUCCESS")

        exported_soap = pipeline.export_note_text(draft, note_format="soap", transcript=transcript)
        assert "--- SUBJECTIVE ---" in exported_soap and "DRAFT CLINICAL DOCUMENTATION AID" in exported_soap
        exported_apso = pipeline.export_note_text(draft, note_format="apso", transcript=transcript)
        assert "--- ASSESSMENT ---" in exported_apso
        exported_summary = pipeline.export_note_text(draft, note_format="summary", transcript=transcript)
        assert "--- REASON FOR VISIT & HISTORY ---" in exported_summary
        print("  • Export verification (SOAP / APSO / Summary): SUCCESS")

    print("\n" + "=" * 60)
    print("✅ ALL OFFLINE SMOKE TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_smoke_test()
