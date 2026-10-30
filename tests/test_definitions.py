"""S-070: name and code must agree. Rules against the WHO file, the model's reading mocked (no GPU, no network)."""

import pytest
from fastapi.testclient import TestClient

from hdab import definitions, icd10, kev, register
from hdab.api import app
from hdab.contracts import Applicant, Request
from hdab.data import load_requests
from hdab.pipeline import decide
from hdab.plan import parse

pytestmark = pytest.mark.skipif(not icd10.XML.exists(), reason="WHO ICD-10 file not installed")
REPORT = "Report per region: patients with the term."


def warnings(definition: str, relation: str | None = None, monkeypatch=None):
    if relation:
        monkeypatch.setenv("KEV_MODE", "assisted")
        monkeypatch.setattr(kev, "post", lambda p: {"answers": {"K7_definition": {
            "type": "choice", "choice": relation, "confidence": 0.9}}, "model": "mock"})
    r = Request(id="T", submitted="2026-10-30T10:00:00+01:00", applicant=Applicant(name="A", organisation="B", country="AT"),
                requested_as="health data request", requested_format="anonymised statistics", purpose="Research.",
                question="How many?", definitions=[definition, REPORT])
    return definitions.check(parse(r)).warnings


def icd(name: str, code: str) -> str:
    return f"{name} = any condition with an ICD-10 code starting with {code}."


@pytest.fixture(autouse=True)
def no_cache():
    kev._relation.cache_clear()


def test_modifier_subcodes_exist_though_the_file_does_not_list_them():
    assert icd10.exists("E11") and icd10.exists("E11.9") and not icd10.exists("J99.9")


def test_r01_to_r10_rules_only_warn_only_on_r03_and_the_check_changes_no_number(monkeypatch):
    got = {r.id: decide(r) for r in load_requests()}
    for rid, a in got.items():
        assert [w.definition for w in a.definition_warnings] == (["Atrial fibrillation"] if rid == "R03" else []), rid
    monkeypatch.setattr(definitions, "check", lambda plan: definitions.Checked())
    for r in load_requests():
        a = decide(r)
        assert (a.decision, a.answer) == (got[r.id].decision, got[r.id].answer), r.id


def test_r03_warns_about_flutter_and_does_not_go_to_review():
    r03 = next(r for r in load_requests() if r.id == "R03")
    got = decide(r03)
    assert got.definition_warnings[0].severity == "check" and "I48.3" in got.definition_warnings[0].message
    assert not got.needs_review and got.answer is not None


@pytest.mark.parametrize("name, code, severity", [
    ("Asthma", "J99.9", "wrong"),  # no such code
    ("Type 2 diabetes", "E10", "wrong"),  # the hand-built table knows another code
    ("Hypertension", "I48", "wrong"),
    ("Gaucher disease", "E75", "check"),  # a subcode fits better
    ("Heart attack", "I21", "unsure"),  # a synonym the words cannot confirm
    ("Depression", "F33", None),  # the table lists it
    ("Stroke", "I64", None),  # not in the table, but WHO's title says stroke
    ("Type 2 diabetes", "E11", None),
    ("COPD", "J44", None),
    ("Breast cancer", "C50", None),
])
def test_rules_alone(name, code, severity):
    got = warnings(icd(name, code))
    assert [w.severity for w in got] == ([severity] if severity else [])


@pytest.mark.parametrize("name, code, relation, severity", [
    ("Hypothyroidism", "E05", "different", "wrong"),  # the words alone cannot tell
    ("Hypertension", "I48", "broader", "check"),  # conflict, but the two disagree
    ("Atrial fibrillation", "I48", "match", "check"),  # the model cannot clear a rule finding
    ("Hay fever", "E11", "broader", "check"),
    ("Heart attack", "I21", "match", None),  # the model clears "can't confirm"
    ("Type 2 diabetes", "E11", "match", None),
])
def test_rules_and_model_combined(monkeypatch, name, code, relation, severity):
    got = warnings(icd(name, code), relation, monkeypatch)
    assert [w.severity for w in got] == ([severity] if severity else [])


def test_model_is_not_asked_about_a_code_that_does_not_exist(monkeypatch):
    got = warnings(icd("Asthma", "J99.9"), "match", monkeypatch)
    assert got[0].severity == "wrong"


def test_atc_and_loinc_use_the_table_only(monkeypatch):
    monkeypatch.setenv("KEV_MODE", "assisted")
    monkeypatch.setattr(kev, "post", lambda p: pytest.fail("no WHO wording for ATC, the model would answer from memory"))
    assert warnings("Statin = ATC code starting with C09AA.")[0].severity == "wrong"
    assert warnings("Statin = ATC code starting with C10AA.") == []


