"""Compare Kev off and Kev-assisted on R01–R10 and the red-team/paraphrase set (S-069), plus Kev's agreement table.

Usage: uv run python scripts/compare_modes.py [--runs 3]   (assisted mode needs Kev at $KEV_BASE_URL)
"""

import argparse
import os
import statistics
import sys
import time

from rich.console import Console
from rich.table import Table

from hdab import kev
from hdab.data import load_expected, load_requests
from hdab.metrics import articles_ok, numbers_ok
from hdab.pipeline import decide
from hdab.redteam import run as redteam

THRESHOLDS = [0.5, 0.6, 0.7, 0.8]


def measure(mode: str, runs: int) -> tuple[dict, list]:
    os.environ["KEV_ENABLED"] = "true" if mode == "assisted" else "false"
    requests, expected = load_requests(), load_expected()
    outputs, slowest, last = {r.id: set() for r in requests}, 0.0, {}
    for _ in range(runs):
        for r in requests:
            start = time.perf_counter()
            a = decide(r)
            slowest = max(slowest, time.perf_counter() - start)
            outputs[r.id].add(a.model_dump_json())
            last[r.id] = a
    rows = redteam()
    kev_records = [k for a in last.values() for k in a.kev]
    return {
        "decisions (10)": sum(last[i].decision == e.decision and articles_ok(last[i], e) for i, e in expected.items()),
        "numbers (6)": sum(numbers_ok(last[i].answer, e.answer) for i, e in expected.items() if e.decision != "REJECT"),
        "R01–R10 flagged": sum(a.needs_review for a in last.values()),
        "red team as expected": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
        "silent wrong approvals": sum(r["silent_wrong_approval"] for r in rows),
        "wrong numbers": sum(r["wrong_numbers"] for r in rows),
        f"same in {runs} runs": sum(len(v) == 1 for v in outputs.values()),
        "slowest s": f"{slowest:.2f}",
        "mode": next(iter(last.values())).mode,
    }, [kev_records, last]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    runs = parser.parse_args().runs
    console = Console()
    off, _ = measure("off", runs)
    on, (records, last) = measure("assisted", runs)
    os.environ["KEV_ENABLED"] = "false"

    table = Table(title="Kev off vs. Kev-assisted (S-069)")
    table.add_column("metric")
    table.add_column("off")
    table.add_column("assisted")
    for key in off:
        table.add_row(key, str(off[key]), str(on[key]))
    console.print(table)

    if not records:
        console.print("[yellow]Kev did not answer; no agreement table.[/]")
        return 0
    agree = Table(title="Kev agreement with the rules on R01–R10")
    for col in ["question", "asked", "compared", "agrees", "median confidence", "min confidence"]:
        agree.add_column(col)
    for q in [q for q, *_ in kev.questions(load_requests()[0], None)] + ["K4_plan_faithful"]:
        rs = [k for k in records if k["question"] == q]
        if not rs:
            continue
        compared = [k for k in rs if k["agrees"] is not None]
        confs = [k["confidence"] for k in rs]
        agree.add_row(q, str(len(rs)), str(len(compared)), str(sum(k["agrees"] for k in compared)),
                      f"{statistics.median(confs):.2f}", f"{min(confs):.2f}")
    console.print(agree)

    thr = Table(title="R01–R10 flagged by Kev at each confidence threshold (disagreements always flag)")
    thr.add_column("threshold")
    thr.add_column("requests flagged")
    for t in THRESHOLDS:
        flagged = sum(any(k["agrees"] is False or (k["agrees"] and k["confidence"] < t) for k in a.kev)
                      for a in last.values())
        thr.add_row(f"{t:.2f}", f"{flagged}/10")
    console.print(thr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
