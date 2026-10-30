"""Definitions → query plan (S-006, S-056, S-057). Pattern parser only, nothing per request (S-053).

Each definition clause must fully match one template; each report item must fully parse. Anything else is unclaimed:
its content words are listed and the request gets `needs_review` with no numbers (S-046, S-056). Never guess.
"""

import re
from dataclasses import dataclass, field

from hdab import vocab
from hdab.contracts import Request

REF_DATE = "31 December 2025"  # S-009
STOP = {"a", "an", "the", "of", "in", "on", "at", "to", "and", "or", "with", "who", "which", "that", "is", "are", "was",
        "were", "be", "by", "for", "per", "from", "as", "it", "its", "their", "them", "they", "this", "these", "those"}
CODE = r"\b(?:[A-Z]\d{2}[A-Z]{1,2}\d{0,2}|[A-Z]\d{2}(?:\.\d+)?)\b"  # ATC first, so B01AA is not read as B01
CODES = rf"(?:{CODE})(?:(?:,\s*|\s+or\s+)(?:{CODE}))*"
IRREGULAR = {"children": "child", "child": "children", "women": "woman", "woman": "women", "men": "man", "man": "men"}
ICD = r"ICD[- ]?10"
SUBJECT_ALL = {"patient", "patients", "people", "persons"}
GROUP_WORDS = {"region": "region", "regions": "region", "band": "band", "age band": "band", "age bands": "band",
               "age group": "band", "data_holder": "data_holder", "data holder": "data_holder", "hospital": "data_holder",
               "hospitals": "data_holder", "sex": "sex", "gender": "sex"}


@dataclass
class Term:
    name: str
    kind: str  # condition | medication | observation | age | sex | encounter | ratio
    codes: tuple[str, ...] = ()
    min_age: int | None = None
    max_age: int | None = None
    sex: str | None = None
    enc_type: str | None = None
    inferred: bool = False
    num: "PSet | None" = None  # ratio terms
    den: "PSet | None" = None
    used: bool = False

    def describe(self) -> str:
        if self.kind == "condition":
            return f"a condition with an ICD-10 code starting with {' or '.join(self.codes)}"
        if self.kind == "medication":
            return f"a medication with an ATC code starting with {' or '.join(self.codes)}"
        if self.kind == "observation":
            return f"a measurement with LOINC {' or '.join(self.codes)}"
        if self.kind == "age":
            hi = f" and at most {self.max_age}" if self.max_age is not None else ""
            return f"aged at least {self.min_age}{hi} on {REF_DATE} (age = 2025 − birth year)"
        if self.kind == "sex":
            return f"sex {self.sex}"
        if self.kind == "encounter":
            parts = [f"type {self.enc_type}"] if self.enc_type else []
            parts += [f"primary diagnosis starting with {' or '.join(self.codes)}"] if self.codes else []
            return "encounters" + (" with " + " and ".join(parts) if parts else "")
        return self.name


@dataclass
class Mod:
    term: Term
    negated: bool = False
    active: bool = False

    def describe(self) -> str:
        what = self.term.describe()
        if self.active:
            what = what.replace("a medication", f"a medication active on {REF_DATE}", 1)
        return ("without " if self.negated else "with ") + what


@dataclass
class PSet:
    """A set of patients (or encounters) described in words: subject terms plus modifiers."""
    text: str
    subject: list[Term] = field(default_factory=list)
    mods: list[Mod] = field(default_factory=list)

    @property
    def unit(self) -> str:
        return "encounters" if any(t.kind == "encounter" for t in self.subject) else "patients"

    def describe(self) -> str:
        if self.unit == "encounters":
            base = " and ".join(t.describe() for t in self.subject)
        else:
            base = "patients" + "".join(f" {t.describe()}" if t.kind == "age" else f" with {t.describe()}"
                                        for t in self.subject)
        return base + "".join(f", {m.describe()}" for m in self.mods)


@dataclass
class Measure:
    key: str
    kind: str  # count | share | mean
    num: PSet | None = None  # count: the set; share: numerator
    den: PSet | None = None  # share: denominator; mean: population
    obs: Term | None = None

    def describe(self) -> str:
        if self.kind == "count":
            return f"{self.key}: number of {self.num.describe()}"
        if self.kind == "share":
            return f"{self.key}: {self.num.describe()} as % of {self.den.describe()}, one decimal"
        return (f"{self.key}: mean of the latest {self.obs.name} value (LOINC {' or '.join(self.obs.codes)}) per patient, "
                f"over {self.den.describe()}, one decimal")


