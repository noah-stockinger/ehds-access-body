"""Writes tests/jury/cases.json: requests the jury could send, with the expected outcome written down before any run.

Three kinds: `new` (well-formed, unlike R01–R10: per hospital, primary diagnosis, plain-English names, other years),
`wildcard` (same meaning, messy form) and `error` (a request that makes no sense or is broken; it must never be
approved cleanly). `expect`: approve | reject | review | invalid (refused with 422). Numbers for `approve` cases come
from scripts/jury_oracle.py, which does not use the app's code.
Usage: uv run python scripts/make_jury_cases.py
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "jury" / "cases.json"
ADULT = "Adult = aged 18 or older on 31 December 2025."
T2D = "Type 2 diabetes = any condition with an ICD-10 code starting with E11."
RESEARCH = {"name": "Dr. Sophie Lang", "organisation": "Medical University of Graz, Institute of Epidemiology", "country": "AT"}


def req(i, purpose, question, definitions, as_="health data request", fmt=None, applicant=RESEARCH, **extra):
    fmt = fmt or ("anonymised statistics" if as_ == "health data request" else "pseudonymised records")
    return {"id": i, "submitted": "2026-10-30T10:00:00+01:00", "applicant": applicant, "requested_as": as_,
            "requested_format": fmt, "purpose": purpose, "question": question, "definitions": definitions, **extra}


def case(name, kind, expect, request, decision=None, note=""):
    c = {"name": name, "kind": kind, "expect": expect, "request": request}
    if decision:
        c["decision"] = decision
    if note:
        c["note"] = note
    return c


CASES = [
    # ---- new: well-formed requests unlike R01–R10 ------------------------------------------------------------------
    case("heart failure stays by main diagnosis per hospital", "new", "approve", req(
        "J01", "We study hospital use for heart failure to improve discharge planning.",
        "How many inpatient stays in 2025 had heart failure as the main diagnosis, per hospital?",
        ["Heart failure stay = encounter with type 'inpatient', whose primary_icd10 starts with I50.",
         "Count stays (not patients) whose start_date is in 2025.", "Report per data_holder: heart failure stays."]),
        "APPROVE_STATISTICAL"),
    case("COPD prevalence per hospital", "new", "approve", req(
        "J02", "Research on chronic lung disease to plan prevention programmes.",
        "What share of adults has COPD, per hospital?",
        [ADULT, "COPD = any condition with an ICD-10 code starting with J44.",
         "Prevalence = adults with COPD / adults × 100, one decimal.",
         "Report per hospital: adults, adults with COPD and the prevalence."]), "APPROVE_STATISTICAL"),
    case("mean systolic blood pressure by sex", "new", "approve", req(
        "J03", "Research on blood pressure control in hypertension, to improve care.",
        "What is the mean systolic blood pressure of adults with hypertension, by sex?",
        [ADULT, "Hypertension = any condition with an ICD-10 code starting with I10.",
         "Use the latest systolic blood pressure (LOINC 8480-6) per patient.",
         ("Report per sex: adults with hypertension who have a systolic blood pressure value and their mean systolic "
          "blood pressure, one decimal.")]), "APPROVE_STATISTICAL"),
    case("plain-English names, no codes", "new", "approve", req(
        "J04", "Research on how new guideline treatments reach patients with heart failure.",
        "How many patients with heart failure have an active SGLT2 inhibitor, per region?",
        [("Report per region: patients with heart failure, how many of them have an active SGLT2 inhibitor and that "
          "share in %, one decimal.")]), "APPROVE_STATISTICAL", "codes inferred: I50, A10BK"),
    case("mean eGFR in chronic kidney disease by age band", "new", "approve", req(
        "J05", "Research on kidney function decline in chronic kidney disease.",
        "What is the mean eGFR of adults with chronic kidney disease, by age band?",
        [ADULT, "Chronic kidney disease = any condition with an ICD-10 code starting with N18.",
         "Age bands on 31 December 2025: 18-64, 65+.", "Use the latest eGFR (LOINC 62238-1) per patient.",
         "Report per band: adults with chronic kidney disease who have an eGFR value and their mean eGFR, one decimal."]),
        "APPROVE_STATISTICAL"),
    case("emergency visits in 2024 per hospital", "new", "approve", req(
        "J06", "Policy-making: planning emergency department capacity.",
        "How many emergency visits started in 2024, per hospital?",
        ["Emergency visit = encounter with type 'emergency'.", "Count visits (not patients) whose start_date is in 2024.",
         "Report per data_holder: emergency visits."]), "APPROVE_STATISTICAL"),
    case("pneumonia stays per region (code only in encounters)", "new", "approve", req(
        "J07", "Public health surveillance of pneumonia admissions.",
        "How many inpatient stays in 2025 had pneumonia as the main diagnosis, per region?",
        ["Pneumonia stay = encounter with type 'inpatient', whose primary_icd10 starts with J18.",
         "Count stays (not patients) whose start_date is in 2025.", "Report per region: pneumonia stays."]),
        "APPROVE_STATISTICAL"),
    case("children with asthma per region (small cells)", "new", "approve", req(
        "J08", "Public health research on childhood asthma.", "How many children have asthma, per region?",
        ["Child = aged under 18 on 31 December 2025.", "Asthma = any condition with an ICD-10 code starting with J45.",
         "Report per region: children with asthma."]), "APPROVE_STATISTICAL"),
    case("SPE with another justification wording", "new", "approve", req(
        "J09", ("We develop and validate an algorithm that predicts kidney decline in heart failure. We need to link the "
                "records of each patient over time, so statistics are not enough."),
        "Provide pseudonymised conditions, medications and eGFR values for adults with heart failure who have at least "
        "one eGFR value.",
        [ADULT, "Heart failure = any condition with an ICD-10 code starting with I50.",
         "Cohort = adults with heart failure who have at least one eGFR value (LOINC 62238-1).",
         "Report the size of the cohort you would make available."], as_="health data access application"),
        "APPROVE_SPE"),
    case("access application without justification per hospital", "new", "approve", req(
        "J10", "Quality improvement: statin use in type 2 diabetes, to update a care guideline.",
        "Provide pseudonymised records of adults with type 2 diabetes and their statins.",
        [ADULT, T2D, "Statin = ATC code starting with C10AA.",
         "Report per hospital: adults with type 2 diabetes, % of them with an active statin."],
        as_="health data access application"), "APPROVE_STATISTICAL"),
    case("grouped by region and sex", "new", "approve", req(
        "J11", "Research on obesity by region and sex, to target prevention.", "How many patients have obesity, by region and sex?",
        ["Obesity = any condition with an ICD-10 code starting with E66.", "Report per region and sex: patients with obesity."]),
        "APPROVE_STATISTICAL"),
    case("employer reassigning drivers", "new", "reject", req(
        "J12", ("Our occupational health service wants to know which drivers have diabetes so that we can reassign "
                "drivers to shorter routes."), "How many of our drivers have type 2 diabetes, per region?",
        [ADULT, T2D, "Report per region: adults with type 2 diabetes."],
        applicant={"name": "Petra Wimmer", "organisation": "AlpTrans Logistik GmbH, HR", "country": "AT"})),
    case("statin advertising campaign", "new", "reject", req(
        "J13", "We plan the advertising campaign for our new statin and need to know where most patients live.",
        "How many adults with hypertension live in each region?",
        [ADULT, "Hypertension = any condition with an ICD-10 code starting with I10.",
         "Report per region: adults with hypertension."],
        applicant={"name": "Jan Novak", "organisation": "CardioPharm GmbH, brand team", "country": "AT"})),
    case("life insurer underwriting", "new", "reject", req(
        "J14", "We want to improve underwriting of life insurance policies for applicants with heart failure.",
        "What share of patients with heart failure is aged 65 or older?",
        ["Heart failure = any condition with an ICD-10 code starting with I50.", "Report per region: patients with heart failure."],
        applicant={"name": "Eva Moser", "organisation": "Donau Leben AG", "country": "AT"})),

    # ---- wildcard: same meaning, messy form ------------------------------------------------------------------------
    case("lower-case codes", "wildcard", "approve", req(
        "W01", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, "Type 2 diabetes = any condition with an ICD-10 code starting with e11.",
         "Report per region: adults, adults with type 2 diabetes."]), "APPROVE_STATISTICAL"),
    case("no spaces around =, no full stops", "wildcard", "approve", req(
        "W02", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        ["Adult=aged 18 or older on 31 December 2025", "Type 2 diabetes=any condition with an ICD-10 code starting with E11",
         "Report per region: adults, adults with type 2 diabetes"]), "APPROVE_STATISTICAL"),
    case("all definitions in one string, semicolons", "wildcard", "approve", req(
        "W03", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [f"{ADULT[:-1]}; {T2D[:-1]}; Report per region: adults, adults with type 2 diabetes."]), "APPROVE_STATISTICAL"),
    case("definitions as one text instead of a list", "wildcard", "approve", req(
        "W04", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        f"{ADULT}\n{T2D}\nReport per region: adults, adults with type 2 diabetes."), "APPROVE_STATISTICAL"),
    case("no id and no submitted timestamp", "wildcard", "approve", {
        k: v for k, v in req("W05", "Research on regional differences in type 2 diabetes.",
                             "How many adults have type 2 diabetes, per region?",
                             [ADULT, T2D, "Report per region: adults, adults with type 2 diabetes."]).items()
        if k not in {"id", "submitted"}}, "APPROVE_STATISTICAL"),
    case("request type in capitals", "wildcard", "approve", req(
        "W06", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, T2D, "Report per region: adults, adults with type 2 diabetes."], as_="Health Data Request",
        fmt="anonymised statistics"), "APPROVE_STATISTICAL"),
    case("ICD10 without hyphen", "wildcard", "approve", req(
        "W07", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, "Type 2 diabetes = any condition with an ICD10 code starting with E11.",
         "Report per region: adults, adults with type 2 diabetes."]), "APPROVE_STATISTICAL"),
    case("several codes in one definition", "wildcard", "approve", req(
        "W08", "Research on cardiovascular disease burden by hospital.", "How many patients have heart failure or atrial fibrillation, per hospital?",
        ["Heart disease = any condition with an ICD-10 code starting with I50 or I48.",
         "Report per data_holder: patients with heart disease."]), "APPROVE_STATISTICAL"),
    case("extra unknown fields", "wildcard", "approve", req(
        "W09", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, T2D, "Report per region: adults, adults with type 2 diabetes."],
        ethics_vote="EK 1234/2026", funding={"source": "FWF", "grant": "P-12345"}), "APPROVE_STATISTICAL"),
    case("ICD-10 code without \"starting with\"", "wildcard", "approve", req(
        "W12", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, "Type 2 diabetes = ICD-10 code E11.", "Report per region: adults, adults with type 2 diabetes."]),
        "APPROVE_STATISTICAL"),
    case("age as 18+", "wildcard", "approve", req(
        "W13", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        ["Adult = aged 18+ on 31 December 2025.", T2D, "Report per region: adults, adults with type 2 diabetes."]),
        "APPROVE_STATISTICAL"),
    case("age without the reference date", "wildcard", "approve", req(
        "W14", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        ["Adult = aged 18 or older.", T2D, "Report per region: adults, adults with type 2 diabetes."]),
        "APPROVE_STATISTICAL", "the data's reference date is assumed and noted"),
    case("age range with between", "wildcard", "approve", req(
        "W15", "Occupational health research on hypertension in working-age adults.",
        "How many working-age adults have hypertension, per hospital?",
        ["Working age = aged between 18 and 64 on 31 December 2025.",
         "Hypertension = any condition with an ICD-10 code starting with I10.",
         "Report per hospital: working age, working age with hypertension."]), "APPROVE_STATISTICAL"),
    case("exclude a condition", "wildcard", "approve", req(
        "W16", "Research on type 2 diabetes without kidney disease, to plan prevention.",
        "How many adults with type 2 diabetes but without chronic kidney disease are there, per region?",
        [ADULT, T2D, "Exclude patients with chronic kidney disease.", "Report per region: adults with type 2 diabetes."]),
        "APPROVE_STATISTICAL"),
    case("exclude opted-out patients (already done)", "wildcard", "approve", req(
        "W17", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, T2D, "Exclude opted-out patients.", "Report per region: adults, adults with type 2 diabetes."]),
        "APPROVE_STATISTICAL"),
    case("exclude with a time window we cannot read", "wildcard", "review", req(
        "W18", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, T2D, "Exclude patients who had a stroke in the last year.",
         "Report per region: adults, adults with type 2 diabetes."]), note="no time window template: must not guess"),
    case("typo in a template word", "wildcard", "review", req(
        "W10", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, "Type 2 diabetes = any conditon with an ICD-10 code startng with E11.",
         "Report per region: adults, adults with type 2 diabetes."]), note="must not guess what a misspelt clause means"),
    case("German definitions", "wildcard", "review", req(
        "W11", "Wir untersuchen regionale Unterschiede bei Typ-2-Diabetes.", "Wie viele Erwachsene haben Typ-2-Diabetes, je Bundesland?",
        ["Erwachsene = 18 Jahre oder älter am 31. Dezember 2025.", "Typ-2-Diabetes = ICD-10-Code beginnt mit E11.",
         "Bericht je Bundesland: Erwachsene, Erwachsene mit Typ-2-Diabetes."])),

    # ---- error: requests that make no sense or are broken ----------------------------------------------------------
    case("no definitions at all", "error", "review", req(
        "E01", "Research on type 2 diabetes.", "How many adults have type 2 diabetes?", [])),
    case("age bands outside the population", "error", "review", req(
        "E02", "Research on type 2 diabetes in adults.", "How many adults have type 2 diabetes, by age band?",
        [ADULT, T2D, "Age bands on 31 December 2025: 0-9, 10-17.", "Report per band: adults with type 2 diabetes."]),
        note="every cell would be <10 because no adult is in any band"),
    case("inverted age range", "error", "review", req(
        "E03", "Research on heart failure in old age.", "How many older patients have heart failure, per region?",
        ["Elderly = aged 90 to 65 on 31 December 2025.", "Heart failure = any condition with an ICD-10 code starting with I50.",
         "Report per region: elderly with heart failure."])),
    case("overlapping age bands", "error", "review", req(
        "E04", "Research on hypertension by age.", "How many adults have hypertension, by age band?",
        [ADULT, "Hypertension = any condition with an ICD-10 code starting with I10.",
         "Age bands on 31 December 2025: 18-49, 40-64, 65+.", "Report per band: adults with hypertension."])),
    case("code that occurs nowhere in the data", "error", "review", req(
        "E05", "Research on Gaucher disease.", "How many patients have Gaucher disease, per region?",
        ["Gaucher disease = any condition with an ICD-10 code starting with E75.", "Report per region: patients with Gaucher disease."])),
    case("measurement that occurs nowhere in the data", "error", "review", req(
        "E06", "Research on glucose control in type 2 diabetes.", "What is the mean fasting glucose in type 2 diabetes, per region?",
        [T2D, "Use the latest glucose (LOINC 2345-7) per patient.",
         "Report per region: patients with type 2 diabetes who have a glucose value and their mean glucose, one decimal."])),
    case("year outside the data", "error", "review", req(
        "E07", "Policy-making: hospital capacity planning.", "How many inpatient stays started in 2019, per region?",
        ["Inpatient stay = encounter with type 'inpatient'.", "Count stays (not patients) whose start_date is in 2019.",
         "Report per region: inpatient stays."]), note="data runs 2023-2025"),
    case("statistics request that asks for records", "error", "review", req(
        "E08", "Research on regional differences in type 2 diabetes.", "How many adults have type 2 diabetes, per region?",
        [ADULT, T2D, "Report per region: adults, adults with type 2 diabetes."], fmt="pseudonymised records"),
        note="requested_as and requested_format contradict each other"),
    case("same term defined twice", "error", "review", req(
        "E09", "Research on regional differences in diabetes.", "How many patients have diabetes, per region?",
        ["Diabetes = any condition with an ICD-10 code starting with E11.",
         "Diabetes = any condition with an ICD-10 code starting with E10.", "Report per region: patients with diabetes."])),
    case("gibberish purpose and question", "error", "review", req(
        "E10", "asdf qwer lorem ipsum.", "zzz?", [ADULT, T2D, "Report per region: adults, adults with type 2 diabetes."])),
    case("question asks for something the definitions do not", "error", "review", req(
        "E11", "Research on body weight in type 2 diabetes.", "What is the mean BMI of adults with type 2 diabetes, per region?",
        [ADULT, T2D, "Use the latest HbA1c (LOINC 4548-4) per patient.",
         "Report per region: adults with type 2 diabetes who have a HbA1c value and their mean HbA1c, one decimal."]),
        note="question says BMI, definitions compute HbA1c"),
    case("SPE cohort that nobody matches", "error", "review", req(
        "E12", "We train a model on patient histories of very old adults with type 2 diabetes; aggregates are not enough.",
        "Provide pseudonymised conditions and medications for patients aged 120 or older with type 2 diabetes.",
        ["Very old = aged 120 or older on 31 December 2025.", T2D, "Cohort = very old with type 2 diabetes.",
         "Report the size of the cohort you would make available."], as_="health data access application")),
    case("report per band without bands", "error", "review", req(
        "E13", "Research on type 2 diabetes by age.", "How many adults have type 2 diabetes, by age band?",
        [ADULT, T2D, "Report per band: adults with type 2 diabetes."])),
    case("mean of a diagnosis", "error", "review", req(
        "E14", "Research on type 2 diabetes.", "What is the mean type 2 diabetes per region?",
        [ADULT, T2D, "Report per region: adults with type 2 diabetes and their mean type 2 diabetes."])),
    case("missing purpose", "error", "invalid", {k: v for k, v in req(
        "E15", "x", "How many adults have type 2 diabetes?", [ADULT, T2D, "Report per region: adults."]).items()
        if k != "purpose"}),
    case("unknown request type", "error", "invalid", req(
        "E16", "Research on type 2 diabetes.", "How many adults have type 2 diabetes?",
        [ADULT, T2D, "Report per region: adults."], as_="please give me everything", fmt="all")),
    case("reference date that is not the data's", "error", "review", req(
        "E17", "Research on type 2 diabetes.", "How many adults had type 2 diabetes at the end of 2023, per region?",
        ["Adult = aged 18 or older on 31 December 2023.", T2D, "Report per region: adults with type 2 diabetes."])),
]

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(CASES, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(CASES)} cases → {OUT}")
