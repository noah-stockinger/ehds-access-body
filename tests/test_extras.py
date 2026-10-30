import json
import re

from fastapi.testclient import TestClient

from hdab import pipeline
from hdab.api import app
from hdab.data import load_requests

REQUESTS = {r.id: r for r in load_requests()}
client = TestClient(app)


def test_s051_overlapping_requests_differing_by_fewer_than_10_are_flagged():
    first = REQUESTS["R01"]
    assert not pipeline.submit(first).needs_review
    # same applicant, adults aged 19+ instead of 18+: each region differs by a few 18-year-olds
    second = first.model_copy(update={"id": "R01b", "definitions": [
        "Adult = aged 19 or older on 31 December 2025.", *first.definitions[1:]]})
    got = pipeline.submit(second)
    assert got.needs_review and any("S-051" in r for r in got.review_reasons)


def test_s051_other_applicant_is_not_compared():
    pipeline.submit(REQUESTS["R01"])
    other = REQUESTS["R01"].model_copy(update={"id": "R01c", "applicant": REQUESTS["R08"].applicant, "definitions": [
        "Adult = aged 19 or older on 31 December 2025.", *REQUESTS["R01"].definitions[1:]]})
    assert not any("S-051" in r for r in pipeline.submit(other).review_reasons)


def leaves(value):
    if isinstance(value, dict):
        return [x for v in value.values() for x in leaves(v)]
    return [value]


def test_s082_public_list_has_no_numbers():
    for rid in sorted(REQUESTS):
        pipeline.submit(REQUESTS[rid])
        pipeline.confirm(rid, "officer.a")
    listed = client.get("/public/decisions").json()
    assert [d["id"] for d in listed] == sorted(REQUESTS)
    assert all(set(d) == {"id", "organisation", "purpose", "decision", "articles", "reason"} for d in listed)
    text = json.dumps(listed, ensure_ascii=False)
    answer_numbers = {v for rid in REQUESTS for v in leaves(pipeline.decide(REQUESTS[rid]).answer or {})
                      if isinstance(v, (int, float)) and v >= 100}
    assert not any(re.search(rf"\b{v:g}\b", text) for v in answer_numbers)
    assert not re.search(r"\bp-[0-9a-f]{8}\b", text)