@dataclass
class Plan:
    terms: dict[str, Term] = field(default_factory=dict)
    bands: list[tuple[int, int | None, str]] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    restrict: list[Mod] = field(default_factory=list)
    year: str | None = None  # encounters: start_date in this year
    cohort: PSet | None = None
    cohort_size: bool = False
    per_patient: bool = False
    has_report: bool = False
    unclaimed: list[tuple[str, list[str]]] = field(default_factory=list)  # (sentence, content words)
    ambiguous: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # definitions that contradict themselves (sanity.py adds data checks)
    notes: list[str] = field(default_factory=list)

    @property
    def problems(self) -> list[str]:
        out = [f'S-056: could not understand "{s}" (unclaimed words: {", ".join(w)})' for s, w in self.unclaimed]
        out += [f"S-058: {a}" for a in self.ambiguous]
        out += [f"Sanity: {e}" for e in self.errors]
        if not self.has_report:
            out.append("S-046: no report line (\"Report per …\") was found")
        return out

    @property
    def unclaimed_words(self) -> list[str]:
        return [w for _, words in self.unclaimed for w in words]

    def render(self) -> list[str]:
        """S-057: the plan in plain English, next to the original definitions."""
        lines = ["Opted-out patients are excluded everywhere (Art. 71)."]
        for t in self.terms.values():
            if t.kind != "ratio":
                lines.append(f"{t.name} = {t.describe()}" + (" (inferred from the name, please check)" if t.inferred else ""))
        if self.year:
            lines.append(f"Encounters are counted (not patients), with a start date in {self.year}.")
        for m in self.restrict:
            lines.append(f"Everything is restricted to patients {m.describe()}.")
        if self.groups:
            names = {"band": "age band (" + ", ".join(b[2] for b in self.bands) + ")", "region": "region (all 9)",
                     "data_holder": "hospital (all 3)", "sex": "sex"}
            lines.append("Grouped by " + " and ".join(names[g] for g in self.groups) + "; empty groups are shown.")
        if self.cohort:
            lines.append(f"Cohort: {self.cohort.describe()}.")
        if self.cohort_size:
            lines.append("Reported: the size of the cohort.")
        if self.per_patient:
            lines.append("Reported: one line per patient (patient-level output).")
        lines += [f"Reported: {m.describe()}." for m in self.measures]
        lines.append("Counts below 10 are shown as <10; shares and means over fewer than 10 patients are suppressed.")
        return lines


def content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w%+-]+", text.lower()) if w not in STOP and not re.fullmatch(r"[\d.+-]+", w)]


def norm(text: str) -> str:
    text = " ".join(text.strip().rstrip(".").split())
    return re.sub(r"^(the|a|an)\s+", "", text, flags=re.IGNORECASE)


def slug(text: str) -> str:
    words = [w for w in re.findall(r"[\w%]+", text.lower()) if w not in {"a", "an", "the", "of", "number"}]
    return "_".join(words).replace("%", "pct")


def _codes(text: str) -> tuple[str, ...]:
    return tuple(re.findall(CODE, text.upper()))  # "e11" is E11; the clause regexes match case-insensitively


