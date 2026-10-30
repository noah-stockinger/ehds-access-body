"""Does the request make sense? Checks on a parsed plan that would otherwise give a clean but meaningless answer
(tests/jury `error` cases): contradictory ranges, codes or years the data does not have, empty populations, a format
that contradicts the request type, a question about something no definition covers.

Each finding is a review reason starting with "Sanity:"; the pipeline then withholds the numbers (S-046, S-071).
Only aggregate counts are computed here; nothing leaves the app.
"""

import re
from itertools import pairwise

from hdab import vocab
from hdab.contracts import Request
from hdab.data import load_tables
from hdab.plan import Plan, PSet
from hdab.stats import Engine

TABLE = {"condition": ("conditions", "icd10"), "medication": ("medications", "atc"), "observation": ("observations", "loinc")}


def _in_data(kind: str, codes: tuple[str, ...]) -> bool:
    table, col = TABLE[kind]
    values = load_tables()[table][col]
    return bool(values.isin(codes).any() if kind == "observation" else values.str.startswith(codes).any())


def _ranges(plan: Plan) -> list[str]:
    out = [f'"{t.name}" is an age range from {t.min_age} to {t.max_age}, which contains nobody'
           for t in plan.terms.values() if t.kind == "age" and t.max_age is not None and t.min_age > t.max_age]
    bands = sorted(plan.bands, key=lambda b: b[0])
    out += [f"age band {label} ends before it starts" for lo, hi, label in bands if hi is not None and lo > hi]
    ages = [t for t in plan.terms.values() if t.kind == "age" and t.used]
    for t in ages:  # "Adult = 18 or older" reported in bands 0-9, 10-17: no adult can be in any band
        hi = t.max_age if t.max_age is not None else 999
        if bands and not any(lo <= hi and (bhi is None or bhi >= (t.min_age or 0)) for lo, bhi, _ in bands):
            out.append(f'"{t.name}" ({t.describe()}) falls into none of the age bands ' + ", ".join(b[2] for b in bands))
    for (lo1, hi1, a), (lo2, _, b) in pairwise(bands):
        if hi1 is None or lo2 <= hi1:
            out.append(f"age bands {a} and {b} overlap, so a patient could be counted in either")
    return out


def _positive(plan: Plan) -> set[int]:
    """Terms that select patients ("with X"); a code missing from the data only matters for these, since
    "without X" is then simply everyone."""
    sets = [p for m in plan.measures for p in (m.num, m.den) if p is not None] + ([plan.cohort] if plan.cohort else [])
    ids = {id(t) for s in sets for t in s.subject} | {id(m.term) for s in sets for m in s.mods if not m.negated}
    return ids | {id(m.term) for m in plan.restrict if not m.negated} | {id(m.obs) for m in plan.measures if m.obs}


def _codes(plan: Plan) -> list[str]:
    out = []
    positive = _positive(plan)
    for t in plan.terms.values():
        if id(t) not in positive:
            continue
        if t.kind in TABLE and t.codes and not _in_data(t.kind, t.codes):
            out.append(f'"{t.name}" ({t.kind} code {" or ".join(t.codes)}) occurs nowhere in the data')
        if t.kind == "encounter" and t.codes and not load_tables()["encounters"]["primary_icd10"].str.startswith(t.codes).any():
            out.append(f'"{t.name}" (main diagnosis {" or ".join(t.codes)}) occurs nowhere in the data')
    years = set(load_tables()["encounters"]["start_date"].str[:4])
    if plan.year and plan.year not in years:
        out.append(f"the data has encounters from {min(years)} to {max(years)}, none in {plan.year}")
    return out


def _empty(plan: Plan, spe: bool) -> list[str]:
    """A population with nobody in it, or groups that cover none of it, gives a table of `<10` that means nothing."""
    engine = Engine(plan)
    out = []
    if plan.cohort is not None and (spe or plan.cohort_size) and len(engine.cohort()) == 0:
        out.append(f"the cohort ({plan.cohort.describe()}) contains no patient")
    seen: set[str] = set()
    for m in plan.measures:
        base: PSet | None = m.den if m.kind in {"share", "mean"} else m.num
        if base is None or base.describe() in seen:
            continue
        seen.add(base.describe())
        if base.unit == "encounters":
            if len(engine.encounters(base)) == 0:
                out.append(f"no encounter matches {base.describe()}")
            continue
        mask = engine.patients(base)
        if m.kind == "mean":
            mask &= engine.term_mask(m.obs)
        if not mask.any():
            out.append(f"no patient matches {base.describe()}" + (f" with a {m.obs.name} value" if m.kind == "mean" else ""))
    return out


def _format(request: Request) -> list[str]:
    if request.requested_as == "health data request" and re.search(r"pseudonym|record|row|individual", request.requested_format, re.IGNORECASE):
        return [(f"a health data request is answered with anonymised statistics only, but the requested format is "
                 f'"{request.requested_format}"; the applicant may have meant an access application')]
    return []


def _question(request: Request, plan: Plan) -> list[str]:
    """The question names a condition, drug or measurement that no definition covers (asked BMI, computed HbA1c)."""
    q = request.question.lower()
    planned = {c for t in plan.terms.values() for c in t.codes}
    hits = [k for k in vocab.CURATED if re.search(rf"\b{re.escape(k)}s?\b", q)]
    hits = [k for k in hits if not any(k != o and k in o for o in hits)]  # "diabetes" inside "type 2 diabetes"
    out = []
    for k in hits:
        codes = {c for concept in vocab.CURATED[k] for c in concept.codes}
        if not any(p.startswith(c) or c.startswith(p) for p in planned for c in codes):
            out.append(f'the question asks about "{k}", but no definition covers it; the numbers would answer a '
                       "different question")
    return out


def check(request: Request, plan: Plan, spe: bool) -> list[str]:
    found = _format(request) + _ranges(plan) + _codes(plan) + _question(request, plan)
    if not plan.problems:  # only a fully understood plan can be evaluated
        found += _empty(plan, spe)
    return [f"Sanity: {f}" for f in found]
