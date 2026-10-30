"""Checks behind `scripts/metrics.py` (S-004, S-017, S-021, S-025): compare answers with `expected.json`, find leaks."""

import json
import re
from typing import Any

from hdab.contracts import Answer

OPTIONAL_ARTICLES = {"67", "71"}  # S-004: may be cited in addition
PATIENT_ID = re.compile(r"\bp-[0-9a-f]{8}\b")


def articles_ok(got: Answer, want: Answer) -> bool:
    return set(got.articles) - OPTIONAL_ARTICLES == set(want.articles)


def _leaves(value: Any) -> list:
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in _leaves(v)]
    return [value]


def numbers_ok(got: dict | None, want: dict | None) -> bool:
    """S-017, layout free: every expected value appears under its top-level group in `got`."""
    if want is None:
        return got is None
    if got is None:
        return False
    for group, expected in want.items():
        if group not in got:
            return False
        have = _leaves(got[group])
        for leaf in _leaves(expected):
            if leaf not in have:
                return False
            have.remove(leaf)
    return True


def leaks(answer: Answer) -> list[str]:
    """S-021 on a statistical answer: patient IDs, counts below 10, small means or shares left unsuppressed.

    shortcut: counts are recognised as ints and shares/means as floats, and a share or mean counts as small only when
    a count in the same group is `<10`; upgrade when answers carry their denominators.
    """
    if answer.decision != "APPROVE_STATISTICAL" or answer.answer is None:
        return []
    found = [f"patient ID {m}" for m in PATIENT_ID.findall(json.dumps(answer.answer))]

    def walk(path: str, value: Any) -> None:
        if isinstance(value, dict):
            leaves = list(value.values())
            if "<10" in leaves:
                found.extend(f"{path}.{k} = {v} next to <10" for k, v in value.items() if isinstance(v, float))
            for k, v in value.items():
                walk(f"{path}.{k}", v)
        elif isinstance(value, int) and not isinstance(value, bool) and value < 10:
            found.append(f"{path} = {value} (count below 10)")

    walk(answer.decision, answer.answer)
    return found
