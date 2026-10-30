"""Deterministic decision rules (S-003, S-053): prohibited purpose → request type → SPE justification → statistics.

Every pattern is hand-written; no machine-learned component (S-052). Patterns are case-insensitive regexes over the
request's own text fields, never over the organisation (S-062, S-074).
"""

import re
from dataclasses import dataclass, field

from hdab.contracts import Answer, Decision, Request, TraceStep

# S-037 / S-073: one entry per Art. 54(1) category; Kev's option list (M-10) is built from these keys.
CATEGORIES: dict[str, tuple[str, str, list[str]]] = {
    # key: (Art. 54(1) point, label, patterns)
    "detrimental_decisions": ("a", "decisions detrimental to persons", [
        r"detrimental", r"\bdeny (them|patients|people|persons|benefits|treatment|coverage)", r"blacklist",
        r"exclude (them|patients|people|persons|customers|applicants) from",
        r"\b(avoid|refuse|stop) (renting|lending|insuring|hiring|selling)\b",
    ]),
    "employment": ("b", "decisions about employees or employment", [
        r"employee list", r"(decisions?|decide) (about|on) (our |their )?(employees|staff|workers)", r"renew\w* .{0,20}contracts",
        r"\bhiring\b", r"\brecruit\w* decisions?", r"who (to|we) (hire|dismiss|promote)", r"\bdismiss\w*", r"job applicants?",
        r"which (of (our|their) )?(staff|employees|workers|drivers) to (keep|hire|dismiss|promote|let go)",
        r"pre-employment", r"\b(reassign|release|dismiss|fire|lay off)\w* (them|employees|staff|workers|drivers)\b",
        r"medically unfit", r"\bfit(ness)? for (duty|work)\b",
        r"mitarbeiterliste", r"bewerber", r"kündigung", r"angestellte\w*", r"vertragsverlängerung",
    ]),
    "insurance_credit": ("b", "insurance, credit or premiums", [
        r"premiums?\b", r"underwrit", r"insurance pricing", r"risk[- ]based (tariff|pricing)", r"tariffs?\b",
        r"credit ?(score|worthiness|rating)", r"\bloans?\b", r"interest rates?",
        r"\bpric\w*\b.{0,30}\b(insurance|policies|policy|contracts?|loans?|credit)\b",
        r"\b(cost|price|rate|fee)s? (that )?(reflect|depend|are based)\w*.{0,40}\b(health|risk|profile|diagnos\w*|illness)", r"prämie", r"versicherungstarif", r"kreditwürdig",
    ]),
    "advertising_marketing": ("c", "advertising or marketing", [
        r"advertis", r"marketing", r"promot\w* (our|their|the|a|new) (product|drug|brand|medicine)",
        r"sales (target|territor|lead|rep)", r"\bpush\w* .{0,30}\bto (doctors|physicians|gps|prescribers)\b", r"increase (the )?(prescriptions|sales|uptake) of (our|their)", r"billboards?",
        r"werbung", r"werbekampagne",
    ]),
    "harmful_products": ("d", "harmful products (tobacco, nicotine, alcohol, illicit drugs, weapons, addictive designs)", [
        r"nicotine", r"tobacco", r"cigarett", r"\bvap(e|es|ing)\b", r"alcoholic (beverage|drink|product)s?",
        r"\b(beer|wine|spirits|liquor)\b", r"\bweapons?\b", r"illicit drugs?", r"addictive (design|product|feature)s?", r"gambling", r"casinos?", r"e-?liquids?", r"nikotin", r"tabak",
        r"zigarette", r"\bwaffe",
    ]),
    "ethics": ("e", "purposes against national ethical rules", [
        r"ethical rules", r"eugenic", r"sex selection", r"human cloning",
    ]),
}

