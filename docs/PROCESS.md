# Process and personas — solution/Laurenz

Context for the design. Not a goal list (goals live in `MILESTONES.md`) and not binding (rules live in `SPECS.md`).
Legal statements below come from secondary summaries of Reg. (EU) 2025/327 and still need checking against the Official Journal.

## Idea
Today a request arrives as an email and a clerk checks it by hand. We put a **guided platform** in front of the access body:
the applicant fills a form that builds the request JSON, so the request is complete by construction and the decision tree works on
structured fields. The API still accepts any request JSON (S-001), so the jury's files and unseen phrasings also work; what the parser
cannot understand becomes a "needs review" flag, never a guessed number.

## Personas
| Persona | Example | Today | Where we want to go |
|---|---|---|---|
| Researcher | University, public health institute (R01, R08) | Email, weeks of back-and-forth about missing details | Guided form, instant triage, statistics in minutes |
| Health-tech / AI developer | GlucoSense (R05) | Unsure whether to ask for records or statistics | Pre-check explains when an SPE is justified and what the SPE is |
| Public authority / statistics office | R07 | Informal requests | Standard template, auditable answer |
| Teaching / GP institute | R09 | Asks for records they do not need | Pre-check offers the statistical route |
| Prohibited-purpose applicant | Insurer, marketer, employer, tobacco (R02, R04, R06, R10) | Rejection late, by email | Early rejection with the article and a reason they can follow |
| Access-body officer | Staff | Reads emails, checks the law manually | Queue with trace, flags, confirm or override (S-042) |
| Data-protection / ethics reviewer | Staff | Consulted ad hoc | Sees only flagged cases with the evidence |
| Data holder | Hospital | Not involved | Optional: sees what was approved for its data |

## Flow
1. **Draft** — applicant fills the form (applicant, purpose from the Art. 53 list, format, population, variables, period, why statistics are not enough if records are requested).
2. **Pre-check** — likely decision with reasons, no register entry (proposed S-048).
3. **Submit** — request stored in the register with timestamp (S-038).
4. **Triage** — deterministic rules decide in the S-003 order and write a trace (proposed S-043); Kev gives an advisory second opinion (S-033, S-034).
5. **Execute** — reject (no numbers), statistics (query plan, opt-outs, small-cell rule), or SPE (separate DuckDB file, permit, named persons).
6. **Staff confirm** — decision is a proposal until staff confirm or override; every action logged (S-042).
7. **Deliver** — decision letter (HTML and JSON), duties of the applicant (S-041), numbers or SPE workspace.

## What each side gets back
| Output | Applicant | Staff |
|---|---|---|
| Decision, articles, reason (S-002) | yes, plain language | yes |
| Rule trace | short version | full, with evidence |
| Statistics table with `<10` / `suppressed` | yes | yes |
| Parsed definitions / query plan | summary | full |
| Kev answers and probabilities, review flags | no | yes |
| Data permit and SPE access (S-039, S-040) | yes | yes, plus access log |
| Duties (S-041) | yes | n/a |
| Register and audit log (S-038) | own requests | all |

## SPE, in one picture
A secure processing environment is a locked room for data. For R05 we create a separate DuckDB file holding only the 1152 selected patients
and only conditions, medications and HbA1c values. Only persons named in the permit may enter; a "Download" button answers 403 and the
attempt appears in the access log. The demo shows that screen, a proof panel (cohort size, tables present, zero opted-out IDs) and the log.

## AI Act and data protection stance
All statements below are our reading, not legal advice, and still need checking against the Official Journal.
- **Rules-only mode** is hand-written software and generally falls outside the Act's definition of an "AI system" (a system that infers outputs from its input). **Kev-assisted and Kev-led modes** use a model that infers probabilities, so they are inside it.
- **Risk class depends on the use case (Annex III), not on touching health data or using AI to read text.** The nearest entries are 5(a) (public authorities assessing natural persons' eligibility for essential public benefits and services, including healthcare) and 5(c) (risk assessment and pricing of life and health insurance). Deciding whether an organisation may reuse data does neither, so we assess it as probably not high-risk, but that is unverified. The closer Kev is to the decision (Kev-led), the more this matters.
- Art. 50 (transparency for chatbots, synthetic content, emotion recognition) likely does not apply: Kev only classifies and writes no text.
- Design that helps in every mode: rules-only is the default (S-052, S-053), Kev can be switched off, the mode is named in every view (S-055), inputs and outputs are logged (S-038), staff confirm every proposal (S-042), and only request text goes to a local model (S-022, S-035).
- Reported dates (secondary sources, provisional): standalone high-risk obligations moved to 2 December 2027. The EHDS secondary-use chapter applies from March 2029. Decision deadlines under the EHDS are reported inconsistently; do not quote one.

## Risks
- Free-text definitions in unseen requests: mitigated by building the vocabulary from the data's own `description` / `name` columns and by the needs-review flag.
- Prohibited-purpose phrasing: lexicon plus Kev, disagreement goes to staff.
- Kev runs on another machine: rule-only mode keeps the app working.
