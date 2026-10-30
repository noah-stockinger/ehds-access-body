"""Decision-model questions (S-031 to S-034, S-036, S-050, S-052, S-054, S-065, S-072), local Kev or hosted Jev.

`KEV_MODE` (default `off`; `KEV_ENABLED=true` still means `assisted`):
- `assisted`: the rules decide; the model's disagreement or low confidence (< 0.80) sets `needs_review` (S-054).
- `led` (branch `noah` only, DECISIONS.md D-08): the model reads the purpose (K1). It can reject a prohibited purpose
  the keyword rules missed, and turn a keyword rejection it reads as harmless into a review; it never approves on its
  own. Its other answers only flag on disagreement.
`KEV_PROVIDER`: `kev` (local, `$KEV_BASE_URL`) or `jev` (hosted TypeSafe, `$TYPESAFE_API_KEY`); `led` defaults to `jev`.
Only request text is sent (S-022), never data rows.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

import httpx

from hdab import rules
from hdab.contracts import Answer, Request, TraceStep
from hdab.plan import Plan
from hdab.rules import CATEGORIES, RuleResult

THRESHOLD = 0.80  # S-050 start value, assisted mode
LEAD_REJECT = 0.50  # led: K1 names a prohibited category at least this sure → reject (DECISIONS.md D-08)
LEAD_CLEAR = 0.70  # led: K1 says "none" at least this sure → a keyword rejection becomes a review
MODEL_STEP = "1b decision model reads the purpose"  # trace step the staff view shows when the model changed the outcome


def lead_threshold(kind: str) -> float:
    """`$KEV_LEAD_REJECT` / `$KEV_LEAD_CLEAR` override the defaults, read on every request (like `mode`)."""
    default = LEAD_REJECT if kind == "reject" else LEAD_CLEAR
    try:
        return float(os.environ.get(f"KEV_LEAD_{kind.upper()}", default))
    except ValueError:
        return default

# S-073: the same Art. 54 categories as the rule lexicon, plus "none"; fixed order (S-036).
CATEGORY_CRITERIA = {key: f"Art. 54(1)({point}): {label}" for key, (point, label, _) in CATEGORIES.items()}
CATEGORY_CRITERIA["none"] = "none of these: the use is not prohibited"


class Unavailable(Exception):
    pass


def mode() -> str:
    """S-052: read on every request, so switching needs no code change and no restart."""
    m = os.environ.get("KEV_MODE", "").strip().lower()
    if m in {"off", "assisted", "led"}:
        return m
    return "assisted" if os.environ.get("KEV_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"} else "off"


def enabled() -> bool:
    return mode() != "off"


def provider() -> str:
    p = os.environ.get("KEV_PROVIDER", "").strip().lower()
    return p if p in {"kev", "jev"} else ("jev" if mode() == "led" else "kev")


def name() -> str:
    return provider().capitalize()


def base_url() -> str:
    if provider() == "jev":
        return os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")
    return os.environ.get("KEV_BASE_URL", "http://127.0.0.1:8009").rstrip("/")


def model() -> str:
    return "jev-latest" if provider() == "jev" else "kev-latest"  # DECISIONS.md D-01


def timeout() -> float:
    return float(os.environ.get("KEV_TIMEOUT", "60" if provider() == "jev" else "10"))


def post(payload: dict) -> dict:
    """The only outbound call of the app (S-032; with the jev provider this is a hosted service, D-08)."""
    headers = {"Authorization": f"Bearer {os.environ.get('TYPESAFE_API_KEY', '')}"} if provider() == "jev" else {}
    r = httpx.post(f"{base_url()}/v1/systemone", json=payload, headers=headers, timeout=timeout())
    r.raise_for_status()
    return r.json()


def request_text(request: Request) -> str:
    """Only request text goes to the model, never data rows (S-022)."""
    return "\n".join([f"Purpose: {request.purpose}", f"Question: {request.question}", "Definitions:",
                      *request.definitions])


def questions(request: Request, plan: Plan | None) -> list[tuple[str, str, dict]]:
    """K1 to K6 of docs/DESIGN.md as (key, state, question), in a fixed order (S-036). K6 only in `led` mode."""
    text = request_text(request)
    qs = [
        ("K1_category", text, {"type": "choice", "instructions": "Which prohibited use under Art. 54 of the EHDS does the "
                               "applicant actually intend? Choose none if the use is allowed.", "criteria": CATEGORY_CRITERIA}),
        ("K2_negated", text, {"type": "noul", "instructions": "Does the text mention a prohibited use (such as insurance "
                              "premiums, marketing or decisions about employees) only to deny it, hypothetically or in quotes?"}),
        ("K3_individual_level", text, {"type": "noul", "instructions": "Does the applicant give a reason why aggregate "
                                       "statistics would not be enough for their purpose? Merely asking for records is not a reason."}),
        ("K5_per_patient", text, {"type": "noul", "instructions": "Does the requested output list individual patients "
                                  "(one line per patient, patient IDs) instead of aggregate numbers?"}),
    ]
    if plan is not None:
        state = text + "\n\nPlan:\n" + "\n".join(plan.render())
        qs.insert(3, ("K4_plan_faithful", state, {"type": "noul", "instructions": "Does the plan describe what the "
                                                  "definitions ask for, without adding or leaving out a condition?"}))
    if mode() == "led":
        qs.append(("K6_identifies_people", text, {"type": "noul", "instructions": "Could the requested results, alone "
                   "or combined with data the applicant already holds, be used to identify, contact or single out "
                   "individual people?"}))
    return qs


def confidence(a: dict) -> float:
    """DECISIONS.md D-02: `confidence` for a choice, distance from 0.5 for a yes/no answer."""
    if a["type"] == "choice":
        return float(a["confidence"])
    return max(float(a["noul"]), 1 - float(a["noul"]))


@dataclass
class Asked:
    key: str
    answer: dict
    version: str
    instructions: str = ""
    sent: str = ""

    @property
    def value(self):
        return self.answer["choice"] if self.answer["type"] == "choice" else float(self.answer["noul"]) >= 0.5

    @property
    def confidence(self) -> float:
        return confidence(self.answer)


def ask(request: Request, plan: Plan | None) -> dict[str, Asked]:
    """One question per call, fixed order (S-036). Raises `Unavailable` if any call fails (S-072)."""
    out = {}
    for key, state, question in questions(request, plan):
        try:
            r = post({"state": state, "model": model(), "questions": {key: question}})
            out[key] = Asked(key, r["answers"][key], r.get("model", model()), question["instructions"], state)
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise Unavailable(type(e).__name__) from e
    return out


RELATION_CRITERIA = {"match": "the code means the named condition",
                     "broader": "the code covers the named condition and other, different conditions too",
                     "different": "the code means a different condition"}


RELATION_INSTRUCTIONS = "How does the ICD-10 code relate to the named condition?"


@lru_cache(maxsize=256)  # a pre-check and its submit ask the same thing; failures are not cached
def _relation(who: str, state: str) -> tuple[dict, str]:
    question = {"type": "choice", "instructions": RELATION_INSTRUCTIONS,
                "criteria": RELATION_CRITERIA}
    r = post({"state": state, "model": model(), "questions": {"K7_definition": question}})
    return r["answers"]["K7_definition"], r.get("model", model())


def relation_state(name_: str, codes: tuple[str, ...], who_text: str) -> str:
    return f'Definition: "{name_} = any condition with an ICD-10 code starting with {" or ".join(codes)}."\n{who_text}'


def relation(name_: str, codes: tuple[str, ...], who_text: str) -> tuple[dict, str]:
    """S-070: does the code mean the named condition? Only the definition and WHO's wording are sent, not the request."""
    state = relation_state(name_, codes, who_text)
    try:
        answer, version = _relation(provider(), state)
        return {**answer, "confidence": confidence(answer)}, version
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise Unavailable(type(e).__name__) from e