class Parser:
    def __init__(self, request: Request):
        self.request = request
        self.plan = Plan()

    # ---- terms -----------------------------------------------------------------------------------------------
    def term(self, name: str) -> Term | None:
        key = norm(name).lower()
        for k in (key, key.removesuffix("s"), key + "s", IRREGULAR.get(key, key)):
            if k in self.plan.terms:
                return self.plan.terms[k]
        return None

    def define(self, term: Term) -> None:
        key = norm(term.name).lower()
        old = self.plan.terms.get(key)
        if old is not None and (old.kind, old.codes, old.min_age, old.max_age, old.sex) != \
                (term.kind, term.codes, term.min_age, term.max_age, term.sex):
            self.plan.errors.append(f'"{term.name}" is defined twice with different meanings')
        self.plan.terms[key] = term

    def resolve(self, name: str) -> Term | None:
        """A defined term, or a plain-English name looked up in the vocabulary (S-007, S-058)."""
        if t := self.term(name):
            return t
        candidates = vocab.lookup(norm(name))
        if len(candidates) == 1:
            c = candidates[0]
            t = Term(name=norm(name), kind=c.kind, codes=c.codes, inferred=True)
            self.define(t)
            self.plan.notes.append(f'Inferred mapping: "{norm(name)}" → {c.kind} code {" or ".join(c.codes)} ({c.label}). '
                                   "Please check (S-058).")
            return t
        if len(candidates) > 1:
            options = "; ".join(f"{' or '.join(c.codes)} ({c.label})" for c in candidates)
            self.plan.ambiguous.append(f'"{norm(name)}" fits more than one code: {options}')
            return Term(name=norm(name), kind="ambiguous")
        return None

    # ---- sets ------------------------------------------------------------------------------------------------
    MOD = re.compile(r"(?:with|who have|who has|having|have|has)\s+(?:(no)\s+|(?:a|an|at least one|any)\s+)?(active\s+)?"
                     r"(.+?)(?:\s+(?:values?|prescriptions?|diagnosis|diagnoses|measurements?))?", re.IGNORECASE)

    def mods(self, text: str) -> list[Mod] | None:
        out = []
        for part in re.split(r"\s+(?=(?:with|who have|who has|having)\s)", text.strip()):
            m = self.MOD.fullmatch(part.strip())
            if not m:
                return None
            t = self.resolve(m.group(3))
            if t is None or t.kind not in {"condition", "medication", "observation", "ambiguous"}:
                return None
            if m.group(2) and t.kind not in {"medication", "ambiguous"}:
                return None
            t.used = True
            out.append(Mod(t, negated=bool(m.group(1)), active=bool(m.group(2))))
        return out

    def pset(self, text: str) -> PSet | None:
        t = norm(text)
        t = re.sub(r"^(number of|all)\s+", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+in (the|each|this) (region|band|age band|group|hospital)$", "", t, flags=re.IGNORECASE)
        words = t.split()
        for n in range(len(words), 0, -1):  # longest subject first: "inpatient stays", then "adults"
            head, rest = " ".join(words[:n]), " ".join(words[n:])
            if head.lower() in SUBJECT_ALL:
                subject = []
            elif (s := self.term(head)) and s.kind in {"age", "sex", "encounter"}:
                s.used = True
                subject = [s]
            else:
                continue
            mods = self.mods(rest) if rest else []
            if mods is None:
                return None
            return PSet(text=t, subject=subject, mods=mods)
        return None

    # ---- definitions -----------------------------------------------------------------------------------------
    def definition(self, clause: str) -> bool:
        c = norm(clause)
        d = re.escape(REF_DATE)
        if m := re.fullmatch(rf"(.+?) = any (?:condition|diagnosis) with an {ICD} code starting with ({CODES})", c, re.IGNORECASE):
            self.define(Term(m.group(1), "condition", _codes(m.group(2))))
            if note := vocab.mismatch_note(m.group(1), _codes(m.group(2))):
                self.plan.notes.append(note)
            return True
        if m := re.fullmatch(rf"(.+?) = (?:any medication with an )?ATC code starting with ({CODES})", c, re.IGNORECASE):
            self.define(Term(m.group(1), "medication", _codes(m.group(2))))
            return True
        # Shorter forms ("ICD-10 code E11", "ATC C10AA"): a code is read as a prefix, as in "starting with"
        if m := re.fullmatch(rf"(.+?) = (?:(?:any |a )?(?:condition|diagnosis) with )?(?:an? )?{ICD}(?: codes?)?"
                             rf"(?: (?:starting|beginning) with)? ({CODES})", c, re.IGNORECASE):
            self.define(Term(m.group(1), "condition", _codes(m.group(2))))
            if note := vocab.mismatch_note(m.group(1), _codes(m.group(2))):
                self.plan.notes.append(note)
            return True
        if m := re.fullmatch(rf"(.+?) = (?:(?:any |a )?medication with )?(?:an? )?ATC(?: codes?)?"
                             rf"(?: (?:starting|beginning) with)? ({CODES})", c, re.IGNORECASE):
            self.define(Term(m.group(1), "medication", _codes(m.group(2))))
            return True
        if m := re.fullmatch(rf"(.+?) = aged (\d+)(?: years)?(?: or older| or over| and older| and over|\+)(?: on {d})?",
                             c, re.IGNORECASE):
            self.define(Term(m.group(1), "age", min_age=int(m.group(2))))
            self.no_date(c)
            return True
        if m := re.fullmatch(rf"(.+?) = aged between (\d+) and (\d+)(?: years)?(?: on {d})?", c, re.IGNORECASE):
            self.define(Term(m.group(1), "age", min_age=int(m.group(2)), max_age=int(m.group(3))))
            self.no_date(c)
            return True
        if m := re.fullmatch(rf"(.+?) = aged (\d+) (?:to|-) (\d+)(?: on {d})?", c, re.IGNORECASE):
            self.define(Term(m.group(1), "age", min_age=int(m.group(2)), max_age=int(m.group(3))))
            self.no_date(c)
            return True
        if m := re.fullmatch(rf"(.+?) = aged (?:under|below) (\d+)(?: on {d})?", c, re.IGNORECASE):
            self.define(Term(m.group(1), "age", min_age=0, max_age=int(m.group(2)) - 1))
            self.no_date(c)
            return True
        if m := re.fullmatch(r"(.+?) = sex '?(female|male)'?", c, re.IGNORECASE):
            self.define(Term(m.group(1), "sex", sex=m.group(2).lower()))
            return True
        if m := re.fullmatch(rf"(.+?) = (?:an? )?encounter(?: with type '?(\w+)'?)?(?:,? whose primary_icd10 starts with ({CODES}))?", c, re.IGNORECASE):
            self.define(Term(m.group(1), "encounter", _codes(m.group(3) or ""), enc_type=m.group(2)))
            return True
        if m := re.fullmatch(rf"age bands on {d}: (.+)", c, re.IGNORECASE):
            bands = []
            for b in re.split(r",\s*", m.group(1)):
                if bm := re.fullmatch(r"(\d+)\s*-\s*(\d+)", b):
                    bands.append((int(bm.group(1)), int(bm.group(2)), b))
                elif bm := re.fullmatch(r"(\d+)\+", b):
                    bands.append((int(bm.group(1)), None, b))
                else:
                    return False
            self.plan.bands = bands
            return True
        if re.fullmatch(r"(?:exclude (?:all )?opted[- ]out patients|opted[- ]out patients are (?:excluded|left out))", c,
                        re.IGNORECASE):
            return True  # S-008 holds for every request; the sentence only states it
        if re.fullmatch(rf"(?:a )?medication is active on {d} if start_date is on or before that day and end_date is empty "
                        r"or on or after that day", c, re.IGNORECASE):
            return True  # S-010 is the fixed semantic of "active"; the sentence only states it
        if m := re.fullmatch(r"use the latest (.+?) per patient", c, re.IGNORECASE):
            t = self.resolve(m.group(1))
            return t is not None and t.kind == "observation"  # "latest" is the fixed semantic of every mean (S-012)
        if m := re.fullmatch(r"patients without an? (.+?) are left out", c, re.IGNORECASE):
            t = self.resolve(m.group(1))
            if t is None or t.kind != "observation":
                return False
            t.used = True
            self.plan.restrict.append(Mod(t))
            return True
        if m := re.fullmatch(r"count (?:stays|encounters|visits)(?: \(not patients\))? whose start_date is in (\d{4})", c, re.IGNORECASE):
            self.plan.year = m.group(1)
            return True
        return False

    def no_date(self, clause: str) -> None:
        if REF_DATE.lower() not in clause.lower():
            note = f"No reference date given; ages are taken on {REF_DATE}, the data's reference date (S-009)."
            if note not in self.plan.notes:
                self.plan.notes.append(note)

    def deferred(self, clause: str) -> bool:
        """Definitions that refer to other terms: ratios, cohorts and the report line."""
        c = norm(clause)
        if m := re.fullmatch(r"(.+?) = (.+?) / (.+?)(\s*[×x*]\s*100)?(?:,? (?:with )?one decimal)?", c, re.IGNORECASE):
            num, den = self.pset(m.group(2)), self.pset(m.group(3))
            if num is None or den is None:
                return False
            self.define(Term(m.group(1), "ratio", num=num, den=den))
            return True
        if m := re.fullmatch(r"exclude (?:all )?(?:patients|people|persons|those) ((?:with|who have|who has|having) .+)", c,
                             re.IGNORECASE):
            mods = self.mods(m.group(1))  # "who had a stroke in the last year" does not parse: stays unclaimed
            if mods is None:
                return False
            self.plan.restrict += [Mod(x.term, negated=not x.negated, active=x.active) for x in mods]
            return True
        if m := re.fullmatch(r"cohort = (.+)", c, re.IGNORECASE):
            self.plan.cohort = self.pset(m.group(1))
            return self.plan.cohort is not None
        if m := re.fullmatch(r"report (?:the )?size of the cohort(?: you would make available)?", c, re.IGNORECASE):
            self.plan.cohort_size = self.plan.has_report = True
            return True
        if re.match(r"report for each patient\b|.*\b(list (each|every|all) patients?|patient ids?)\b", c, re.IGNORECASE):
            self.plan.per_patient = self.plan.has_report = True  # S-059: understood, and never answered with records
            return True
        if m := re.fullmatch(r"report per (.+?): (.+)", c, re.IGNORECASE):
            groups = [GROUP_WORDS.get(g.strip().lower()) for g in re.split(r"\s+and\s+", m.group(1))]
            if None in groups or ("band" in groups and not self.plan.bands):
                return False
            self.plan.groups = groups
            self.plan.has_report = True
            return self.report_items(m.group(2))
        return False

    def report_items(self, text: str) -> bool:
        base: PSet | None = None
        last: Measure | None = None
        for raw in re.split(r",\s*|\s+and\s+", text):
            item = norm(raw)
            item = re.sub(r"\s*,?\s*(?:with )?one decimal$", "", item, flags=re.IGNORECASE)
            if not item:
                continue
            measure = None
            if re.fullmatch(r"(?:that|the|their) share(?: in %)?", item, re.IGNORECASE) and last and last.kind == "count" and base:
                measure = Measure(f"share_{last.key}_pct", "share", num=last.num, den=base)
            elif (m := re.fullmatch(r"how many of them (.+)", item, re.IGNORECASE)) and base:
                mods = self.mods(m.group(1))
                if mods is not None:
                    measure = Measure(slug(m.group(1)), "count",
                                      num=PSet(item, base.subject, base.mods + mods))
            elif (m := re.fullmatch(r"%\s+(?:of them\s+)?(.+)", item, re.IGNORECASE)) and base:
                mods = self.mods(m.group(1))
                if mods is not None:
                    measure = Measure(slug(m.group(1)) + "_pct", "share",
                                      num=PSet(item, base.subject, base.mods + mods), den=base)
            elif (m := re.fullmatch(r"(?:their |the )?mean (.+?)", item, re.IGNORECASE)) and base:
                obs = self.resolve(m.group(1))
                if obs is not None and obs.kind == "observation":
                    obs.used = True
                    measure = Measure("mean_" + slug(m.group(1)), "mean", den=base, obs=obs)
            elif (t := self.term(item)) and t.kind == "ratio":
                t.used = True
                measure = Measure(slug(t.name) + "_pct", "share", num=t.num, den=t.den)
            elif s := self.pset(item):
                base = s
                measure = Measure(slug(item), "count", num=s)
            if measure is None:
                self.plan.unclaimed.append((raw.strip(), content_words(raw)))
                continue
            self.plan.measures.append(measure)
            last = measure if measure.kind == "count" else last
        return True  # unclaimed items are already recorded; the line itself is understood

    # ---- whole request ---------------------------------------------------------------------------------------
    def parse(self) -> Plan:
        clauses = [c.strip() for d in self.request.definitions for c in d.split(";") if c.strip()]
        later = []
        for clause in clauses:
            clause = self.inline_loinc(re.sub(r"\s*=\s*", " = ", clause))  # "Adult=aged …" reads as "Adult = aged …"
            if not self.definition(clause):
                later.append(clause)
        for clause in later:
            if not self.deferred(clause):
                self.plan.unclaimed.append((clause, content_words(clause)))
        self.implicit_restrictions()
        return self.plan

    def inline_loinc(self, clause: str) -> str:
        """`HbA1c value (LOINC 4548-4)` defines the observation term HbA1c and leaves `HbA1c value`."""
        def define(m: re.Match) -> str:
            self.define(Term(m.group(1), "observation", (m.group(3),)))
            return m.group(1) + (m.group(2) or "")
        return re.sub(r"([\w-]+)((?: values?)?) \(LOINC ([\d-]+)\)", define, clause)

    def implicit_restrictions(self) -> None:
        """A defined condition or medication not used in the report restricts the population if the question names it
        (R08: "women with breast cancer"); otherwise it is an unused definition and is flagged."""
        text = f"{self.request.question} {self.request.purpose}".lower()
        for t in self.plan.terms.values():
            if t.used or t.inferred or t.kind not in {"condition", "medication"}:
                continue
            if t.name.lower() in text:
                t.used = True
                self.plan.restrict.append(Mod(t))
                self.plan.notes.append(f'"{t.name}" is not in the report line; because the question names it, every '
                                       "count is restricted to these patients.")
            elif self.plan.has_report and not self.plan.cohort:
                self.plan.unclaimed.append((f"{t.name} (defined but never used)", content_words(t.name)))


def parse(request: Request) -> Plan:
    return Parser(request).parse()
