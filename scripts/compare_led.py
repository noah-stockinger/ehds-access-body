"""Rules only vs. model-led (KEV_MODE=led) on R01–R10, the red team and both holdout sets.

Usage: KEV_PROVIDER=jev uv run python scripts/compare_led.py   (jev needs TYPESAFE_API_KEY in .env)
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from hdab.data import load_expected, load_requests
from hdab.metrics import articles_ok, numbers_ok
from hdab.pipeline import decide
from hdab.redteam import CASES, run

ROOT = Path(__file__).resolve().parents[1]
SETS = {"red team": CASES, "holdout 1": ROOT / "tests/redteam/holdout.json", "holdout 2": ROOT / "tests/redteam/holdout2.json"}


def official() -> dict:
    expected = load_expected()
    got = {r.id: decide(r) for r in load_requests()}
    return {"decisions": sum(got[i].decision == e.decision and articles_ok(got[i], e) for i, e in expected.items()),
            "numbers": sum(numbers_ok(got[i].answer, e.answer) for i, e in expected.items() if e.decision != "REJECT"),
            "flagged": [i for i, a in got.items() if a.needs_review]}


def main() -> None:
    load_dotenv(ROOT / ".env")
    results = {}
    for m in ["off", "led"]:
        os.environ["KEV_MODE"] = m
        results[m] = {"official": official(), **{n: run(cases=p) for n, p in SETS.items()}}
    print(f"{'':28} {'rules only':>22} {'led':>22}")
    o, l = results["off"]["official"], results["led"]["official"]
    print(f"{'R01–R10 decisions':28} {o['decisions']:>22} {l['decisions']:>22}")
    print(f"{'R01–R10 numbers':28} {o['numbers']:>22} {l['numbers']:>22}")
    print(f"{'R01–R10 flagged':28} {','.join(o['flagged']) or '-':>22} {','.join(l['flagged']) or '-':>22}")
    for n in SETS:
        def s(rows):
            return f"{sum(r['ok'] for r in rows)}/{len(rows)} ok, {sum(r['silent_wrong_approval'] for r in rows)} silent"
        print(f"{n:28} {s(results['off'][n]):>22} {s(results['led'][n]):>22}")
    print("\ncases not as expected (led):")
    for n in SETS:
        for r in results["led"][n]:
            if not r["ok"]:
                print(f"  {n:9} {r['name'][:50]:50} expect {r['expect']:7} got {r['got']:7}"
                      + ("  SILENT" if r["silent_wrong_approval"] else "") + f"  {r['why'][:1]}")


if __name__ == "__main__":
    sys.exit(main())
