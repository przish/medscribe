import json
import logging
from typing import Optional, Dict, Any
import requests

from medscribe.adapters.base import BaseModelAdapter
from medscribe.schemas import (
    Transcript,
    SOAPNoteDraft,
    SubjectiveSection,
    ObjectiveSection,
    AssessmentSection,
    PlanSection,
    SOAPClaim,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a clinical documentation assistant for Medscribe.
Convert the provided medical consultation transcript into a structured draft SOAP note.
CRITICAL SAFETY RULES:
1. Every claim MUST include the exact source segment ID(s) (e.g. ["seg-001"]) and an exact verbatim quote from the transcript.
2. DO NOT fabricate vitals, allergies, physical exam findings, or medications. If not mentioned in the transcript, leave the list EMPTY.
3. Preserve patient denials and qualifiers (e.g. 'denies chest pain', 'sometimes misses dose', 'borderline'). Do not convert denials into positive findings.
4. Output strictly valid JSON conforming to the requested schema.
"""


class OllamaModelAdapter(BaseModelAdapter):
    """
    Local AI Adapter connecting to Ollama running on localhost.
    100% on-device inference; zero cloud communication.
    """

    def __init__(self, host: str = "http://127.0.0.1:11434", model_name: str = "llama3.2:3b", timeout_seconds: int = 45):
        self.host = host.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout_seconds

    def engine_name(self) -> str:
        return f"Local Ollama ({self.model_name})"

    def is_available(self) -> bool:
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=2)
            if res.status_code == 200:
                data = res.json()
                models = [m.get("name") for m in data.get("models", [])]
                # Check if requested model or matching prefix exists
                return any(self.model_name in m for m in models) or len(models) > 0
            return False
        except Exception:
            return False

    def get_installed_models(self) -> list:
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=2)
            if res.status_code == 200:
                return [m.get("name") for m in res.json().get("models", [])]
            return []
        except Exception:
            return []

    def generate_draft(self, transcript: Transcript) -> SOAPNoteDraft:
        prompt = f"""
{SYSTEM_PROMPT}

Encounter ID: {transcript.encounter_id}
Patient ID: {transcript.patient_synthetic_id}

TRANSCRIPT:
{transcript.full_text()}

Respond ONLY with a JSON object with this exact structure:
{{
  "subjective": {{
    "chief_complaint": [{{"claim_id": "CLM-S-01", "statement": "...", "source_segment_ids": ["seg-001"], "source_exact_quote": "..."}}],
    "history_of_present_illness": [...],
    "current_medications": [...],
    "allergies": [...]
  }},
  "objective": {{
    "vital_signs": [...],
    "physical_exam": [...],
    "diagnostic_tests": [...]
  }},
  "assessment": {{
    "clinical_impressions": [...]
  }},
  "plan": {{
    "medications_advised": [...],
    "non_pharmacologic_care": [...],
    "follow_up_and_red_flags": [...]
  }}
}}
"""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,  # Low temperature for factual fidelity
            },
        }

        try:
            resp = requests.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            raw_response = data.get("response", "{}")
            parsed = json.loads(raw_response)
            return self._parse_json_to_draft(parsed, transcript)
        except Exception as e:
            logger.error(f"Ollama inference error: {e}")
            raise RuntimeError(f"Ollama inference failed: {e}")

    def _parse_json_to_draft(self, data: Dict[str, Any], transcript: Transcript) -> SOAPNoteDraft:
        draft = SOAPNoteDraft(
            encounter_id=transcript.encounter_id,
            patient_synthetic_id=transcript.patient_synthetic_id,
        )

        def make_claims(category: str, field_name: str, raw_items: list) -> list:
            claims = []
            for idx, item in enumerate(raw_items or []):
                claims.append(
                    SOAPClaim(
                        claim_id=item.get("claim_id", f"CLM-{category[0]}-{idx+1:02d}"),
                        category=category,
                        field=field_name,
                        statement=item.get("statement", ""),
                        verification_status=VerificationStatus.UNSUPPORTED,
                        source_segment_ids=item.get("source_segment_ids", []),
                        source_exact_quote=item.get("source_exact_quote"),
                    )
                )
            return claims

        subj = data.get("subjective", {})
        draft.subjective = SubjectiveSection(
            chief_complaint=make_claims("Subjective", "chief_complaint", subj.get("chief_complaint", [])),
            history_of_present_illness=make_claims("Subjective", "hpi", subj.get("history_of_present_illness", [])),
            current_medications=make_claims("Subjective", "current_medications", subj.get("current_medications", [])),
            allergies=make_claims("Subjective", "allergies", subj.get("allergies", [])),
        )

        obj = data.get("objective", {})
        draft.objective = ObjectiveSection(
            vital_signs=make_claims("Objective", "vitals", obj.get("vital_signs", [])),
            physical_exam=make_claims("Objective", "physical_exam", obj.get("physical_exam", [])),
            diagnostic_tests=make_claims("Objective", "diagnostic_tests", obj.get("diagnostic_tests", [])),
        )

        ass = data.get("assessment", {})
        draft.assessment = AssessmentSection(
            clinical_impressions=make_claims("Assessment", "clinical_impressions", ass.get("clinical_impressions", [])),
        )

        plan = data.get("plan", {})
        draft.plan = PlanSection(
            medications_advised=make_claims("Plan", "medications_advised", plan.get("medications_advised", [])),
            non_pharmacologic_care=make_claims("Plan", "non_pharmacologic_care", plan.get("non_pharmacologic_care", [])),
            follow_up_and_red_flags=make_claims("Plan", "follow_up_and_red_flags", plan.get("follow_up_and_red_flags", [])),
        )

        return draft
