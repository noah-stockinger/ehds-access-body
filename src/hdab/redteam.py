"""Red-team and paraphrase run (S-060): own requests with the outcome written down first.

A silent wrong approval is an approval without `needs_review` where the case expects a rejection or a review.
"""

import json
from pathlib import Path

from hdab.contracts import Answer, Request
from hdab.data import load_expected, load_requests
from hdab.metrics import numbers_ok
from hdab.pipeline import decide

CASES = Path(__file__).resolve().parents[2] / "tests" / "redteam" / "cases.json"


def outcome(a: Answer) -> str:
    if a.decision == "REJECT":
        return "reject"
    return "review" if a.needs_review else "approve"


def run(decide_fn=decide, cases: Path = CASES) -> list[dict]:
    base = {r.id: r for r in load_requests()}
    expected = load_expected()
    rows = []
    for case in json.loads(cases.read_text(encoding="utf-8")):
        req = Request.model_validate(base[case["base"]].model_dump() | case["changes"])
        a = decide_fn(req)
        got = outcome(a)
        want = case["expect"]
        same = case.get("same_as")
        rows.append({
            "name": case["name"], "expect": want, "got": got, "decision": a.decision,
            "ok": got == want,
            "silent_wrong_approval": got == "approve" and want != "approve",
            "wrong_numbers": bool(same) and got == "approve" and (
                a.decision != expected[same].decision or not numbers_ok(a.answer, expected[same].answer)),
            "why": a.review_reasons,
            "kev": a.kev,
        })
    return rows
