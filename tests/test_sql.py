"""The SQL in the audit log says what the statistics engine computes: same numbers, on every request we have."""

import json

import pytest

from hdab import pipeline, register, spe, sql, stats
from hdab.contracts import Request
from hdab.data import load_requests
from hdab.jury import DIR
from hdab.plan import parse

CASES = {r.id: r for r in load_requests()}
for case in json.loads((DIR / "cases.json").read_text(encoding="utf-8")):
    try:
        CASES[case["name"]] = Request.model_validate(case["request"])
    except ValueError:
        pass  # a broken request never reaches the statistics


@pytest.mark.parametrize("name", sorted(CASES))
def test_sql_gives_exactly_the_numbers_of_the_engine(name):
    plan = parse(CASES[name])
    if plan.problems:
        return  # S-046: nothing understood only in part gets numbers
    if plan.per_patient and not plan.cohort_size and not plan.measures:
        return
    numbers = stats.execute(plan, spe=False)
    text, matches = sql.check(plan, numbers)
    assert matches, text


def test_sql_for_the_exact_spe_cohort_and_what_is_copied():
    r = CASES["R05"]
    plan = parse(r)
    text, matches = sql.check(plan, stats.execute(plan, spe=True), spe.held_types(r, plan))
    assert matches and "NOT opted_out" in text and "FROM conditions t" in text and "t.loinc IN ('4548-4')" in text


def test_a_wrong_number_is_reported_as_a_mismatch():
    plan = parse(CASES["R01"])
    numbers = stats.execute(plan)
    numbers["Wien"]["adults"] = 1
    assert sql.check(plan, numbers)[1] is False


def test_text_from_a_request_cannot_break_out_of_a_comment_or_string():
    assert sql._comment("x\nDROP TABLE patients") == "-- x DROP TABLE patients"
    assert sql._text("a' OR 1=1 --") == "'a'' OR 1=1 --'"


def test_the_log_holds_the_sql_and_the_check_but_no_numbers():
    answer = pipeline.submit(CASES["R01"])
    event = next(e for e in register.events("R01") if e["action"] == "query_run")["detail"]
    assert event["sql"] == answer.sql and "FROM patients WHERE NOT opted_out" in event["sql"]
    assert event["matches_computed_numbers"] is True and "3247" not in event["sql"]


def test_a_rejection_runs_no_query():
    pipeline.submit(CASES["R02"])
    assert not [e for e in register.events("R02") if e["action"] == "query_run"]


def test_override_to_statistics_logs_the_query_and_a_rejection_clears_it():
    pipeline.submit(CASES["R05"])
    pipeline.override("R05", "officer.a", "REJECT", "no", ["54"])
    assert register.get("R05")["answer"].sql is None
    pipeline.submit(CASES["R02"])
    new = pipeline.override("R02", "officer.a", "APPROVE_STATISTICAL", "Allowed after all.", ["53"])
    if new.answer is not None:
        assert any(e["action"] == "query_run" for e in register.events("R02"))