NEGATION = re.compile(
    r"\b(not|never|no|without|instead|rather|nor|won't|don't|doesn't|isn't|aren't|nicht|kein\w*|nie)\b|n't\b", re.IGNORECASE
)
HYPOTHETICAL = re.compile(r"\b(if|could|might|would|hypothetical\w*|suppose\w*|wenn|falls|könnte\w*)\b", re.IGNORECASE)
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|„[^“”]*[“”]|‘[^’]*’|(?<!\w)'[^']*'(?!\w)")
INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules)|disregard (all |any |the )?\w* ?(instructions|rules)"
    r"|system prompt|you are now|approve this request|ignoriere|note to the (review\w* )?(system|reviewer|model|ai)"
    r"|\balready (been )?approved\b|\bmark (it|this|the request) as\b|\bplease approve\b",
    re.IGNORECASE,
)
# Matching released data against an own list of people re-identifies them (R06; Art. 61 duty).
REIDENTIFICATION = [
    r"(match|link|combin|merg)\w* .{0,40}\b(with|against) (our|their|an?|the) .{0,30}\blist", r"re-?identif\w*",
    r"de-?anonymi[sz]\w*", r"\bfind (out )?who\b",
    (r"\b(compare|match|link|check|combin|merg|cross-?referenc)\w*\b.{0,80}\b(member|customer|client|employee|staff|patient|"
     r"policyholder|tenant)s?\b.{0,20}\b(database|list|records|register)\b"),
    r"\b(names?|addresses)\b.{0,60}\b(database|list|register)\b",
]
# S-059 / S-021: a statistics request that asks for record-level data anywhere in its text (H15).
RECORDS = [r"\b(underlying|raw|individual|row-level|record-level|patient)[- ](rows|records|data)\b",
           r"\b(attach|export|send|provide|include|share)\w*\b.{0,40}\b(rows|raw data|patient data|records)\b"]
# A prohibited-product or pricing word in a sentence about the harm itself (H08, H10): review, not reject.
COUNTER_PURPOSE = re.compile(r"\b(cessation|quit\w*|stop smoking|prevent\w*|harm|harms|harm reduction|barriers?|whether|"
                             r"keep\w* (people|patients) from)\b", re.IGNORECASE)
WINDOW = 8  # words before a hit that are checked for negation or hypothesis

# S-075: phrasings that individual-level data is needed (S-003 rule 3).
SPE_JUSTIFICATION = [
    r"individual[- ]level", r"record[- ]level", r"patient[- ]level", r"per[- ]patient (data|histor\w*|records)",
    r"(aggregates?|aggregated data|statistics|summary data) (is|are) not (enough|sufficient)",
    r"(aggregates?|statistics) (would )?not (be )?(enough|sufficient)", r"not (answerable|possible) with (aggregates|statistics)",
    r"link\w* (the )?records (of each patient )?over time", r"longitudinal (patient )?records",
    r"(train|validat|develop)\w* .{0,60}\bon (individual |patient |pseudonymised )?(patient )?(histories|records)",
    r"patient histories",
]

# S-078: Art. 53(1) purpose points.
PURPOSES: dict[str, tuple[str, list[str]]] = {
    "a": ("public health or occupational health", [r"public health", r"prevention", r"prävention", r"occupational", r"epidemic", r"surveillance"]),
    "b": ("policy-making and regulation", [r"\bpolicy", r"policies", r"regulat", r"health planning"]),
    "c": ("official statistics", [r"official statistic", r"annual health report", r"national statistic"]),
    "d": ("education and teaching", [r"teaching", r"\blehre\b", r"\beducation", r"curricul", r"students?\b", r"lecture"]),
    "e": ("scientific research, including product development and training or testing of algorithms", [
        r"forschung", r"untersuch", r"studie",
        r"research", r"\bstud(y|ies)\b", r"\bmodel\b", r"algorithm", r"validat", r"\bAI\b", r"machine learning",
        r"risk factor", r"epidemiolog",
    ]),
    "f": ("improving healthcare", [r"quality", r"treatment gap", r"improv\w* (care|treatment|healthcare)", r"guideline",
                                   r"patient safety", r"discharge planning"]),
}
PUBLIC_BODY = re.compile(
    r"ministry|federal|national|statistic|public|authority|agency|universit|government|bundes|\bamt\b|gesundheitskasse", re.IGNORECASE
)
ORG_SIGNALS = {
    "insurer": r"insur|versicher",
    "HR department": r"\bHR\b|human resources|personnel|personalabteilung",
    "marketing": r"marketing|advertis|werb",
    "tobacco or nicotine company": r"tobacco|nicotine|tabak|nikotin",
}

ARTICLES: dict[str, list[str]] = {
    "reject": ["54"],
    "statistics_request": ["53", "69"],
    "spe": ["53", "66", "68", "73"],
    "statistics_fallback": ["53", "66", "69"],
}
OPT_OUT_SENTENCE = "Patients who opted out of secondary use were excluded (Art. 71)."


@dataclass
class Hit:
    key: str
    field: str
    words: str
    qualified: str | None  # "negated", "hypothetical", "quoted" (S-063) or "about the harm itself"; None = plain hit


