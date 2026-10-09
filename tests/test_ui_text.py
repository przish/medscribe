from medscribe.schemas import AuditFlag, AuditFlagSeverity, AuditFlagType, SOAPClaim
from medscribe.ui_text import FLAG_COPY, describe_flag, friendly, unassessed_label


def test_every_flag_type_has_clinical_copy_without_raw_tags():
    for ft in AuditFlagType:
        assert ft in FLAG_COPY
        blob = " ".join(FLAG_COPY[ft].values())
        assert ft.value not in blob and "_" not in FLAG_COPY[ft]["title"]


def test_describe_flag_uses_transcript_quote_and_line_numbers():
    claim = SOAPClaim(claim_id="C1", category="Assessment", field="a",
                      statement="Uncontrolled diabetes", source_exact_quote="fasting sugar was borderline")
    flag = AuditFlag(flag_type=AuditFlagType.UNCERTAINTY_UPGRADED, severity=AuditFlagSeverity.WARNING,
                     message="See seg-203", suggested_action="x")
    d = describe_flag(flag, claim, {"seg-203": 3})
    assert "fasting sugar was borderline" in d["why"] and "Uncontrolled diabetes" in d["why"]
    assert d["detail"] == "See Line 03" and "uncertainty_upgraded" not in str(d)


def test_unassessed_label_and_friendly():
    assert unassessed_label("Objective: Vital Signs (Unassessed / Not Measured)") == "Objective \u00b7 Vital Signs"
    assert friendly("seg-9", {}) == "Unknown line"
