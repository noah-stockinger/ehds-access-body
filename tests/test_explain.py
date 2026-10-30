"""Staff get an explanation for every rule step and every review reason the system can produce."""

import json

import pytest
from fastapi.testclient import TestClient

from hdab import explain, pipeline, register, views
from hdab.api import app
from hdab.contracts import Request
from hdab.data import load_requests
from hdab.jury import DIR
from hdab.kev import MODEL_STEP

REQUESTS = list(load_requests())
for case in json.loads((DIR / "cases.json").read_text(encoding="utf-8")):
    try:
        REQUESTS.append(Request.model_validate(case["request"]))
    except ValueError:
        pass
ANSWERS = [pipeline.decide(r) for r in REQUESTS]


def test_every_rule_step_is_explained():
    steps = {s.rule for a in ANSWERS for s in a.trace} | {MODEL_STEP, f"{MODEL_STEP} (Art. 54)"}
    assert not [s for s in steps if explain.rule(s) is None]
    for entry in explain.RULES.values():
        assert entry.keys() == {"what", "checked", "why", "matched", "not_matched"} and all(entry.values())


def test_every_review_reason_and_signal_is_explained():
    assert not [r for a in ANSWERS for r in a.review_reasons if explain.review(r) is None]
    assert not [s for a in ANSWERS for s in a.signals if explain.signal(s) is None]


@pytest.mark.parametrize("reason", [
    "D-08: x", "S-054: x", "S-034: x", "S-072: x", "S-064: x", "S-061: x", "S-070: x", "S-051: x", "Sanity: x", "S-018: x", "S-049: x"])
def test_reasons_the_cases_may_not_reach_are_explained_too(reason):
    assert explain.review(reason)


def test_staff_view_carries_them_and_the_applicant_view_does_not():
    pipeline.submit(REQUESTS[1])  # R02, rejected
    entry = register.get("R02")
    seen = views.staff(entry)["explanations"]
    assert seen["checklist"] == explain.CHECKLIST["REJECT"]
    assert seen["rules"]["1 prohibited purpose (Art. 54)"]["what"]
    assert "explanations" not in views.applicant(entry) and "sql" not in views.applicant(entry)


def test_checklist_does_not_mention_numbers_when_none_were_computed():
    a = next(x for x in ANSWERS if x.decision == "APPROVE_STATISTICAL" and x.answer is not None)
    assert "Look at the numbers" in explain.for_answer(a)["checklist"][-1]
    assert "No numbers were computed" in explain.for_answer(a.model_copy(update={"answer": None}))["checklist"][-1]


def test_unknown_reason_gets_a_fallback_rather_than_a_crash():
    a = ANSWERS[0].model_copy(update={"review_reasons": ["Something new"]})
    assert explain.for_answer(a)["review"][0]["why"]


def test_results_csv_only_after_release_and_keeps_small_cells():
    client = TestClient(app)
    r01 = next(r for r in REQUESTS if r.id == "R01")
    client.post("/requests", json=r01.model_dump())
    url = "/applicant/requests/R01/results.csv"
    assert client.get(url).status_code == 404  # S-071: not before staff confirm
    client.post("/staff/requests/R01/confirm", json={"staff": "officer.a"})
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="R01-results.csv"' in r.headers["content-disposition"]
    lines = r.content.decode("utf-8-sig").splitlines()
    assert lines[0].split(",")[0] == "region" and any(line.startswith("Wien,3247") for line in lines) and len(lines) == 10
    assert any(e["action"] == "results_exported" for e in client.get("/register/R01/log").json())


def test_results_csv_refused_for_a_rejection_and_for_records():
    client = TestClient(app)
    for rid in ("R02", "R05"):
        r = next(x for x in REQUESTS if x.id == rid)
        client.post("/requests", json=r.model_dump())
        client.post(f"/staff/requests/{rid}/confirm", json={"staff": "officer.a"})
        assert client.get(f"/applicant/requests/{rid}/results.csv").status_code == 404


def test_csv_with_two_groups_and_with_no_group():
    entry = {"request": next(r for r in REQUESTS if r.id == "R01"),
             "answer": ANSWERS[0].model_copy(update={"answer": {"cohort_size": "<10"}})}
    assert "cohort_size\r\n<10" in views.results_csv(entry)
    entry["answer"] = ANSWERS[0].model_copy(update={"answer": {"Wien": {"m": {"n": 12}, "f": {"n": "<10"}}}})
    assert views.results_csv(entry).splitlines()[1].startswith("Wien,m,12")
