"""Metric run over R01–R10 (S-017, S-021, S-025, S-026, S-029). Exit code 0 only if every column is green.

Usage: uv run python scripts/metrics.py [--runs 3]
"""

import argparse
import sys
import time

from rich.console import Console
from rich.table import Table

from hdab.data import load_expected, load_requests
from hdab.metrics import articles_ok, leaks, numbers_ok
from hdab.pipeline import decide


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    runs = parser.parse_args().runs

    requests, expected = load_requests(), load_expected()
    outputs: dict[str, list[str]] = {r.id: [] for r in requests}
    seconds: dict[str, float] = {r.id: 0.0 for r in requests}
    last = {}
    for _ in range(runs):
        for r in requests:
            start = time.perf_counter()
            answer = decide(r)
            seconds[r.id] = max(seconds[r.id], time.perf_counter() - start)
            outputs[r.id].append(answer.model_dump_json())
            last[r.id] = answer

    table = Table(title=f"R01–R10, {runs} runs")
    for col in ["request", "decision", "articles", "numbers", "leaks", f"same in {runs}", "slowest s"]:
        table.add_column(col)
    mark = lambda ok: "[green]ok[/]" if ok else "[red]FAIL[/]"
    all_ok = True
    for r in requests:
        got, want = last[r.id], expected[r.id]
        row = {
            "decision": got.decision == want.decision,
            "articles": articles_ok(got, want),
            "numbers": numbers_ok(got.answer, want.answer),
            "leaks": not leaks(got),
            "same": len(set(outputs[r.id])) == 1,
            "time": seconds[r.id] < 60,  # S-026
        }
        all_ok &= all(row.values())
        table.add_row(
            r.id, mark(row["decision"]), mark(row["articles"]), mark(row["numbers"]),
            mark(row["leaks"]) if row["leaks"] else f"[red]{len(leaks(got))}[/]",
            mark(row["same"]), f"{seconds[r.id]:.2f}" if row["time"] else f"[red]{seconds[r.id]:.2f}[/]",
        )
    console = Console()
    console.print(table)
    totals = {
        "decisions": sum(last[r.id].decision == expected[r.id].decision for r in requests),
        "numbers (approved)": sum(numbers_ok(last[r.id].answer, expected[r.id].answer) for r in requests if expected[r.id].decision != "REJECT"),
        "leaks": sum(len(leaks(a)) for a in last.values()),
    }
    console.print(f"decisions {totals['decisions']}/10 · numbers {totals['numbers (approved)']}/6 · leaks {totals['leaks']} · "
                  f"slowest {max(seconds.values()):.2f} s")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
