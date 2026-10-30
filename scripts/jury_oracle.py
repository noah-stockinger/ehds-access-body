"""Independent expected numbers for the `approve` cases of tests/jury/cases.json, written by hand per case with plain
pandas; it imports nothing from `hdab`, so a bug in the app's parser or engine cannot hide here.
Writes tests/jury/expected.json: id → decision and {group: {measure: value}} (counts, shares, means as the app would
report them, small cells as "<10" / "suppressed"). Usage: uv run python scripts/jury_oracle.py
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "track3" / "data"
OUT = ROOT / "tests" / "jury" / "expected.json"
read = lambda n: pd.read_csv(D / f"{n}.csv", dtype=str, keep_default_na=False, encoding="utf-8")
P, C, M, O, E = (read(n) for n in ["patients", "conditions", "medications", "observations", "encounters"])
P = P[P["opted_out"].str.lower() != "true"].copy()  # opt-outs out of everything
P["age"] = 2025 - P["birth_date"].str[:4].astype(int)
REGIONS = sorted(read("patients")["region"].unique())
HOSPITALS = sorted(read("patients")["data_holder"].unique())
SEXES = sorted(read("patients")["sex"].unique())


def cnt(n):
    return n if n >= 10 else "<10"


def pct(n, d):
    return "suppressed" if n < 10 or d < 10 else float((Decimal(n) * 100 / Decimal(d)).quantize(Decimal("0.1"), ROUND_HALF_UP))


def mean(values):
    v = [Decimal(x) for x in values]
    return "suppressed" if len(v) < 10 else float((sum(v) / len(v)).quantize(Decimal("0.1"), ROUND_HALF_UP))


def has_cond(*prefixes):
    return set(C[C["icd10"].str.startswith(prefixes)]["patient_id"])


def active_med(*prefixes):
    m = M[M["atc"].str.startswith(prefixes)]
    m = m[(m["start_date"] <= "2025-12-31") & ((m["end_date"] == "") | (m["end_date"] >= "2025-12-31"))]
    return set(m["patient_id"])


def latest(loinc):
    o = O[O["loinc"] == loinc].sort_values(["patient_id", "date"])
    return o.groupby("patient_id")["value"].last()


def stays(etype, year, prefix=None):
    e = E[(E["type"] == etype) & E["start_date"].str.startswith(year) & E["patient_id"].isin(P["patient_id"])]
    if prefix:
        e = e[e["primary_icd10"].str.startswith(prefix)]
    return e.merge(P[["patient_id", "region"]], on="patient_id")


adults = P[P["age"] >= 18]
t2d = has_cond("E11")
r01_like = {r: {"adults": cnt(len(a := adults[adults["region"] == r])),
                "adults_with_type_2_diabetes": cnt(int(a["patient_id"].isin(t2d).sum()))} for r in REGIONS}

out = {}
e = stays("inpatient", "2025", "I50")
out["J01"] = {h: {"heart_failure_stays": cnt(int((e["data_holder"] == h).sum()))} for h in HOSPITALS}
copd = has_cond("J44")
out["J02"] = {}
for h in HOSPITALS:
    a = adults[adults["data_holder"] == h]
    n = int(a["patient_id"].isin(copd).sum())
    out["J02"][h] = {"adults": cnt(len(a)), "adults_with_copd": cnt(n), "prevalence_pct": pct(n, len(a))}
sbp, htn = latest("8480-6"), has_cond("I10")
out["J03"] = {}
for s in SEXES:
    a = adults[(adults["sex"] == s) & adults["patient_id"].isin(htn) & adults["patient_id"].isin(sbp.index)]
    out["J03"][s] = {"n": cnt(len(a)), "mean": mean(sbp[a["patient_id"]])}
hf, sglt2 = has_cond("I50"), active_med("A10BK")
out["J04"] = {}
for r in REGIONS:
    a = P[(P["region"] == r) & P["patient_id"].isin(hf)]
    n = int(a["patient_id"].isin(sglt2).sum())
    out["J04"][r] = {"n": cnt(len(a)), "with": cnt(n), "share": pct(n, len(a))}
egfr, ckd = latest("62238-1"), has_cond("N18")
out["J05"] = {}
for label, lo, hi in [("18-64", 18, 64), ("65+", 65, 999)]:
    a = P[(P["age"] >= lo) & (P["age"] <= hi) & P["patient_id"].isin(ckd) & P["patient_id"].isin(egfr.index)]
    out["J05"][label] = {"n": cnt(len(a)), "mean": mean(egfr[a["patient_id"]])}
e = stays("emergency", "2024")
out["J06"] = {h: {"emergency_visits": cnt(int((e["data_holder"] == h).sum()))} for h in HOSPITALS}
e = stays("inpatient", "2025", "J18")
out["J07"] = {r: {"pneumonia_stays": cnt(int((e["region"] == r).sum()))} for r in REGIONS}
asthma = has_cond("J45")
out["J08"] = {r: {"children_with_asthma": cnt(int(((P["region"] == r) & (P["age"] < 18) & P["patient_id"].isin(asthma)).sum()))}
              for r in REGIONS}
out["J09"] = {"cohort_size": int((adults["patient_id"].isin(hf) & adults["patient_id"].isin(set(O[O["loinc"] == "62238-1"]["patient_id"]))).sum())}
statin = active_med("C10AA")
out["J10"] = {}
for h in HOSPITALS:
    a = adults[(adults["data_holder"] == h) & adults["patient_id"].isin(t2d)]
    n = int(a["patient_id"].isin(statin).sum())
    out["J10"][h] = {"n": cnt(len(a)), "share": pct(n, len(a))}
ob = has_cond("E66")
out["J11"] = {r: {s: {"patients_with_obesity": cnt(int(((P["region"] == r) & (P["sex"] == s) & P["patient_id"].isin(ob)).sum()))}
                  for s in SEXES} for r in REGIONS}
for w in ["W01", "W02", "W03", "W04", "W05", "W06", "W07", "W09", "W12", "W13", "W14", "W17"]:
    out[w] = r01_like
work = P[(P["age"] >= 18) & (P["age"] <= 64)]
out["W15"] = {h: {"working_age": cnt(len(a := work[work["data_holder"] == h])),
                  "with_htn": cnt(int(a["patient_id"].isin(htn).sum()))} for h in HOSPITALS}
no_ckd = adults[~adults["patient_id"].isin(ckd)]
out["W16"] = {r: {"adults_with_type_2_diabetes": cnt(int(((no_ckd["region"] == r) & no_ckd["patient_id"].isin(t2d)).sum()))}
              for r in REGIONS}
hd = has_cond("I50", "I48")
out["W08"] = {h: {"patients_with_heart_disease": cnt(int(((P["data_holder"] == h) & P["patient_id"].isin(hd)).sum()))}
              for h in HOSPITALS}

if __name__ == "__main__":
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} expected answers → {OUT}")