def test_only_the_definition_goes_to_the_model(monkeypatch):
    sent = []
    monkeypatch.setenv("KEV_MODE", "assisted")
    monkeypatch.setattr(kev, "post", lambda p: sent.append(p) or {"answers": {"K7_definition": {
        "type": "choice", "choice": "match", "confidence": 0.9}}})
    warnings(icd("Asthma", "J45"))
    assert len(sent) == 1 and "Research." not in sent[0]["state"] and "WHO ICD-10 J45: Asthma" in sent[0]["state"]


def test_model_off_sends_nothing(monkeypatch):
    monkeypatch.delenv("KEV_MODE", raising=False)
    monkeypatch.setattr(kev, "post", lambda p: pytest.fail("S-052"))
    assert warnings(icd("Asthma", "J45")) == []


def test_unreachable_model_falls_back_to_the_rules_and_says_so(monkeypatch):
    monkeypatch.setenv("KEV_MODE", "assisted")
    def down(p):
        raise ValueError("down")
    monkeypatch.setattr(kev, "post", down)
    r = Request(id="T", submitted="2026-10-30T10:00:00+01:00", applicant=Applicant(name="A", organisation="B", country="AT"),
                requested_as="health data request", requested_format="anonymised statistics", purpose="Research.",
                question="How many?", definitions=[icd("Heart attack", "I21"), REPORT])
    got = definitions.check(parse(r))
    assert got.warnings[0].severity == "unsure" and "did not answer" in got.notes[0]


def test_missing_who_file_is_said_not_silent(monkeypatch, tmp_path):
    monkeypatch.setattr(icd10, "XML", tmp_path / "none.xml")
    icd10.categories.cache_clear()
    try:
        r03 = next(r for r in load_requests() if r.id == "R03")
        got = decide(r03)
        assert got.definition_warnings == [] and any("not installed" in n for n in got.notes)
        assert got.answer is not None
    finally:
        icd10.categories.cache_clear()


FORM = {"applicant": {"name": "A", "organisation": "B", "country": "AT"}, "requested_as": "health data request",
        "purpose": "We plan a quality programme for older patients.", "question": "How many patients have asthma, per region?",
        "plan_confirmed": True}


@pytest.mark.parametrize("code, confirmed, status", [("I10", False, 422), ("I10", True, 200), ("J45", False, 200)])
def test_form_needs_confirmation_only_when_warned(code, confirmed, status):
    body = FORM | {"definitions": [icd("Asthma", code), "Report per region: patients with asthma."],
                   "warnings_confirmed": confirmed}
    r = TestClient(app).post("/form/submit", json=body)
    assert r.status_code == status, r.text
    if status == 200 and code == "I10":
        assert any(e["action"] == "sent despite definition warnings" for e in register.events(r.json()["id"]))


def test_precheck_returns_warnings_apart_from_the_notes():
    body = FORM | {"definitions": [icd("Asthma", "I10"), "Report per region: patients with asthma."]}
    got = TestClient(app).post("/form/precheck", json=body).json()
    assert got["definition_warnings"][0]["severity"] == "wrong"
    assert got["definition_warnings"][0]["message"] not in got["notes"]


def test_only_the_sentences_that_failed_are_marked_not_every_use_of_their_words():
    """A word in a sentence the parser could not read is fine elsewhere: "December", "condition", the term's own name."""
    from hdab.pipeline import decide

    adult = "Adult = aged 18 or older on 31 December 2025."
    chd = "Coronary heart disease = any condition with an ICD-10 code starting with I20, I21, I22, I23, I24 or I25."
    window = "Past 5 years = a coronary heart disease condition whose start_date is from 1 January 2021 to 31 December 2025."
    a = decide(Request(id="CHD", applicant={"name": "Dr. Test", "organisation": "Medical University of Graz", "country": "AT"},
                       requested_as="health data request", purpose="Research on improving treatment of coronary heart disease.",
                       question="How many adults had coronary heart disease in the past 5 years per region?",
                       definitions=[adult, chd, window, "Report per region: adults with coronary heart disease in the past 5 years."]))
    assert window in a.unclaimed_parts and adult not in a.unclaimed_parts and chd not in a.unclaimed_parts
    assert "december" in a.unclaimed_words  # why highlighting by single words marked the correct first line
    assert a.answer is None and a.needs_review  # S-046: no numbers, never a guess at the date window
    assert any(r.startswith("Data:") and "occurs nowhere" in r for r in a.review_reasons)  # the data has no I20-I25


def test_unsure_warning_goes_to_review_but_changes_no_decision(monkeypatch):
    monkeypatch.setenv("KEV_MODE", "off")
    r03 = next(r for r in load_requests() if r.id == "R03")
    a = decide(r03.model_copy(update={"definitions": [icd("Gout", "E11"), *r03.definitions[1:]],
                                      "question": r03.question.replace("atrial fibrillation", "gout")}))
    assert [w.severity for w in a.definition_warnings] == ["unsure"]
    assert a.decision == "APPROVE_STATISTICAL" and a.needs_review
    assert any(r.startswith('S-070: "Gout"') for r in a.review_reasons)
