from decimal import Decimal

from hdab.data import load_requests, load_tables
from hdab.pipeline import decide
from hdab.plan import parse
from hdab.stats import Engine, count_cell, round1

REQUESTS = {r.id: r for r in load_requests()}


def test_s016_halves_round_up():
    assert round1(Decimal("0.25")) == 0.3
    assert round1(Decimal("0.35")) == 0.4
    assert round1(Decimal("2.45")) == 2.5
    assert round1(Decimal("2.44")) == 2.4


def test_s014_counts_below_10_including_0():
    assert count_cell(0) == "<10" and count_cell(9) == "<10" and count_cell(10) == 10


def test_s012_latest_value_per_patient():
    o = load_tables()["observations"]
    hba1c = o[o["loinc"] == "4548-4"]
    pid = hba1c["patient_id"].value_counts().index[0]
    rows = hba1c[hba1c["patient_id"] == pid].sort_values("date")
    assert len(rows) >= 2
    engine = Engine(parse(REQUESTS["R02"]))
    assert engine.latest(engine.plan.terms["hba1c"])[pid] == rows["value"].iloc[-1]


def test_s008_r05_cohort_excludes_opt_outs():
    assert decide(REQUESTS["R05"]).answer == {"cohort_size": 1152}
    t = load_tables()
    p = t["patients"]
    adults = set(p[2025 - p["birth_date"].str[:4].astype(int) >= 18]["patient_id"])
    t2d = set(t["conditions"][t["conditions"]["icd10"].str.startswith("E11")]["patient_id"])
    hba1c = set(t["observations"][t["observations"]["loinc"] == "4548-4"]["patient_id"])
    assert len(adults & t2d & hba1c) == 1207


def test_s013_s015_r08_shows_all_regions_and_suppresses_small_means():
    got = decide(REQUESTS["R08"]).answer
    assert len(got) == 9
    for cell in got.values():
        if cell["women_with_bmi"] == "<10":
            assert cell["mean_bmi"] == "suppressed"
