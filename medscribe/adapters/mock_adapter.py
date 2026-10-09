from typing import Optional
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


class DeterministicModelAdapter(BaseModelAdapter):
    """
    Deterministic clinical inference adapter generating structured SOAP notes from transcript fixtures.
    Useful for offline testing, UI development, and adversarial regression validation.
    """

    def __init__(self, mode: str = "standard"):
        """
        mode:
          - "standard": outputs faithful draft with correct citations
          - "adversarial": injects deliberate hallucinations, invalid segment IDs, and altered negation
        """
        self.mode = mode

    def is_available(self) -> bool:
        return True

    def engine_name(self) -> str:
        return f"Deterministic Clinical Engine ({self.mode})"

    def generate_draft(self, transcript: Transcript) -> SOAPNoteDraft:
        enc_id = transcript.encounter_id

        # Only use static calibrated reference benchmarks for the exact synthetic test fixtures
        if enc_id == "ENC-SYN-2026-001":
            return self._build_hypertension_draft(transcript)
        elif enc_id == "ENC-SYN-2026-002":
            return self._build_pediatric_draft(transcript)
        elif enc_id == "ENC-SYN-2026-003" or (self.mode == "adversarial" and enc_id.startswith("ENC-SYN")):
            return self._build_adversarial_draft(transcript)
        else:
            return self._build_generic_draft(transcript)

    def _build_hypertension_draft(self, transcript: Transcript) -> SOAPNoteDraft:
        draft = SOAPNoteDraft(
            encounter_id=transcript.encounter_id,
            patient_synthetic_id=transcript.patient_synthetic_id,
            subjective=SubjectiveSection(
                chief_complaint=[
                    SOAPClaim(
                        claim_id="CLM-S-01",
                        category="Subjective",
                        field="chief_complaint",
                        statement="Follow-up review of blood pressure; occasional mild occipital headaches in the afternoon when fatigued.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-001", "seg-002"],
                        source_exact_quote="occasional mild occipital headaches in the afternoon when I am tired from work",
                    )
                ],
                history_of_present_illness=[
                    SOAPClaim(
                        claim_id="CLM-S-02",
                        category="Subjective",
                        field="hpi",
                        statement="Denies chest pain, shortness of breath, palpitations, or ankle edema.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-003", "seg-004"],
                        source_exact_quote="No chest pain at all. No difficulty breathing and no ankle swelling.",
                    )
                ],
                current_medications=[
                    SOAPClaim(
                        claim_id="CLM-S-03",
                        category="Subjective",
                        field="current_medications",
                        statement="Amlodipine 5mg PO daily in the morning; admits occasionally missing Sunday dose.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-006"],
                        source_exact_quote="I take Amlodipine 5 milligrams once daily in the morning. To be honest, I sometimes miss the Sunday dose",
                    )
                ],
                allergies=[
                    SOAPClaim(
                        claim_id="CLM-S-04",
                        category="Subjective",
                        field="allergies",
                        statement="Penicillin (reports pruritic skin rash and hives).",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-008"],
                        source_exact_quote="Penicillin gives me an itchy skin rash and hives.",
                    )
                ],
            ),
            objective=ObjectiveSection(
                vital_signs=[
                    SOAPClaim(
                        claim_id="CLM-O-01",
                        category="Objective",
                        field="vitals",
                        statement="Sitting BP right arm: 138/86 mmHg, Pulse: 74 bpm regular.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-009"],
                        source_exact_quote="It is 138 over 86 millimeters of mercury, pulse rate 74 regular.",
                    )
                ],
                physical_exam=[],  # Deliberately empty (no other physical exam discussed)
                diagnostic_tests=[],
            ),
            assessment=AssessmentSection(
                clinical_impressions=[
                    SOAPClaim(
                        claim_id="CLM-A-01",
                        category="Assessment",
                        field="clinical_impressions",
                        statement="Essential hypertension, borderline elevated, likely related to intermittent medication non-adherence on weekends.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-010"],
                        source_exact_quote="Your blood pressure is borderline elevated today, likely related to missed doses.",
                    )
                ]
            ),
            plan=PlanSection(
                medications_advised=[
                    SOAPClaim(
                        claim_id="CLM-P-01",
                        category="Plan",
                        field="medications_advised",
                        statement="Maintain Amlodipine 5mg PO once daily.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-010"],
                        source_exact_quote="We will keep Amlodipine at 5mg daily.",
                    )
                ],
                non_pharmacologic_care=[
                    SOAPClaim(
                        claim_id="CLM-P-02",
                        category="Plan",
                        field="non_pharmacologic_care",
                        statement="Advised setting a recurring phone alarm to avoid missing Sunday doses.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-010"],
                        source_exact_quote="Please set a phone alarm so you don't miss Sunday doses.",
                    )
                ],
                follow_up_and_red_flags=[
                    SOAPClaim(
                        claim_id="CLM-P-03",
                        category="Plan",
                        field="follow_up_and_red_flags",
                        statement="Return in 4 weeks for repeat blood pressure check; return sooner if occipital headaches worsen.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-010"],
                        source_exact_quote="Return in 4 weeks for repeat BP check, or sooner if headaches worsen.",
                    )
                ],
            ),
        )
        return draft

    def _build_pediatric_draft(self, transcript: Transcript) -> SOAPNoteDraft:
        draft = SOAPNoteDraft(
            encounter_id=transcript.encounter_id,
            patient_synthetic_id=transcript.patient_synthetic_id,
            subjective=SubjectiveSection(
                chief_complaint=[
                    SOAPClaim(
                        claim_id="CLM-S-101",
                        category="Subjective",
                        field="chief_complaint",
                        statement="Dry hacky cough for 3 days; no fever today.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-102"],
                        source_exact_quote="he has had a dry hacky cough for 3 days. He does NOT have fever today",
                    )
                ],
                history_of_present_illness=[
                    SOAPClaim(
                        claim_id="CLM-S-102",
                        category="Subjective",
                        field="hpi",
                        statement="Denies vomiting, diarrhea, or respiratory distress; appetite and activity preserved.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-104"],
                        source_exact_quote="No vomiting, no diarrhea, and breathing seems normal.",
                    )
                ],
                current_medications=[
                    SOAPClaim(
                        claim_id="CLM-S-103",
                        category="Subjective",
                        field="current_medications",
                        statement="Paracetamol discontinued due to stomach upset; received warm water with honey.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-106"],
                        source_exact_quote="We stopped Paracetamol yesterday because he complained of an upset tummy after taking it, and we only gave warm water with honey last night.",
                    )
                ],
                allergies=[
                    SOAPClaim(
                        claim_id="CLM-S-104",
                        category="Subjective",
                        field="allergies",
                        statement="No known drug allergies reported.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-106"],
                        source_exact_quote="Does he have any allergies? None that we know of.",
                    )
                ],
            ),
            objective=ObjectiveSection(
                vital_signs=[],  # Vitals were never taken during this encounter
                physical_exam=[
                    SOAPClaim(
                        claim_id="CLM-O-101",
                        category="Objective",
                        field="physical_exam",
                        statement="Lungs clear bilaterally with good air entry, no wheezes or crackles. Mild pharyngeal erythema; tonsils not enlarged.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-107"],
                        source_exact_quote="Lungs are clear bilaterally with good air entry, no wheezes or crackles. Throat has mild pharyngeal erythema, tonsils are not enlarged.",
                    )
                ],
                diagnostic_tests=[],
            ),
            assessment=AssessmentSection(
                clinical_impressions=[
                    SOAPClaim(
                        claim_id="CLM-A-101",
                        category="Assessment",
                        field="clinical_impressions",
                        statement="Suspected uncomplicated viral upper respiratory infection.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-108"],
                        source_exact_quote="This appears to be an uncomplicated viral upper respiratory infection.",
                    )
                ]
            ),
            plan=PlanSection(
                medications_advised=[
                    SOAPClaim(
                        claim_id="CLM-P-101",
                        category="Plan",
                        field="medications_advised",
                        statement="Hold antibiotics; antibiotics not indicated.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-108"],
                        source_exact_quote="We should hold off on any antibiotics—antibiotics are not indicated here.",
                    )
                ],
                non_pharmacologic_care=[
                    SOAPClaim(
                        claim_id="CLM-P-102",
                        category="Plan",
                        field="non_pharmacologic_care",
                        statement="Supportive hydration and honey for cough relief.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-108"],
                        source_exact_quote="Continue oral hydration, honey for cough relief",
                    )
                ],
                follow_up_and_red_flags=[
                    SOAPClaim(
                        claim_id="CLM-P-103",
                        category="Plan",
                        field="follow_up_and_red_flags",
                        statement="Return immediately if tachypnea, breathing difficulty, or high fever develops.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-108"],
                        source_exact_quote="come back immediately if you notice fast breathing or high fever.",
                    )
                ],
            ),
        )
        return draft

    def _build_adversarial_draft(self, transcript: Transcript) -> SOAPNoteDraft:
        """
        Draft injected with deliberate hallucinations & invalid references for adversarial validation.
        """
        draft = SOAPNoteDraft(
            encounter_id=transcript.encounter_id,
            patient_synthetic_id=transcript.patient_synthetic_id,
            subjective=SubjectiveSection(
                chief_complaint=[
                    SOAPClaim(
                        claim_id="CLM-ADV-01",
                        category="Subjective",
                        field="chief_complaint",
                        statement="Routine wellness checkup.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-201"],
                        source_exact_quote="routine checkup",
                    )
                ],
                history_of_present_illness=[
                    # NEGATION FLIP: Claims patient has diabetes, but transcript denies it / hedged borderline
                    SOAPClaim(
                        claim_id="CLM-ADV-02",
                        category="Subjective",
                        field="hpi",
                        statement="Patient diagnosed with Type 2 Diabetes Mellitus.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-202"],
                        source_exact_quote="fasting sugar was borderline",
                    )
                ],
                current_medications=[
                    # MEDICATION AMBIGUITY
                    SOAPClaim(
                        claim_id="CLM-ADV-03",
                        category="Subjective",
                        field="current_medications",
                        statement="Takes half or one tablet of something white for cholesterol, unknown dose.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-204"],
                        source_exact_quote="half a tablet or maybe one tablet of something white for cholesterol",
                    )
                ],
                allergies=[],
            ),
            objective=ObjectiveSection(
                vital_signs=[],
                physical_exam=[
                    # PHANTOM EXAM: No physical exam was done, bogus reference ID seg-999
                    SOAPClaim(
                        claim_id="CLM-ADV-04",
                        category="Objective",
                        field="physical_exam",
                        statement="Heart: Normal S1/S2, lungs clear to auscultation bilaterally.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-999"],  # Non-existent segment
                        source_exact_quote="heart sounds normal",  # Bogus quote
                    )
                ],
                diagnostic_tests=[],
            ),
            assessment=AssessmentSection(
                clinical_impressions=[
                    # UPGRADED UNCERTAINTY
                    SOAPClaim(
                        claim_id="CLM-ADV-05",
                        category="Assessment",
                        field="clinical_impressions",
                        statement="Definite Hyperlipidemia and Uncontrolled Diabetes.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-202"],
                        source_exact_quote="fasting sugar was borderline",
                    )
                ]
            ),
            plan=PlanSection(
                medications_advised=[
                    # FABRICATED MEDICATION WITHOUT ANY TRANSCRIPT SUPPORT
                    SOAPClaim(
                        claim_id="CLM-ADV-06",
                        category="Plan",
                        field="medications_advised",
                        statement="Prescribe Atorvastatin 40mg PO at bedtime and Metformin 500mg PO BID.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=[],  # Completely unsupported
                        source_exact_quote=None,
                    )
                ],
                non_pharmacologic_care=[],
                follow_up_and_red_flags=[
                    SOAPClaim(
                        claim_id="CLM-ADV-07",
                        category="Plan",
                        field="follow_up_and_red_flags",
                        statement="Return next Tuesday morning fasting for blood lab work.",
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=["seg-205"],
                        source_exact_quote="Come back next Tuesday fasting.",
                    )
                ],
            ),
        )
        return draft

    def _build_generic_draft(self, transcript: Transcript) -> SOAPNoteDraft:
        if not transcript.segments:
            return SOAPNoteDraft(
                encounter_id=transcript.encounter_id,
                patient_synthetic_id=transcript.patient_synthetic_id,
                subjective=SubjectiveSection(),
            )

        cc_claims = []
        hpi_claims = []
        med_claims = []
        allergy_claims = []
        vitals_claims = []
        pe_claims = []
        assessment_claims = []
        plan_med_claims = []
        plan_care_claims = []

        claim_idx = 1
        for seg in transcript.segments:
            text = seg.text.strip()
            if not text:
                continue
            low = text.lower()
            s_id = seg.segment_id
            is_clinician = (seg.speaker.value.lower() in ("clinician", "doctor", "doc"))

            # Keywords covering English, Tagalog, and Taglish clinical dialogue
            symptom_words = [
                "masakit", "pananakit", "kumikirot", "kirot", "hapdi", "ulo", "tiyan", "ubo", "sipon",
                "lagnat", "nahihilo", "hilo", "hininga", "hingal", "hirap", "leeg", "katawan", "likod",
                "tuhod", "binti", "dibdib", "pain", "headache", "cough", "fever", "chest", "dizzy",
                "shortness", "fatigue", "weak", "tired", "sakit", "nararamdaman", "problema"
            ]
            med_words = [
                "gamot", "inumin", "iniinom", "maintenance", "reseta", "take", "pill", "tablet", "kapsula",
                "mg", "dose", "amlodipine", "metformin", "paracetamol", "biogesic", "losartan", "aspirin", "antibiotic"
            ]
            allergy_words = ["allergy", "alergi", "allergic", "bawal", "rash", "singaw", "hives", "kati", "nangangati"]
            vitals_words = ["bp", "blood pressure", "120/", "130/", "140/", "150/", "over", "temperatura", "temp", "timbang", "kilo", "weight", "pulse", "tibok"]
            assess_words = ["hypertension", "altapresyon", "diabetes", "trangkaso", "flu", "impeksyon", "infection", "hika", "asthma", "pneumonia", "impression", "diagnos", "findings"]
            plan_words = ["pahinga", "rest", "diet", "iwasan", "tubig", "water", "bumalik", "balik", "next week", "follow-up", "lab", "laboratoryo", "test", "checkup", "payo", "gawin", "ireseta", "prescribe"]

            if any(w in low for w in allergy_words):
                allergy_claims.append(
                    SOAPClaim(
                        claim_id=f"CLM-GEN-{claim_idx:02d}",
                        category="Subjective",
                        field="allergies",
                        statement=text,
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=[s_id],
                        source_exact_quote=text,
                    )
                )
                claim_idx += 1
            elif any(w in low for w in med_words) and (is_clinician or "ireseta" in low or "prescribe" in low):
                plan_med_claims.append(
                    SOAPClaim(
                        claim_id=f"CLM-GEN-{claim_idx:02d}",
                        category="Plan",
                        field="medications_advised",
                        statement=text,
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=[s_id],
                        source_exact_quote=text,
                    )
                )
                claim_idx += 1
            elif any(w in low for w in med_words):
                med_claims.append(
                    SOAPClaim(
                        claim_id=f"CLM-GEN-{claim_idx:02d}",
                        category="Subjective",
                        field="current_medications",
                        statement=text,
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=[s_id],
                        source_exact_quote=text,
                    )
                )
                claim_idx += 1
            elif any(w in low for w in vitals_words):
                vitals_claims.append(
                    SOAPClaim(
                        claim_id=f"CLM-GEN-{claim_idx:02d}",
                        category="Objective",
                        field="vital_signs",
                        statement=text,
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=[s_id],
                        source_exact_quote=text,
                    )
                )
                claim_idx += 1
            elif any(w in low for w in assess_words) and is_clinician:
                assessment_claims.append(
                    SOAPClaim(
                        claim_id=f"CLM-GEN-{claim_idx:02d}",
                        category="Assessment",
                        field="clinical_impressions",
                        statement=text,
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=[s_id],
                        source_exact_quote=text,
                    )
                )
                claim_idx += 1
            elif any(w in low for w in plan_words) and is_clinician:
                plan_care_claims.append(
                    SOAPClaim(
                        claim_id=f"CLM-GEN-{claim_idx:02d}",
                        category="Plan",
                        field="non_pharmacologic_care",
                        statement=text,
                        verification_status=VerificationStatus.SUPPORTED,
                        source_segment_ids=[s_id],
                        source_exact_quote=text,
                    )
                )
                claim_idx += 1
            elif any(w in low for w in symptom_words):
                if not cc_claims:
                    cc_claims.append(
                        SOAPClaim(
                            claim_id=f"CLM-GEN-{claim_idx:02d}",
                            category="Subjective",
                            field="chief_complaint",
                            statement=text,
                            verification_status=VerificationStatus.SUPPORTED,
                            source_segment_ids=[s_id],
                            source_exact_quote=text,
                        )
                    )
                else:
                    hpi_claims.append(
                        SOAPClaim(
                            claim_id=f"CLM-GEN-{claim_idx:02d}",
                            category="Subjective",
                            field="hpi",
                            statement=text,
                            verification_status=VerificationStatus.SUPPORTED,
                            source_segment_ids=[s_id],
                            source_exact_quote=text,
                        )
                    )
                claim_idx += 1
            else:
                # Capture conversational and descriptive dialogue dynamically
                if not is_clinician:
                    if not cc_claims:
                        cc_claims.append(
                            SOAPClaim(
                                claim_id=f"CLM-GEN-{claim_idx:02d}",
                                category="Subjective",
                                field="chief_complaint",
                                statement=text,
                                verification_status=VerificationStatus.SUPPORTED,
                                source_segment_ids=[s_id],
                                source_exact_quote=text,
                            )
                        )
                    else:
                        hpi_claims.append(
                            SOAPClaim(
                                claim_id=f"CLM-GEN-{claim_idx:02d}",
                                category="Subjective",
                                field="hpi",
                                statement=text,
                                verification_status=VerificationStatus.SUPPORTED,
                                source_segment_ids=[s_id],
                                source_exact_quote=text,
                            )
                        )
                    claim_idx += 1
                elif is_clinician and len(text) > 15:
                    plan_care_claims.append(
                        SOAPClaim(
                            claim_id=f"CLM-GEN-{claim_idx:02d}",
                            category="Plan",
                            field="non_pharmacologic_care",
                            statement=text,
                            verification_status=VerificationStatus.SUPPORTED,
                            source_segment_ids=[s_id],
                            source_exact_quote=text,
                        )
                    )
                    claim_idx += 1

        if not cc_claims and transcript.segments:
            first_s = transcript.segments[0]
            cc_claims.append(
                SOAPClaim(
                    claim_id="CLM-GEN-01",
                    category="Subjective",
                    field="chief_complaint",
                    statement=first_s.text,
                    verification_status=VerificationStatus.SUPPORTED,
                    source_segment_ids=[first_s.segment_id],
                    source_exact_quote=first_s.text,
                )
            )

        return SOAPNoteDraft(
            encounter_id=transcript.encounter_id,
            patient_synthetic_id=transcript.patient_synthetic_id,
            subjective=SubjectiveSection(
                chief_complaint=cc_claims,
                history_of_present_illness=hpi_claims,
                current_medications=med_claims,
                allergies=allergy_claims,
            ),
            objective=ObjectiveSection(
                vital_signs=vitals_claims,
                physical_exam=pe_claims,
            ),
            assessment=AssessmentSection(
                clinical_impressions=assessment_claims,
            ),
            plan=PlanSection(
                medications_advised=plan_med_claims,
                non_pharmacologic_care=plan_care_claims,
            ),
        )


# Backward-compatible alias
MockModelAdapter = DeterministicModelAdapter

