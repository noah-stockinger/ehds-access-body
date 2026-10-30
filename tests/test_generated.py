"""R01–R10-style requests on the generated dataset (data/generated/), where every expected number is known by construction."""

from pathlib import Path

import duckdb
import pytest

from hdab import data, icd10, pipeline, spe
from hdab.data import load_requests
from hdab.pipeline import decide

needs_who_file = pytest.mark.skipif(not icd10.XML.exists(), reason="WHO ICD-10 file not installed")

GENERATED = Path(__file__).resolve().parents[1] / "data" / "generated" / "data"
REQUESTS = {r.id: r for r in load_requests()}


@pytest.fixture(autouse=True)
def generated_data(monkeypatch):
    monkeypatch.setattr(data, "DATA_DIR", GENERATED)
    data.load_tables.cache_clear()
    yield
    data.load_tables.cache_clear()


def test_ids_are_generated_not_challenge_ids():
    p = data.load_tables()["patients"]
    assert p["patient_id"].str.startswith("g-").all()


def test_r01_small_cells_opt_outs_and_age_boundary():
    a = decide(REQUESTS["R01"]).answer
    assert a["Burgenland"] == {"adults": 30, "adults_with_type_2_diabetes": 10, "prevalence_pct": 33.3}
    assert a["Kärnten"] == {"adults": 29, "adults_with_type_2_diabetes": "<10", "prevalence_pct": "suppressed"}
    assert a["Wien"] == {"adults": 32, "adults_with_type_2_diabetes": 12, "prevalence_pct": 37.5}  # 3 opted out
    assert a["Tirol"] == {"adults": 30, "adults_with_type_2_diabetes": 10, "prevalence_pct": 33.3}  # 17-year-old out
    assert a["Oberösterreich"]["adults"] == 152 and a["Vorarlberg"]["adults"] == 20
    assert len(a) == 9


def test_r09_band_edges_active_medication_and_half_up():
    a = decide(REQUESTS["R09"]).answer
    assert a["50-64"] == {"adults_with_hypertension": 40, "with_active_ace_inhibitor_pct": 50.0,
                          "with_active_arb_pct": "suppressed"}
    assert a["65+"] == {"adults_with_hypertension": 80, "with_active_ace_inhibitor_pct": "suppressed",
                        "with_active_arb_pct": 16.3}
    assert a["18-49"]["adults_with_hypertension"] == 12


def test_r08_latest_bmi_and_mean_half_up():
    a = decide(REQUESTS["R08"]).answer
    assert a["Salzburg"] == {"women_with_bmi": 10, "mean_bmi": 26.3}
    assert a["Steiermark"] == {"women_with_bmi": "<10", "mean_bmi": "suppressed"}
    assert a["Wien"] == {"women_with_bmi": "<10", "mean_bmi": "suppressed"}


@needs_who_file
def test_r03_mismatch_note_lists_flutter_codes_in_this_data():
    got = decide(REQUESTS["R03"])
    assert any("these codes occur: I48.3" in n for n in got.notes)
    assert got.answer["65-74"] == {"patients_with_atrial_fibrillation": 12, "have_no_active_oral_anticoagulant": 12,
                                   "share_have_no_active_oral_anticoagulant_pct": 100.0}
    assert got.answer["75-84"]["patients_with_atrial_fibrillation"] == "<10"


def test_r07_inpatient_stays_year_type_and_opt_outs():
    a = decide(REQUESTS["R07"]).answer
    assert a["Vorarlberg"] == {"inpatient_stays": 10} and a["Kärnten"] == {"inpatient_stays": 10}
    assert a["Wien"] == {"inpatient_stays": "<10"}


def test_primary_diagnosis_per_hospital():
    new = REQUESTS["R07"].model_copy(update={"definitions": [
        "Heart failure stay = encounter with type 'inpatient' whose primary_icd10 starts with I50.",
        "Count stays (not patients) whose start_date is in 2025.",
        "Report per data_holder: heart failure stays."]})
    a = decide(new).answer
    assert a == {"Klinikum Nord": {"heart_failure_stays": 10}, "Klinikum Süd": {"heart_failure_stays": "<10"},
                 "Klinikum West": {"heart_failure_stays": "<10"}}


def test_r05_spe_holds_only_cohort_and_hba1c():
    answer = pipeline.submit(REQUESTS["R05"])
    assert answer.answer == {"cohort_size": 22}  # Burgenland 10 + Wien 12; opted-out Wien patients excluded
    with duckdb.connect(str(spe.path("R05")), read_only=True) as con:
        assert con.execute("SELECT DISTINCT loinc FROM observations").fetchall() == [("4548-4",)]
        assert con.execute("SELECT count(*) FROM observations").fetchone()[0] == 10 + 24
    assert spe.proof("R05") == {"cohort_size": 22, "tables": {"conditions": 22, "medications": 10, "observations": 34},
                                "opted_out_ids_inside": 0}
