"""Plain-English names → code prefixes (S-007, S-058) and code/name mismatch notes (S-070).

A hand-built table only (S-053): resolving names from the data's own columns would tell applicants what the data holds.
A name with more than one fitting concept is ambiguous and never resolved silently.
"""

import re
from dataclasses import dataclass

from hdab import icd10
from hdab.data import load_tables

Kind = str  # "condition" | "medication" | "observation"


@dataclass(frozen=True)
class Concept:
    kind: Kind
    codes: tuple[str, ...]  # ICD-10 / ATC prefixes, or exact LOINC codes
    label: str


# One name → one or more concepts; more than one means ambiguous (S-058).
CURATED: dict[str, list[Concept]] = {
    "type 2 diabetes": [Concept("condition", ("E11",), "type 2 diabetes mellitus")],
    "type 1 diabetes": [Concept("condition", ("E10",), "type 1 diabetes mellitus")],
    "diabetes": [Concept("condition", ("E10",), "type 1 diabetes mellitus"),
                 Concept("condition", ("E11",), "type 2 diabetes mellitus")],
    "heart failure": [Concept("condition", ("I50",), "heart failure")],
    "atrial fibrillation": [Concept("condition", ("I48",), "atrial fibrillation and flutter")],
    "hypertension": [Concept("condition", ("I10",), "essential (primary) hypertension")],
    "high blood pressure": [Concept("condition", ("I10",), "essential (primary) hypertension")],
    "copd": [Concept("condition", ("J44",), "chronic obstructive pulmonary disease")],
    "chronic obstructive pulmonary disease": [Concept("condition", ("J44",), "chronic obstructive pulmonary disease")],
    "asthma": [Concept("condition", ("J45",), "asthma")],
    "depression": [Concept("condition", ("F32",), "depressive episode"),
                   Concept("condition", ("F33",), "recurrent depressive disorder")],
    "stroke": [Concept("condition", ("I63",), "cerebral infarction"),
               Concept("condition", ("I61",), "intracerebral haemorrhage")],
    "obesity": [Concept("condition", ("E66",), "obesity")],
    "breast cancer": [Concept("condition", ("C50",), "malignant neoplasm of breast")],
    "chronic kidney disease": [Concept("condition", ("N18",), "chronic kidney disease")],
    "ace inhibitor": [Concept("medication", ("C09AA",), "ACE inhibitors, plain")],
    "arb": [Concept("medication", ("C09CA",), "angiotensin II receptor blockers, plain")],
    "angiotensin receptor blocker": [Concept("medication", ("C09CA",), "angiotensin II receptor blockers, plain")],
    "sglt2 inhibitor": [Concept("medication", ("A10BK",), "SGLT2 inhibitors")],
    "oral anticoagulant": [Concept("medication", ("B01AA", "B01AF"), "vitamin K antagonists and direct factor Xa inhibitors")],
    "statin": [Concept("medication", ("C10AA",), "HMG CoA reductase inhibitors")],
    "insulin": [Concept("medication", ("A10A",), "insulins and analogues")],
    "glp-1 receptor agonist": [Concept("medication", ("A10BJ",), "GLP-1 analogues")],
    "beta blocker": [Concept("medication", ("C07",), "beta blocking agents")],
    "loop diuretic": [Concept("medication", ("C03C",), "high-ceiling diuretics")],
    "ssri": [Concept("medication", ("N06AB",), "selective serotonin reuptake inhibitors")],
    "antidepressant": [Concept("medication", ("N06A",), "antidepressants")],
    "hba1c": [Concept("observation", ("4548-4",), "HbA1c")],
    "bmi": [Concept("observation", ("39156-5",), "body mass index")],
    "body mass index": [Concept("observation", ("39156-5",), "body mass index")],
    "systolic blood pressure": [Concept("observation", ("8480-6",), "systolic blood pressure")],
    "egfr": [Concept("observation", ("62238-1",), "eGFR")],
    "kidney function": [Concept("observation", ("62238-1",), "eGFR")],
}

def _singular(name: str) -> str:
    return name[:-1] if name.endswith("s") and not name.endswith("ss") else name


def lookup(name: str) -> list[Concept]:
    """Candidate concepts for a plain-English name; empty if unknown, more than one if ambiguous."""
    name = " ".join(name.lower().split())
    return CURATED.get(name) or CURATED.get(_singular(name)) or []


def usual_code(name: str, kind: Kind, codes: tuple[str, ...]) -> str | None:
    """The hand-built table's code(s) for this name, if it knows the name and the given codes are none of them."""
    name = " ".join(name.lower().split())
    known = [c for c in CURATED.get(name) or CURATED.get(_singular(name)) or [] if c.kind == kind]
    usual = [u for c in known for u in c.codes]
    if not usual or any(p.startswith(u) or u.startswith(p) for p in codes for u in usual):
        return None
    return " or ".join(usual)


def for_applicant(note: str) -> str:
    """The mismatch note without what it says about the data, which only staff may see."""
    return re.sub(r" (?:In this data these codes occur: .*?\.|None of these codes occur in this data\.)(?= |$)", "", note)


def mismatch_note(name: str, prefixes: tuple[str, ...]) -> str | None:
    """S-070: a note when a definition's code covers more than its name; numbers still use the exact prefix."""
    for prefix in prefixes:
        also = icd10.also_covers(name, prefix)
        if not also:
            continue
        in_data = sorted({c for c in load_tables()["conditions"]["icd10"] if c in also})
        listed = ", ".join(f"{c} {d}" for c, d in also.items())
        found = (f"In this data these codes occur: {', '.join(in_data)}." if in_data
                 else "None of these codes occur in this data.")
        return (f'Definition mismatch: "{name}" is defined as ICD-10 prefix {prefix}, which also covers {listed}. '
                f"{found} The numbers use the exact prefix {prefix} (S-007).")
    return None
