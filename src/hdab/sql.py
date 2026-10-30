"""The query plan as SQL, for the audit log (S-038): staff can read what fetched the data.

The numbers come from `stats.Engine` (pandas). This SQL states the same query over the same tables, and `check` runs it
in DuckDB and compares the result with the numbers already computed, so the log says whether the two really agree.
Only codes from the parsed plan go into it, and it runs with no access to files or the network.
"""

import re

import duckdb

from hdab.data import load_tables
from hdab.plan import Measure, Mod, Plan, PSet, Term
from hdab.stats import REF_DATE, SMALL

TABLES = ("patients", "conditions", "medications", "observations", "encounters")


def _text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _name(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _comment(value: str) -> str:
    return "-- " + " ".join(value.split())  # one line: text from the request must not end the comment


def _starts(column: str, codes: tuple[str, ...]) -> str:
    return " OR ".join(f"{column} LIKE {_text(c + '%')}" for c in codes)


def _term(term: Term, active: bool = False) -> str:
    if term.kind == "condition":
        return f"EXISTS (SELECT 1 FROM conditions c WHERE c.patient_id = s.patient_id AND ({_starts('c.icd10', term.codes)}))"
    if term.kind == "medication":
        when = f" AND m.start_date <= '{REF_DATE}' AND (m.end_date = '' OR m.end_date >= '{REF_DATE}')" if active else ""
        return f"EXISTS (SELECT 1 FROM medications m WHERE m.patient_id = s.patient_id AND ({_starts('m.atc', term.codes)}){when})"
    if term.kind == "observation":
        return (f"EXISTS (SELECT 1 FROM observations o WHERE o.patient_id = s.patient_id "
                f"AND o.loinc IN ({', '.join(map(_text, term.codes))}))")
    if term.kind == "age":
        upper = f" AND s.age <= {term.max_age}" if term.max_age is not None else ""
        return f"s.age >= {term.min_age or 0}{upper}"
    if term.kind == "sex":
        return f"s.sex = {_text(term.sex)}"
    raise ValueError(f"no SQL for a {term.kind} term on patients")


def _mod(mod: Mod) -> str:
    condition = _term(mod.term, mod.active)
    return f"NOT {condition}" if mod.negated else condition


def _where(s: PSet, plan: Plan, extra: list[str] | None = None) -> str:
    parts = (extra or []) + [_term(t) for t in s.subject] + [_mod(m) for m in s.mods + plan.restrict]
    return "\n    AND ".join(parts) or "TRUE"


def _encounters(s: PSet, plan: Plan) -> str:
    conditions = []
    for term in s.subject:
        if term.enc_type:
            conditions.append(f"e.type = {_text(term.enc_type)}")
        if term.codes:
            conditions.append(f"({_starts('e.primary_icd10', term.codes)})")
    if plan.year:
        conditions.append(f"e.start_date LIKE {_text(plan.year + '%')}")
    keep = _where(PSet(s.text, [], s.mods), plan, conditions)  # the subject terms describe encounters, not patients
    return ("SELECT e.encounter_id, e.data_holder, s.region, s.sex, s.band\n  FROM encounters e "
            f"JOIN scope s ON s.patient_id = e.patient_id\n  WHERE {keep}")


def _scope(plan: Plan) -> str:
    bands = " ".join(f"WHEN age >= {lo}" + (f" AND age <= {hi}" if hi is not None else "") + f" THEN {_text(label)}"
                     for lo, hi, label in plan.bands)
    band = f"CASE {bands} END" if bands else "NULL"
    return ("-- Opted-out patients are removed before anything else (Art. 71). Age = 2025 - birth year.\n"
            f"scope AS (\n  SELECT patient_id, region, sex, data_holder, age, {band} AS band\n"
            "  FROM (SELECT *, 2025 - CAST(substr(birth_date, 1, 4) AS INTEGER) AS age FROM patients WHERE NOT opted_out)\n)")


def _counts_encounters(m: Measure) -> bool:
    return m.num is not None and m.num.unit == "encounters"  # stats.Engine.statistics: a plain count, whatever the kind


def _measure_set(i: int, m: Measure, plan: Plan) -> str:
    head = _comment(m.describe())
    if _counts_encounters(m):
        return f"{head}\nm{i} AS (\n  {_encounters(m.num, plan)}\n)"
    if m.kind == "count":
        return f"{head}\nm{i} AS (\n  SELECT s.* FROM scope s\n  WHERE {_where(m.num, plan)}\n)"
    if m.kind == "share":
        return (f"{head}\nm{i}_num AS (\n  SELECT s.* FROM scope s\n  WHERE {_where(m.num, plan)}\n),\n"
                f"m{i}_den AS (\n  SELECT s.* FROM scope s\n  WHERE {_where(m.den, plan)}\n)")
    codes = ", ".join(map(_text, m.obs.codes))
    return (f"{head}\nm{i}_latest AS (\n  SELECT patient_id, value FROM observations WHERE loinc IN ({codes})\n"
            "  QUALIFY row_number() OVER (PARTITION BY patient_id ORDER BY date DESC) = 1\n),\n"
            f"m{i} AS (\n  SELECT s.*, l.value FROM scope s JOIN m{i}_latest l ON l.patient_id = s.patient_id\n"
            f"  WHERE {_where(m.den, plan)}\n)")


def _grid(plan: Plan) -> str:
    parts = []
    for g in plan.groups:
        if g == "band":
            parts.append(f"(SELECT * FROM (VALUES {', '.join(f'({_text(b[2])})' for b in plan.bands)}) AS t(band))")
        else:
            parts.append(f"(SELECT DISTINCT {g} FROM patients)")  # S-047: also a group where every patient opted out
    return "-- Every group is reported, also empty ones.\ngrid AS (\n  SELECT * FROM " + (" CROSS JOIN ".join(parts) or "(SELECT 1 AS one)") + "\n)"


def _cell(plan: Plan) -> str:
    return " AND ".join(f"x.{g} = g.{g}" for g in plan.groups) or "TRUE"


def _count(column: str) -> str:
    return f"CASE WHEN {column} >= {SMALL} THEN CAST({column} AS VARCHAR) ELSE '<{SMALL}' END"


def statistics(plan: Plan) -> str:
    """One row per group, with the small-cell rules (S-014, S-015) and one decimal, halves up (S-016)."""
    sets, counts, columns = [], [], []
    for i, m in enumerate(plan.measures):
        sets.append(_measure_set(i, m, plan))
        name = _name(m.key)
        if _counts_encounters(m) or m.kind == "count":
            counts.append(f"(SELECT count(*) FROM m{i} x WHERE {_cell(plan)}) AS m{i}_n")
            columns.append(f"{_count(f'm{i}_n')} AS {name}")
        elif m.kind == "share":
            for side in ("num", "den"):
                counts.append(f"(SELECT count(*) FROM m{i}_{side} x WHERE {_cell(plan)}) AS m{i}_{side}")
            n, d = f"m{i}_num", f"m{i}_den"
            columns.append(f"CASE WHEN {n} < {SMALL} OR {d} < {SMALL} THEN 'suppressed' "
                           f"ELSE CAST((2000 * {n} + {d}) // (2 * {d}) / 10.0 AS VARCHAR) END AS {name}")
        else:
            counts.append(f"(SELECT count(*) FROM m{i} x WHERE {_cell(plan)}) AS m{i}_n")
            counts.append(f"(SELECT sum(CAST(CAST(x.value AS DECIMAL(18, 4)) * 10000 AS BIGINT)) FROM m{i} x "
                          f"WHERE {_cell(plan)}) AS m{i}_sum")
            columns.append(f"CASE WHEN m{i}_n < {SMALL} THEN 'suppressed' "
                           f"ELSE CAST((m{i}_sum + 500 * m{i}_n) // (1000 * m{i}_n) / 10.0 AS VARCHAR) END AS {name}")
    pick = ",\n  ".join(plan.groups + columns)
    counted = ",\n    ".join(["g.*"] + counts)
    order = f"\nORDER BY {', '.join(plan.groups)}" if plan.groups else ""
    return ("WITH " + ",\n".join([_scope(plan), *sets, _grid(plan)]) + f",\ncounts AS (\n  SELECT\n    {counted}\n  FROM grid g\n)\n"
            f"SELECT\n  {pick}\nFROM counts{order}")


def cohort(plan: Plan, exact: bool) -> str:
    size = "count(*)" if exact else _count("count(*)")
    return (f"WITH {_scope(plan)},\n{_comment('Cohort: ' + plan.cohort.describe())}\ncohort AS (\n  SELECT s.* FROM scope s\n"
            f"  WHERE {_where(plan.cohort, plan)}\n)\nSELECT {size} AS cohort_size FROM cohort")


def records(plan: Plan, types: dict[str, tuple[str, ...] | None]) -> str:
    """S-018: what is copied into the SPE, per table."""
    out = []
    for table, codes in types.items():
        only = f" AND t.loinc IN ({', '.join(map(_text, codes))})" if codes else ""
        out.append(f"-- Copied into the secure processing environment: {table}\nWITH {_scope(plan)},\ncohort AS (\n"
                   f"  SELECT s.patient_id FROM scope s\n  WHERE {_where(plan.cohort, plan)}\n)\n"
                   f"SELECT t.* FROM {table} t\nWHERE t.patient_id IN (SELECT patient_id FROM cohort){only}")
    return ";\n\n".join(out)


def _nested(rows: list[tuple], columns: list[str], groups: list[str]) -> dict:
    out: dict = {}
    for row in rows:
        values = dict(zip(columns, row))
        cell = [values.pop(g) for g in groups]
        node = out
        for v in cell[:-1]:
            node = node.setdefault(v, {})
        if cell:
            node[cell[-1]] = values
        else:
            out = values
    return out


def _same(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return str(a) == str(b)


def check(plan: Plan, numbers: dict, spe_types: dict[str, tuple[str, ...] | None] | None = None) -> tuple[str | None, bool]:
    """The SQL for these numbers, and whether running it gives exactly them. Never blocks a decision (S-038 is a record)."""
    exact = spe_types is not None
    try:
        query = cohort(plan, exact) if plan.cohort_size else statistics(plan)
        with duckdb.connect(config={"enable_external_access": "false"}) as con:
            tables = load_tables()
            for table in TABLES:
                con.register(table, tables[table])
            result = con.execute(query)
            columns = [d[0] for d in result.description]
            found = _nested(result.fetchall(), columns, [] if plan.cohort_size else plan.groups)
        text = f"{query};\n\n{records(plan, spe_types)}" if exact and plan.cohort else query
        return text, _same(found, numbers)
    except (ValueError, duckdb.Error) as e:
        return _comment(f"No SQL could be stated for this plan: {re.sub(r'[^ -~]', ' ', str(e))[:200]}"), False
