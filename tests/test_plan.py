import json
from pathlib import Path

import pandas as pd
import pytest

from hdab import icd10, vocab
from hdab.contracts import Request
from hdab.data import load_requests, load_tables
from hdab.pipeline import decide
from hdab.plan import parse

needs_who_file = pytest.mark.skipif(not icd10.XML.exists(), reason="WHO ICD-10 file not installed")

REQUESTS = {r.id: r for r in load_requests()}
NEW = Request.model_validate_json((Path(__file__).parent / "fixtures" / "new_request.json").read_text(encoding="utf-8"))


def variant(rid: str, **changes) -> Request:
    return REQUESTS[rid].model_copy(update=changes)


@pytest.mark.parametrize("rid", sorted(REQUESTS))
def test_s056_r01_to_r10_have_no_unclaimed_words(rid):
    plan = parse(REQUESTS[rid])
    assert plan.unclaimed == [] and plan.ambiguous == [] and plan.has_report


def test_s056_extra_clause_lists_exactly_its_words_and_returns_no_numbers():
    r = variant("R01", definitions=REQUESTS["R01"].definitions + ["Exclude patients who had a stroke in the last year."])
    got = decide(r)
    assert got.unclaimed_words == ["exclude", "patients", "had", "stroke", "last", "year"]
    assert got.needs_review and got.answer is None


def test_s046_nonsense_definition_flags_and_keeps_a_valid_decision():
    got = decide(variant("R01", definitions=REQUESTS["R01"].definitions + ["Flurble the wibbles twice."]))
    assert got.decision == "APPROVE_STATISTICAL" and got.needs_review and got.answer is None
    assert any("Flurble" in r for r in got.review_reasons)


def test_s058_diabetes_without_type_is_ambiguous():
    got = decide(variant("R01", definitions=["Adult = aged 18 or older on 31 December 2025.",
                                             "Report per region: adults with diabetes."]))
    assert got.needs_review and got.answer is None
    assert any("S-058" in r and "E10" in r and "E11" in r for r in got.review_reasons)


def test_s058_heart_failure_is_an_inferred_mapping_shown_to_staff():
    got = decide(variant("R01", question="How many adults have heart failure, per region?",
                         definitions=["Adult = aged 18 or older on 31 December 2025.",
                                      "Report per region: adults with heart failure."]))
    assert not got.needs_review and got.answer is not None
    assert any("Inferred mapping" in n and "I50" in n for n in got.notes)


def test_s007_given_prefix_is_used_exactly():
    plan = parse(REQUESTS["R03"])
    assert plan.terms["oral anticoagulant"].codes == ("B01AA", "B01AF")
    assert plan.terms["atrial fibrillation"].codes == ("I48",)


@needs_who_file
def test_s070_r03_carries_i48_note_without_blocking():
    got = decide(REQUESTS["R03"])
    note = next(n for n in got.notes if "Definition mismatch" in n)
    assert "I48.3" in note and "None of these codes occur" in note
    assert not got.needs_review and got.answer is not None


@needs_who_file
def test_s070_note_lists_flutter_codes_present_in_the_data(monkeypatch):
    t = dict(load_tables())
    t["conditions"] = pd.concat([t["conditions"], pd.DataFrame(
        [{"patient_id": "p-00000000", "icd10": "I48.3", "description": "Typical atrial flutter", "onset_date": "2020-01-01"}])])
    monkeypatch.setattr(vocab, "load_tables", lambda: t)
    assert "these codes occur: I48.3" in vocab.mismatch_note("Atrial fibrillation", ("I48",))


def test_s059_per_patient_report_in_statistics_request_returns_no_records():
    got = decide(variant("R01", definitions=REQUESTS["R01"].definitions[:2]
                         + ["Report for each patient: patient ID and region."]))
    assert got.decision == "APPROVE_STATISTICAL" and got.needs_review and got.answer is None
    assert any("S-059" in r for r in got.review_reasons)


@pytest.mark.parametrize("rid, words", [("R03", ["I48", "B01AA", "65-74"]), ("R08", ["C50", "female", "39156-5"])])
def test_s057_plan_is_rendered_in_plain_english(rid, words):
    text = " ".join(decide(REQUESTS[rid]).plan_text)
    assert all(w in text for w in words) and "Art. 71" in text


def test_s047_grouped_by_data_holder_shows_all_three_with_zero_cells():
    r = variant("R08", question="How many patients have breast cancer, per hospital and age band?",
                definitions=["Breast cancer = any condition with an ICD-10 code starting with C50.",
                             "Age bands on 31 December 2025: 0-9, 10-19.",
                             "Report per data_holder and age band: patients with breast cancer."])
    got = decide(r).answer
    assert set(got) == {"Klinikum Nord", "Klinikum Süd", "Klinikum West"}
    assert all(cell == {"patients_with_breast_cancer": "<10"} for h in got.values() for cell in h.values())


def test_s006_s011_new_request_on_primary_diagnosis_per_hospital():
    t = load_tables()
    ok = t["patients"][~t["patients"]["opted_out"]]["patient_id"]
    e = t["encounters"]
    e = e[e["primary_icd10"].str.startswith("I50") & e["start_date"].str.startswith("2025") & e["patient_id"].isin(ok)]
    want = e.groupby("data_holder").size().to_dict()
    got = decide(NEW).answer
    assert {h: v["heart_failure_encounters"] for h, v in got.items()} == {h: (n if n >= 10 else "<10") for h, n in want.items()}


def test_s001_new_request_json_runs_through_the_api_entry_point():
    assert json.loads(decide(NEW).model_dump_json())["decision"] == "APPROVE_STATISTICAL"
