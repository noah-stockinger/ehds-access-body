"""Jury simulation (tests/jury/cases.json, expected outcomes written first; numbers from scripts/jury_oracle.py)."""

import json

import pytest
from fastapi.testclient import TestClient

from hdab.api import app
from hdab.jury import DIR, run

ROWS = {r["name"]: r for r in run()}


@pytest.mark.parametrize("name", sorted(ROWS))
def test_case_as_expected(name):
    r = ROWS[name]
    assert r["ok"], f"{r['id']}: expected {r['expect']}, got {r['got']} ({r['why'][:2]})"
    assert not r["wrong_numbers"] and not r["wrong_decision"] and not r["leaks"]


def test_no_silent_wrong_approval():
    assert not [r["name"] for r in ROWS.values() if r["silent_wrong_approval"]]


def test_api_accepts_request_without_bookkeeping_fields_and_refuses_broken_ones():
    cases = {c["name"]: c["request"] for c in json.loads((DIR / "cases.json").read_text(encoding="utf-8"))}
    client = TestClient(app)
    ok = client.post("/requests", json=cases["no id and no submitted timestamp"])
    assert ok.status_code == 200 and ok.json()["decision"] == "APPROVE_STATISTICAL"
    bad = client.post("/requests", json=cases["missing purpose"])
    assert bad.status_code == 422 and "purpose" in bad.text
