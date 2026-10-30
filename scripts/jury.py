"""Jury simulation: `uv run python scripts/jury.py` (rules only unless KEV_MODE is set). Exit 1 on any silent wrong
approval, wrong number or leak."""

import sys

from rich.console import Console
from rich.table import Table

from hdab.jury import run


def main() -> None:
    rows = run()
    t = Table(title="Jury simulation")
    for col in ["kind", "id", "case", "expect", "got", "decision", "problem"]:
        t.add_column(col, overflow="fold")
    for r in rows:
        problem = ("SILENT WRONG APPROVAL" if r["silent_wrong_approval"] else "wrong numbers" if r["wrong_numbers"]
                   else "wrong decision" if r["wrong_decision"] else "LEAK" if r["leaks"] else "" if r["ok"]
                   else (r["why"][0][:90] if r["why"] else "not as expected"))
        t.add_row(r["kind"], r["id"], r["name"], r["expect"], r["got"], r["decision"] or "–", problem,
                  style=None if r["ok"] else "red" if r["silent_wrong_approval"] or r["wrong_numbers"] else "yellow")
    Console(width=180).print(t)
    by = {}
    for r in rows:
        by.setdefault(r["kind"], []).append(r["ok"] and not r["wrong_numbers"] and not r["wrong_decision"])
    bad = sum(r["silent_wrong_approval"] or r["wrong_numbers"] or bool(r["leaks"]) for r in rows)
    print(" · ".join(f"{k} {sum(v)}/{len(v)}" for k, v in by.items()),
          f"· silent wrong approvals {sum(r['silent_wrong_approval'] for r in rows)}",
          f"· wrong numbers {sum(r['wrong_numbers'] for r in rows)} · leaks {sum(bool(r['leaks']) for r in rows)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
