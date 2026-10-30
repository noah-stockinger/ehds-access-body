"""Jury simulation (tests/jury/): new, messy and broken requests with the outcome written down first.

`outcome`: reject | review | approve | invalid (the request JSON is refused, as `POST /requests` would with 422).
A silent wrong approval is an approval without `needs_review` where the case expects anything else.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from hdab.contracts import Request
from hdab.metrics import leaks, numbers_ok
from hdab.pipeline import decide
from hdab.redteam import outcome

DIR = Path(__file__).resolve().parents[2] / "tests" / "jury"


def run(decide_fn=decide) -> list[dict]:
    expected = json.loads((DIR / "expected.json").read_text(encoding="utf-8"))
    rows = []
    for case in json.loads((DIR / "cases.json").read_text(encoding="utf-8")):
        rid = case["request"].get("id", "")
        try:
            a = decide_fn(Request.model_validate(case["request"]))
        except ValidationError as e:
            got, a, why = "invalid", None, [err["msg"] for err in e.errors()]
        else:
            got, why = outcome(a), a.review_reasons
        want = case["expect"]
        approved = got == "approve"
        rows.append({
            "name": case["name"], "kind": case["kind"], "id": rid, "expect": want, "got": got,
            "decision": a.decision if a else None, "ok": got == want,
            "silent_wrong_approval": approved and want != "approve",
            "wrong_decision": approved and a.decision != case.get("decision", a.decision),
            "wrong_numbers": approved and rid in expected and not numbers_ok(a.answer, expected[rid]),
            "leaks": leaks(a) if a else [], "why": why,
        })
    return rows
