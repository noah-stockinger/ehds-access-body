"""Query plan → small-cell-safe statistics (S-008 to S-016, S-021) or the exact SPE cohort (S-019)."""

from decimal import ROUND_HALF_UP, Decimal
from itertools import product

import pandas as pd

from hdab.data import load_tables
from hdab.plan import Mod, Plan, PSet, Term

REF_DATE = "2025-12-31"  # S-009, S-010
SMALL = 10


def round1(value: Decimal) -> float:
    """S-016: one decimal, halves up (0.25 → 0.3), never banker's rounding."""
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def count_cell(n: int) -> int | str:
    return n if n >= SMALL else "<10"  # S-014, also for 0


class Engine:
    def __init__(self, plan: Plan):
        self.plan = plan
        t = load_tables()
        self.t = t
        self.all_patients = t["patients"]
        p = t["patients"][~t["patients"]["opted_out"]].set_index("patient_id")  # S-008: before anything else
        p = p.assign(age=2025 - p["birth_date"].str[:4].astype(int))  # S-009
        p = p.assign(band=p["age"].map(self.band_of))
        self.p = p

    def band_of(self, age: int) -> str | None:
        for lo, hi, label in self.plan.bands:
            if age >= lo and (hi is None or age <= hi):
                return label
        return None

    # ---- patient sets ----------------------------------------------------------------------------------------
    def has(self, table: str, code_col: str, codes: tuple[str, ...], active: bool = False) -> pd.Series:
        rows = self.t[table]
        rows = rows[rows[code_col].str.startswith(codes)] if table != "observations" else rows[rows["loinc"].isin(codes)]
        if active:  # S-010
            rows = rows[(rows["start_date"] <= REF_DATE) & ((rows["end_date"] == "") | (rows["end_date"] >= REF_DATE))]
        return pd.Series(self.p.index.isin(rows["patient_id"]), index=self.p.index)

    def term_mask(self, term: Term, active: bool = False) -> pd.Series:
        if term.kind == "condition":
            return self.has("conditions", "icd10", term.codes)  # S-011: a diagnosis is a row in conditions.csv
        if term.kind == "medication":
            return self.has("medications", "atc", term.codes, active)
        if term.kind == "observation":
            return self.has("observations", "loinc", term.codes)
        if term.kind == "age":
            m = self.p["age"] >= (term.min_age or 0)
            return m & (self.p["age"] <= term.max_age) if term.max_age is not None else m
        if term.kind == "sex":
            return self.p["sex"] == term.sex
        raise ValueError(f"cannot evaluate a {term.kind} term on patients")

    def mod_mask(self, mod: Mod) -> pd.Series:
        m = self.term_mask(mod.term, mod.active)
        return ~m if mod.negated else m

    def patients(self, s: PSet) -> pd.Series:
        m = pd.Series(True, index=self.p.index)
        for term in s.subject:
            m &= self.term_mask(term)
        for mod in s.mods + self.plan.restrict:
            m &= self.mod_mask(mod)
        return m

    def encounters(self, s: PSet) -> pd.DataFrame:
        e = self.t["encounters"].merge(self.p[["region", "sex", "band"]], left_on="patient_id", right_index=True)
        for term in s.subject:
            if term.enc_type:
                e = e[e["type"] == term.enc_type]
            if term.codes:
                e = e[e["primary_icd10"].str.startswith(term.codes)]
        if self.plan.year:
            e = e[e["start_date"].str.startswith(self.plan.year)]
        keep = pd.Series(True, index=self.p.index)
        for mod in s.mods + self.plan.restrict:
            keep &= self.mod_mask(mod)
        return e[e["patient_id"].isin(self.p.index[keep])]

    def latest(self, term: Term) -> pd.Series:
        """S-012: the value with the latest date per patient."""
        o = self.t["observations"]
        o = o[o["loinc"].isin(term.codes)].sort_values(["patient_id", "date"])
        return o.groupby("patient_id")["value"].last()

    # ---- grouping --------------------------------------------------------------------------------------------
    def group_values(self, group: str) -> list[str]:
        if group == "band":
            return [b[2] for b in self.plan.bands]
        return sorted(self.all_patients[group].unique())  # S-047: every value present in patients.csv

    def cells(self) -> list[tuple[str, ...]]:
        return list(product(*(self.group_values(g) for g in self.plan.groups)))

    def statistics(self) -> dict:
        prepared = []
        for m in self.plan.measures:
            if m.num is not None and m.num.unit == "encounters":
                prepared.append((m, self.encounters(m.num), None))
            else:
                num = self.patients(m.num) if m.num is not None else None
                den = self.patients(m.den) if m.den is not None else None
                if m.kind == "mean":
                    den = den & self.term_mask(m.obs)
                prepared.append((m, num, den))
        latest = {id(m): self.latest(m.obs) for m in self.plan.measures if m.kind == "mean"}

        out: dict = {}
        for cell in self.cells():
            in_cell = pd.Series(True, index=self.p.index)
            for g, v in zip(self.plan.groups, cell):
                in_cell &= self.p[g] == v
            values = {}
            for m, num, den in prepared:
                if isinstance(num, pd.DataFrame):
                    rows = num
                    for g, v in zip(self.plan.groups, cell):
                        rows = rows[rows[g] == v]
                    values[m.key] = count_cell(len(rows))
                elif m.kind == "count":
                    values[m.key] = count_cell(int((num & in_cell).sum()))
                elif m.kind == "share":
                    n, d = int((num & in_cell).sum()), int((den & in_cell).sum())
                    values[m.key] = "suppressed" if n < SMALL or d < SMALL else round1(Decimal(n) * 100 / Decimal(d))  # S-015
                else:
                    ids = self.p.index[den & in_cell]
                    vals = [Decimal(v) for v in latest[id(m)].reindex(ids).dropna()]
                    values[m.key] = "suppressed" if len(vals) < SMALL else round1(sum(vals) / len(vals))
            node = out
            for v in cell[:-1]:
                node = node.setdefault(v, {})
            if cell:
                node[cell[-1]] = values
            else:
                out = values
        return out

    def cell_sets(self) -> dict[str, set[str]]:
        """Patient IDs behind every patient count, per cell; kept inside the app for the overlap check (S-051)."""
        out = {}
        for m in self.plan.measures:
            if m.kind != "count" or m.num.unit != "patients":
                continue
            mask = self.patients(m.num)
            for cell in self.cells():
                in_cell = mask.copy()
                for g, v in zip(self.plan.groups, cell):
                    in_cell &= self.p[g] == v
                out["/".join([*cell, m.key])] = set(self.p.index[in_cell])
        return out

    def cohort(self) -> pd.Index:
        return self.p.index[self.patients(self.plan.cohort)]


def execute(plan: Plan, spe: bool = False) -> dict:
    engine = Engine(plan)
    if plan.cohort_size:
        n = len(engine.cohort())
        return {"cohort_size": n if spe else count_cell(n)}  # S-019: exact only for the SPE
    return engine.statistics()