def lead(request: Request, result: RuleResult, asked: dict[str, Asked]) -> RuleResult:
    """`led` mode: the model's reading of the purpose (K1) can reject, or turn a keyword rejection into a review
    (never when the request contains text addressing the system, S-061)."""
    k1, k2 = asked["K1_category"], asked["K2_negated"]
    prohibited = k1.value != "none"
    who = f"{name()} ({k1.version}, confidence {k1.confidence:.2f})"
    if result.decision == "REJECT":
        if result.injection:  # S-061: text aimed at the model; its "harmless" reading cannot be trusted here
            if not prohibited:
                result.review_reasons.append(f"D-08: {who} reads the purpose as allowed, but the request contains text "
                                             "addressing the system, so the keyword rejection stands")
                result.trace.append(TraceStep(rule=MODEL_STEP, matched=False, evidence=[
                    f"{who}: none", "keyword rejection kept: the request contains text addressing the system"]))
            return result
        if not prohibited and k1.confidence >= lead_threshold("clear"):
            softened = rules.decide(request, ignore_prohibited=True)
            softened.review_reasons.append(
                f"D-08: the keyword rules matched {', '.join(result.categories)}, but {who} reads the purpose as allowed; "
                "staff decide")
            softened.trace.append(TraceStep(rule=MODEL_STEP, matched=False, evidence=[
                f"{who}: none", "overrules the keyword rule: " + ", ".join(
                    f"Art. 54(1)({CATEGORIES[k][0]}) {CATEGORIES[k][1]}" for k in result.categories)]))
            return softened
        return result
    if prohibited and k1.confidence >= lead_threshold("reject") and not k2.value:
        point, label, _ = CATEGORIES[k1.value]
        reason = (f"The stated use is prohibited: Art. 54(1)({point}), {label}, as read by the decision model {who}. "
                  "No keyword rule matched; staff confirm the rejection. No data is released.")
        trace = result.trace + [TraceStep(rule=f"{MODEL_STEP} (Art. 54)", matched=True,
                                          evidence=[f"{who}: {k1.value}"])]
        return RuleResult("REJECT", rules.ARTICLES["reject"], reason, trace, list(result.review_reasons),
                          list(result.signals), categories=[k1.value])
    if prohibited:
        result.review_reasons.append(f"D-08: {who} reads a possible prohibited use ({k1.value}), not sure enough to reject")
    elif k1.confidence < lead_threshold("reject"):
        result.review_reasons.append(f"D-08: {who} is unsure whether the purpose is allowed")
    return result


