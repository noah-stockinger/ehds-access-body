# Finding: R03 — requested diagnosis vs. ICD-10 definition

Reported by a team member. The first part is their note; the last two sections (data check, fit with the specs) were added afterwards.
This is an analysis note, not a goal list (goals: `MILESTONES.md`) and not binding (rules: `SPECS.md`).

## Background

Request R03 is a health data request from the Austrian Federal Ministry of Health. It asks how many patients aged 65 or older with
atrial fibrillation are not receiving oral anticoagulants, to find treatment gaps. It is classified `APPROVE_STATISTICAL`.
The request contains an inconsistency between the condition described in words and its ICD-10 definition.

## Where exactly does the issue occur?

1. `R03.purpose`: "Guidelines recommend oral anticoagulation for most older patients with atrial fibrillation. We want to know how large the treatment gap is to plan a quality programme."
2. `R03.question`: "Among patients with atrial fibrillation aged 65 and over, how many have no active oral anticoagulant, by age band?"
3. `R03.definitions[0]`: "Atrial fibrillation = any condition with an ICD-10 code starting with I48."

The third line creates the problem. ICD-10 category **I48 covers both atrial fibrillation and atrial flutter**:

| ICD-10 code | Diagnosis |
|---|---|
| I48.0 | Paroxysmal atrial fibrillation |
| I48.1 | Persistent atrial fibrillation |
| I48.2 | Chronic atrial fibrillation |
| I48.3 | Typical atrial flutter |
| I48.4 | Atypical atrial flutter |
| I48.9 | Atrial fibrillation and flutter, unspecified |

The requested prefix is broader than the condition in the research question.

## Why is this a problem?

Two different populations could be selected:

- **Interpretation A (verbal diagnosis):** atrial fibrillation only. I48.0, I48.1 and I48.2 identify it; I48.9 needs a special rule because it does not reliably distinguish the two conditions.
- **Interpretation B (ICD-10 prefix):** every patient with a code starting with I48, including atrial flutter without fibrillation.

Both can be defended as following part of the instructions, but they need not give the same statistics. A patient with only typical atrial flutter (`I48.3`) is in B and not in A.

## Where does this affect the expected output?

Expected decision: `APPROVE_STATISTICAL`. Expected answer:

| Age band | AF patients | Without OAC | Share without OAC |
|---|---:|---:|---:|
| 65–74 | 81 | 30 | 37.0% |
| 75–84 | 154 | 37 | 24.0% |
| 85+ | 78 | 22 | 28.2% |

Affected fields: `af_patients`, `without_oac`, `share_without_oac_pct`. The field `af_patients` is the most problematic because it labels the selected population
as atrial fibrillation although the ICD-10 filter also includes flutter. Denominators, numerators and percentages may differ depending on the definition applied.

## Suggested improvement: terminology fact-check before extraction

Add a medical terminology and code-validation step that compares the stated condition with the supplied ICD-10, ATC or LOINC codes and flags inconsistencies
that could materially change the selected population. For R03 it could show:

> **Definition mismatch detected.** Your request refers to patients with atrial fibrillation, but the ICD-10 prefix I48 includes both atrial fibrillation and atrial flutter.
> These definitions may produce different patient counts and treatment-gap percentages. Please clarify whether you intend to include:
> 1. Only patients with atrial fibrillation.
> 2. Patients with atrial fibrillation or atrial flutter.
>
> Please revise or confirm the diagnosis definition before resubmitting. Unspecified diagnoses such as I48.9 may require an additional inclusion rule.

This prevents the tool from silently choosing one interpretation.

## Assessment (team member)

R03 is not a legal compliance problem but a data-definition and output-accuracy problem. The purpose is permitted and statistics are the right format.
The expected assessment approves the request without identifying or resolving the ambiguity.
Recommendation: an automated terminology fact-check that detects such mismatches, explains the implications and asks the applicant to clarify.

## Check against the data (added)

`conditions.csv` contains only two I48 codes: **I48.0** (Paroxysmal atrial fibrillation, 196 rows) and **I48.2** (Chronic atrial fibrillation, 170 rows).
There are no flutter codes (I48.3, I48.4) and no I48.1 or I48.9. 366 patients have an I48 code, 351 of them not opted out.
So on this dataset, Interpretation A and B select the same patients and the expected numbers are the same either way.
The mismatch is real in principle, and a differently generated dataset or a new jury request could expose it, but it does not change the R03 result here.

## How this fits our specs (added)

- **S-007** says a code prefix given in a definition is used exactly, and **S-017** requires the expected numbers of R03. The R03 numbers must therefore come from the exact prefix I48. A blocking "please clarify and resubmit" would make R03 unanswerable and contradict S-003/S-017.
- So the fact-check should be an **advisory note**, not a gate: the answer is computed with the exact prefix, and the note ("I48 also includes atrial flutter; no flutter codes occur in this data") appears in the answer and the staff view. In the guided form it can be shown as a prompt before submission.
- It extends **S-058** (inferred mapping shown to staff) from "name without code" to "name with a code that is broader or narrower than the name", and fits the plain-English plan rendering of **S-057**.
- A general check needs a curated table of code-prefix → what it covers; a first version can cover the prefixes used in R01–R10 plus common ones. Where the data contains none of the extra codes, the note says so (as above).
- Proposed spec text (not yet in `SPECS.md`): S-070 · When a definition names a condition, drug or measurement in words and also gives a code or prefix, the app checks the pair against a curated table; if the code covers more or less than the name, the answer and the staff view carry a "definition mismatch" note that says what else the code covers and whether such codes occur in the data; the numbers are still computed with the exact code or prefix (S-007) and the request is not blocked · **Verify:** R03 carries the I48 note (flutter codes: none in the data) and its numbers still match `expected.json`; a new request using the prefix I48 with a data set containing I48.3 shows them in the note · proposed
