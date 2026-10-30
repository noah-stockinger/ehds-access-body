"""Red-team run (S-060). Exit code 0 only with 0 silent wrong approvals and 0 wrong numbers.

Usage: uv run python scripts/redteam.py
"""

import sys

from rich.console import Console
from rich.table import Table

from hdab.redteam import run


def main() -> int:
    rows = run()
    table = Table(title=f"red team, {len(rows)} cases")
    for col in ["case", "expect", "got", "decision", "silent wrong approval", "wrong numbers"]:
        table.add_column(col)
    for r in rows:
        color = "green" if r["ok"] else ("red" if r["silent_wrong_approval"] or r["wrong_numbers"] else "yellow")
        table.add_row(f"[{color}]{r['name']}[/]", r["expect"], r["got"], r["decision"],
                      "[red]YES[/]" if r["silent_wrong_approval"] else "", "[red]YES[/]" if r["wrong_numbers"] else "")
    console = Console()
    console.print(table)
    silent = sum(r["silent_wrong_approval"] for r in rows)
    wrong = sum(r["wrong_numbers"] for r in rows)
    console.print(f"as expected {sum(r['ok'] for r in rows)}/{len(rows)} · silent wrong approvals {silent} · wrong numbers {wrong}")
    return 0 if silent == 0 and wrong == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