def expected(key: str, rules_: RuleResult, request: Request, plan: Plan | None):
    """What the rules concluded for the same question; None means the question does not apply."""
    if key == "K1_category":
        return set(rules_.categories) or {"none"}
    if key == "K2_negated":
        return rules_.qualified
    if key == "K3_individual_level":
        return rules_.justified if request.requested_as == "health data access application" else None
    if key == "K4_plan_faithful":
        return True
    if key == "K5_per_patient":
        if mode() == "led" and rules_.decision != "APPROVE_STATISTICAL":
            return None  # patient-level output is the point of an SPE and moot for a rejection
        return plan.per_patient if plan is not None else None
    if key == "K6_identifies_people":
        if rules_.decision != "APPROVE_STATISTICAL":
            return None  # an SPE holds records by design; a rejection releases nothing
        return any("Art. 61" in r or "S-059" in r for r in rules_.review_reasons)
    return None


def annotate(answer: Answer, request: Request, rules_: RuleResult, plan: Plan | None,
             asked: dict[str, Asked] | None) -> None:
    """Mode label, the model's answers with agreement, and the resulting review flags (the decision is not changed)."""
    m = mode()
    if asked is None:  # S-072: fall back to rules only, flagged
        answer.mode = f"Rules only ({name()} unreachable)"
        answer.review_reasons.append(f"S-072: {name()} did not answer; decided by the rules only")
        answer.needs_review = True
        return
    answer.mode = f"{name()}-{m}"
    for key, a in asked.items():
        want = expected(key, rules_, request, plan)
        got = a.value
        if key == "K1_category" and want is not None:  # the decision only depends on prohibited or not
            agrees = (got == "none") == (want == {"none"})
        else:
            agrees = None if want is None else got == want
        answer.kev.append({"question": key, "answer": a.answer, "model": a.version, "confidence": round(a.confidence, 4),
                           "rules": sorted(want) if isinstance(want, set) else want, "agrees": agrees,
                           "instructions": a.instructions, "sent": a.sent})
        if m == "led" and key == "K1_category":
            continue  # handled by `lead`
        if agrees is False:
            answer.review_reasons.append(f"S-054: {name()} {key} answered {got!r}, the rules concluded "
                                         f"{sorted(want) if isinstance(want, set) else want!r}")
        elif agrees and m == "assisted" and a.confidence < THRESHOLD:
            answer.review_reasons.append(f"S-034: {name()} {key} agrees but with confidence {a.confidence:.2f} < {THRESHOLD}")
    answer.needs_review = bool(answer.review_reasons)