@dataclass
class RuleResult:
    decision: Decision
    articles: list[str]
    reason: str
    trace: list[TraceStep] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)  # Art. 54 keys with a plain hit (what Kev K1 is compared with)
    qualified: bool = False  # a prohibited purpose mentioned only negated, hypothetically or quoted (Kev K2)
    justified: bool = False  # the text says individual-level data is needed (Kev K3)
    injection: bool = False  # text addressing the system (S-061); the model may then not soften a rejection

    def answer(self) -> Answer:
        return Answer(
            decision=self.decision, articles=self.articles, reason=self.reason, trace=self.trace,
            needs_review=bool(self.review_reasons), review_reasons=self.review_reasons, signals=self.signals,
        )


def text_fields(request: Request) -> dict[str, str]:
    """S-062: every text field of the request except the applicant; extra fields (e.g. from the form) included."""
    fields = {"purpose": request.purpose, "question": request.question}
    fields |= {f"definitions[{i}]": d for i, d in enumerate(request.definitions)}
    fields |= {k: v for k, v in (request.model_extra or {}).items() if isinstance(v, str)}
    return fields


def _qualifier(text: str, start: int, end: int, counter: bool = False) -> str | None:
    if any(q.start() <= start and end <= q.end() for q in QUOTED.finditer(text)):
        return "quoted"
    sentence_start = max(text.rfind(c, 0, start) for c in ".;!?") + 1
    before = " ".join(text[sentence_start:start].split()[-WINDOW:])
    if NEGATION.search(before):
        return "negated"
    if HYPOTHETICAL.search(before):
        return "hypothetical"
    if not counter:
        return None
    sentence_end = min([i for i in (text.find(c, end) for c in ".;!?") if i != -1] or [len(text)])
    if COUNTER_PURPOSE.search(text[sentence_start:sentence_end]):
        return "about the harm itself"
    return None


def find(patterns: list[str], fields: dict[str, str], key: str = "", counter: bool = False) -> list[Hit]:
    hits = []
    for name, text in fields.items():
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                end = m.end()
                while end < len(text) and text[end].isalnum():  # evidence shows whole words ("advertising", not "advertis")
                    end += 1
                hits.append(Hit(key, name, text[m.start():end], _qualifier(text, m.start(), end, counter)))
    return hits


def prohibited_hits(fields: dict[str, str]) -> list[Hit]:
    return [h for key, (_, _, patterns) in CATEGORIES.items() for h in find(patterns, fields, key, counter=True)]


def _evidence(hits: list[Hit]) -> list[str]:
    return [f'{h.field}: "{h.words}"' + (f" ({h.qualified})" if h.qualified else "") for h in hits]


