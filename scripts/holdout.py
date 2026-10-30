"""Fair test of Kev: fresh cases (tests/redteam/holdout.json) that neither the rules nor Kev were tuned on.

Prints rules-only vs. Kev-assisted per case, Kev's category answer and where Kev disagrees with the rules.
Usage: uv run python scripts/holdout.py   (needs Kev at $KEV_BASE_URL)
"""

import os
from pathlib import Path

from hdab.redteam import run

CASES = Path(__file__).resolve().parents[1] / "tests" / "redteam" / "holdout.json"


def main() -> None:
    os.environ["KEV_ENABLED"] = "false"
    off = run(cases=CASES)
    os.environ["KEV_ENABLED"] = "true"
    on = run(cases=CASES)
    print(f"{'case':55} {'expect':7} {'rules':7} {'+kev':7}  K1 choice (conf) · disagreements")
    for a, b in zip(off, on):
        k1 = next((k for k in b["kev"] if k["question"] == "K1_category"), None)
        dis = [k["question"] for k in b["kev"] if k["agrees"] is False]
        k1s = f"{k1['answer']['choice']} ({k1['confidence']:.2f})" if k1 else "-"
        print(f"{a['name'][:55]:55} {a['expect']:7} {a['got']:7} {b['got']:7}  {k1s} · {', '.join(dis) or '-'}")
    for name, rows in [("rules only", off), ("kev-assisted", on)]:
        print(f"{name}: as expected {sum(r['ok'] for r in rows)}/{len(rows)}, "
              f"silent wrong approvals {sum(r['silent_wrong_approval'] for r in rows)}")


if __name__ == "__main__":
    main()
