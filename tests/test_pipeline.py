import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hdab.api import app
from hdab.contracts import Answer
from hdab.data import REQUESTS_DIR

client = TestClient(app)
NEW_REQUEST = Path(__file__).parent / "fixtures" / "new_request.json"
REQUEST_FILES = sorted(REQUESTS_DIR.glob("R*.json")) + [NEW_REQUEST]


@pytest.mark.parametrize("path", REQUEST_FILES, ids=lambda p: p.stem)
def test_every_request_gets_a_schema_valid_answer(path):
    r = client.post("/requests", json=json.loads(path.read_text(encoding="utf-8")))
    assert r.status_code == 200
    answer = Answer.model_validate(r.json())
    body = r.json()
    for field in ["decision", "articles", "reason", "trace", "mode", "needs_review", "review_reasons"]:
        assert field in body
    assert answer.mode == "Rules only"
    assert answer.trace


def test_missing_required_field_is_a_clear_422():
    body = json.loads(NEW_REQUEST.read_text(encoding="utf-8"))
    del body["purpose"]
    r = client.post("/requests", json=body)
    assert r.status_code == 422
    assert any(e["loc"][-1] == "purpose" and e["type"] == "missing" for e in r.json()["detail"])


def test_unknown_fields_are_kept():
    from hdab.contracts import Request

    req = Request.model_validate_json(NEW_REQUEST.read_text(encoding="utf-8"))
    assert req.model_extra == {"contact_email": "unknown field, must be kept"}