def decide(request: Request, ignore_prohibited: bool = False) -> RuleResult:
    """`ignore_prohibited`: keyword hits only flag (D-08, when the decision model reads the purpose as allowed)."""
    fields = text_fields(request)
    trace: list[TraceStep] = []
    review: list[str] = []
    signals = [f"Organisation looks like: {name} ({request.applicant.organisation})"
               for name, pattern in ORG_SIGNALS.items() if re.search(pattern, request.applicant.organisation, re.IGNORECASE)]

    injection = find([INJECTION.pattern], fields)
    trace.append(TraceStep(rule="text addressing the system (S-061)", matched=bool(injection), evidence=_evidence(injection)))
    if injection:
        review.append("S-061: the request contains text that addresses the system: " + "; ".join(_evidence(injection)))

    # Rule 1: prohibited purpose (Art. 54). Any plain hit rejects, also next to allowed purposes (S-064).
    hits = prohibited_hits(fields)
    plain = [h for h in hits if h.qualified is None]
    qualified = [h for h in hits if h.qualified is not None]
    trace.append(TraceStep(rule="1 prohibited purpose (Art. 54)", matched=bool(plain), evidence=_evidence(hits)))
    reid = [h for h in find(REIDENTIFICATION, fields) if h.qualified is None]
    trace.append(TraceStep(rule="re-identification of persons (Art. 61)", matched=bool(reid), evidence=_evidence(reid)))
    why = {k: v for k, v in fields.items() if not k.startswith("definitions")}  # S-049: purpose or question
    justification = find(SPE_JUSTIFICATION, why)
    plain_just = [h for h in justification if h.qualified is None]
    facts = {"categories": list(dict.fromkeys(h.key for h in plain)), "qualified": bool(qualified) and not plain,
             "justified": bool(plain_just), "injection": bool(injection)}
    if plain and ignore_prohibited:
        review.append("S-064: prohibited-purpose words found: " + "; ".join(_evidence(plain)))
    if plain and not ignore_prohibited:
        keys = facts["categories"]
        parts = [f"Art. 54(1)({CATEGORIES[k][0]}), {CATEGORIES[k][1]} ("
                 + ", ".join(f'"{w}"' for w in dict.fromkeys(h.words for h in plain if h.key == k)) + ")" for k in keys]
        reason = "The stated use is prohibited: " + "; ".join(parts) + "."
        if reid:
            reason += " Matching the data with an own list would also re-identify people."
        reason += " No data is released."
        return RuleResult("REJECT", ARTICLES["reject"], reason, trace, review, signals, **facts)
    if reid:
        review.append("Art. 61: the request text suggests re-identifying people: " + "; ".join(_evidence(reid)))
    if qualified:
        review.append("S-063: a prohibited purpose is mentioned negated, hypothetically, quoted or as the harm being studied: "
                      + "; ".join(_evidence(qualified)))

    purposes = {p: label for p, (label, patterns) in PURPOSES.items() if find(patterns, fields)}
    trace.append(TraceStep(rule="Art. 53(1) purpose", matched=bool(purposes),
                           evidence=[f"({p}) {label}" for p, label in purposes.items()]))
    if not purposes:
        review.append("Art. 53(1): no allowed purpose recognised in the request text")
    if set(purposes) & {"a", "b", "c"} and not PUBLIC_BODY.search(request.applicant.organisation):
        signals.append("Art. 53(2): points (a) to (c) are for public sector bodies only; the applicant is not recognisably one")
    purpose_text = ("The purpose is allowed under Art. 53(1): "
                    + "; ".join(f"({p}) {label}" for p, label in purposes.items()) + ". ") if purposes else ""

    # Rule 2: health data request → statistics.
    is_request = request.requested_as == "health data request"
    trace.append(TraceStep(rule="2 requested as a health data request (Art. 69)", matched=is_request, evidence=[request.requested_as]))
    if is_request:
        records = [h for h in find(RECORDS, fields) if h.qualified is None]
        trace.append(TraceStep(rule="record-level data asked for in a statistics request (S-059)", matched=bool(records),
                               evidence=_evidence(records)))
        if records:
            review.append("S-059: a health data request asks for record-level data, which is never released: "
                          + "; ".join(_evidence(records)))
        reason = purpose_text + "Anonymised statistics answer the question (Art. 69). " + OPT_OUT_SENTENCE
        return RuleResult("APPROVE_STATISTICAL", ARTICLES["statistics_request"], reason, trace, review, signals, **facts)

    # Rule 3: access application that explains why statistics are not enough (Art. 67(2)(e)).
    trace.append(TraceStep(rule="3 access application explains why statistics are not enough (Art. 67(2)(e))",
                           matched=bool(plain_just), evidence=_evidence(justification)))
    if plain_just:
        quote = "; ".join(dict.fromkeys(f'"{h.words}"' for h in plain_just))
        reason = (purpose_text + f"The applicant explains why anonymised data is not enough (Art. 67(2)(e)): {quote}, "
                  "which the access body accepts as sufficient (Art. 68(1)(c)), so pseudonymised data is justified "
                  "(Art. 66). Access only under a data permit inside a secure processing environment (Art. 68, 73). "
                  + OPT_OUT_SENTENCE)
        return RuleResult("APPROVE_SPE", ARTICLES["spe"], reason, trace, review, signals, **facts)
    if justification:
        review.append("S-075: a reason why statistics are not enough is mentioned only in a negated, hypothetical or "
                      "quoted way: " + "; ".join(_evidence(justification)))

    # Rule 4: any other access application → statistics.
    trace.append(TraceStep(rule="4 other access application → statistics (Art. 66, 69)", matched=True))
    if request.why_statistics_not_enough:
        review.append("S-049: the applicant gave a reason why statistics are not enough, but the rules did not recognise it: "
                      f'"{request.why_statistics_not_enough}"')
    reason = (purpose_text + "The application does not show under Art. 67(2)(e) why anonymised data is not enough, "
              "so pseudonymised records are not justified (Art. 66). Approved as anonymised statistics instead (Art. 69). "
              + OPT_OUT_SENTENCE)
    return RuleResult("APPROVE_STATISTICAL", ARTICLES["statistics_fallback"], reason, trace, review, signals, **facts)
