"""Write the generated test dataset to data/generated/ (same 5 CSVs as data/track3/data/, IDs start with `g-`).

Every patient belongs to a hand-built scenario, so tests/test_generated.py knows each expected number in advance.
Not challenge data: never used by the app unless $TRACK3_DATA points here. Deterministic, no randomness.
Usage: uv run python scripts/make_testdata.py
"""

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "generated" / "data"
REGIONS = ["Burgenland", "Kärnten", "Niederösterreich", "Oberösterreich", "Salzburg", "Steiermark", "Tirol",
           "Vorarlberg", "Wien"]
HOLDERS = ["Klinikum Nord", "Klinikum Süd", "Klinikum West"]

rows = {name: [] for name in ["patients", "conditions", "medications", "observations", "encounters"]}
counter = {"p": 0, "e": 0}


def patient(region, birth_year, sex="female", opted_out=False, holder=None):
    counter["p"] += 1
    pid = f"g-{counter['p']:05d}"
    rows["patients"].append([pid, sex, f"{birth_year}-06-15", region, holder or HOLDERS[counter["p"] % 3],
                             "true" if opted_out else "false"])
    return pid


def condition(pid, icd10, description, onset="2020-01-01"):
    rows["conditions"].append([pid, icd10, description, onset])


def medication(pid, atc, name, start="2024-01-01", end=""):
    rows["medications"].append([pid, atc, name, start, end])


def observation(pid, loinc, name, value, unit, date):
    rows["observations"].append([pid, loinc, name, value, unit, date])


def encounter(pid, holder, type_, start, primary=""):
    counter["e"] += 1
    rows["encounters"].append([f"g-e{counter['e']:05d}", pid, holder, type_, start, start, primary])


T2D = ("E11.9", "Type 2 diabetes mellitus without complications")
HBA1C = ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%")
BMI = ("39156-5", "Body mass index (BMI)", "kg/m2")

# Filler: 20 adults per region without any condition (born 1980, age 45), half female.
filler = {r: [patient(r, 1980, "female" if i % 2 else "male") for i in range(20)] for r in REGIONS}

# A · small cells by region, opt-outs, age boundary (type 2 diabetes, adults).
for _ in range(10):  # Burgenland: exactly 10 → shown as 10
    pid = patient("Burgenland", 1970)
    condition(pid, *T2D)
    observation(pid, *HBA1C[:2], "7.0", HBA1C[2], "2025-03-01")
    medication(pid, "A10BA02", "Metformin")
for _ in range(9):  # Kärnten: 9 → "<10"
    condition(patient("Kärnten", 1970), *T2D)
for i in range(12):  # Wien: 12, each with two HbA1c values (latest counts)
    pid = patient("Wien", 1970)
    condition(pid, *T2D)
    observation(pid, *HBA1C[:2], "9.0", HBA1C[2], "2024-01-01")
    observation(pid, *HBA1C[:2], "6.5", HBA1C[2], "2025-06-01")
    observation(pid, *BMI[:2], "30.0", BMI[2], "2025-06-01")  # must not enter the SPE
for _ in range(3):  # Wien: 3 opted out → excluded everywhere
    pid = patient("Wien", 1970, opted_out=True)
    condition(pid, *T2D)
    observation(pid, *HBA1C[:2], "8.0", HBA1C[2], "2025-01-01")
for _ in range(9):  # Tirol: 9 adults born 1970 + 1 aged exactly 18 = 10; 1 aged 17 not an adult
    condition(patient("Tirol", 1970), *T2D)
condition(patient("Tirol", 2007), *T2D)
condition(patient("Tirol", 2008), *T2D)

# B · Oberösterreich hypertension: band edges, active-medication edges, rounding halves up.
ACE = ("C09AA05", "Ramipril")
ARB = ("C09CA06", "Candesartan")
for i in range(40):  # aged 64 → band 50-64; ACE: 10 end on ref date, 10 end the day before, 10 start after, 10 open
    pid = patient("Oberösterreich", 1961)
    condition(pid, "I10", "Essential (primary) hypertension")
    medication(pid, *ACE, *[("2024-01-01", "2025-12-31"), ("2024-01-01", "2025-12-30"),
                            ("2026-01-01", ""), ("2024-01-01", "")][i // 10])
for i in range(80):  # aged 65 → band 65+; 13 on an ARB → 13/80 = 16.25 % → 16.3
    pid = patient("Oberösterreich", 1960)
    condition(pid, "I10", "Essential (primary) hypertension")
    if i < 13:
        medication(pid, *ARB)
for _ in range(12):  # aged 49 → band 18-49, no ACE inhibitor
    condition(patient("Oberösterreich", 1976), "I10", "Essential (primary) hypertension")

# C · Salzburg breast cancer: latest BMI per patient and a mean that ends in 5 (26.25 → 26.3).
for i in range(10):
    pid = patient("Salzburg", 1970, "female")
    condition(pid, "C50.9", "Malignant neoplasm of breast, unspecified")
    observation(pid, *BMI[:2], "40.0", BMI[2], "2023-01-01")  # older value, must be ignored
    observation(pid, *BMI[:2], "28.5" if i == 0 else "26.0", BMI[2], "2025-01-01")
condition(patient("Salzburg", 1970, "female"), "C50.9", "Malignant neoplasm of breast, unspecified")  # no BMI: left out
pid = patient("Salzburg", 1970, "male")  # man: not a woman
condition(pid, "C50.9", "Malignant neoplasm of breast, unspecified")
observation(pid, *BMI[:2], "25.0", BMI[2], "2025-01-01")
for _ in range(9):  # Steiermark: 9 women with BMI → "<10", mean suppressed
    pid = patient("Steiermark", 1970, "female")
    condition(pid, "C50.9", "Malignant neoplasm of breast, unspecified")
    observation(pid, *BMI[:2], "30.0", BMI[2], "2025-01-01")

# D · Niederösterreich atrial fibrillation with flutter codes (S-070), aged 70 → band 65-74.
for _ in range(10):
    condition(patient("Niederösterreich", 1955), "I48.0", "Paroxysmal atrial fibrillation")
for _ in range(2):
    condition(patient("Niederösterreich", 1955), "I48.3", "Typical atrial flutter")

# E · encounters: year boundary, type, opt-outs, primary diagnosis not in conditions.
for pid in filler["Vorarlberg"][:10]:
    encounter(pid, "Klinikum West", "inpatient", "2025-01-01", "J18.9")
encounter(filler["Vorarlberg"][10], "Klinikum West", "inpatient", "2024-12-31", "J18.9")  # 2024: not counted
for pid in filler["Vorarlberg"][11:16]:
    encounter(pid, "Klinikum West", "outpatient", "2025-05-01")  # not inpatient
encounter(patient("Vorarlberg", 1980, opted_out=True), "Klinikum West", "inpatient", "2025-02-01", "J18.9")
for pid in filler["Kärnten"][:10]:
    encounter(pid, "Klinikum Nord", "inpatient", "2025-07-01", "I50.9")  # heart failure, only in encounters

HEADERS = {
    "patients": ["patient_id", "sex", "birth_date", "region", "data_holder", "opted_out"],
    "conditions": ["patient_id", "icd10", "description", "onset_date"],
    "medications": ["patient_id", "atc", "name", "start_date", "end_date"],
    "observations": ["patient_id", "loinc", "name", "value", "unit", "date"],
    "encounters": ["encounter_id", "patient_id", "data_holder", "type", "start_date", "end_date", "primary_icd10"],
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, header in HEADERS.items():
        with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows[name])
    print({name: len(r) for name, r in rows.items()})
