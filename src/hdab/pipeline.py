"""The single entry point (S-001): every request, from the API, the form or a script, goes through `decide`.

`decide` is pure (same input, same answer, S-025); `submit` adds the side effects: register, SPE file (S-076).
"""

from datetime import date

from hdab import definitions, kev, register, rules, sanity, spe, sql, stats
from hdab.contracts import Answer, Decision, Request
from hdab.data import load_requests
from hdab.plan import Plan, PSet, parse


def decide(request: Request) -> Answer:
    m = kev.mode()
    result = rules.decide(request)
    plan = parse(request) if result.decision != "REJECT" or m == "led" else None
    asked = None
    if m != "off":  # S-052: with the model off no call ever leaves the app
        try:
            asked = kev.ask(request, plan)
        except kev.Unavailable:
            asked = None
    if m == "led" and asked is not None:
        result = kev.lead(request, result, asked)
    answer = result.answer()
    if m != "off":
        kev.annotate(answer, request, result, plan, asked)
    plan = plan or parse(request)
    checked = definitions.check(plan)
    answer.definition_warnings, answer.kev = checked.warnings, answer.kev + checked.asked
    if answer.decision == "REJECT":
        return answer  # S-005: no numbers
    problems = plan.problems
    if answer.decision == "APPROVE_STATISTICAL" and plan.per_patient:
        problems.append("S-059: the report asks for patient-level output, which a statistical answer never contains")
    if answer.decision == "APPROVE_SPE":
        if plan.cohort is None:
            problems.append("S-018: A secure environment needs a line saying which patients to include, such as \"Cohort = adults with type 2 diabetes.\"")
        elif not spe.record_types(request, plan):
            problems.append("S-018: The question or purpose must name the record types the secure environment should hold: conditions, medications or measurements.")
    problems += sanity.check(request, plan, spe=answer.decision == "APPROVE_SPE")  # does the request make sense?
    answer.plan_text, answer.unclaimed_words = plan.render(), plan.unclaimed_words
    answer.unclaimed_parts = [part for part, _ in plan.unclaimed]
    answer.notes = plan.notes + checked.notes + [w.message for w in checked.warnings if w.message not in plan.notes]
    answer.review_reasons += problems + [f"S-070: {w.message}" for w in checked.warnings if w.severity in ("wrong", "unsure")]
    answer.needs_review = bool(answer.review_reasons)
    if not problems:  # S-046, S-056: nothing understood only in part gets numbers
        answer.answer = stats.execute(plan, spe=answer.decision == "APPROVE_SPE")
        if answer.decision == "APPROVE_SPE":
            answer.permit = spe.permit(request, plan, date.today())
    return answer


def overlaps(request: Request, cells: dict[str, set[str]]) -> list[str]:
    """S-051: a cell that differs from an earlier cell of the same applicant by 1 to 9 patients could be
    un-suppressed by subtraction."""
    found = []
    for rid, cell, ids in register.earlier_cells(request.applicant.organisation, request.id):
        for name, mine in cells.items():
            small, big = sorted([mine, ids], key=len)
            if small <= big and 0 < len(big) - len(small) < stats.SMALL:
                found.append(f"S-051: cell {name} differs from cell {cell} of {rid} by fewer than 10 patients")
    return found


def _state_query(answer: Answer, request: Request, plan: Plan) -> None:
    held = spe.held_types(request, plan) if answer.decision == "APPROVE_SPE" else None
    answer.sql, answer.sql_matches = sql.check(plan, answer.answer, held)


def submit(request: Request) -> Answer:
    """S-076: decision, numbers and SPE are computed at once; release to the applicant waits for staff."""
    received = register.now()
    answer = decide(request)
    if answer.decision == "APPROVE_SPE" and answer.permit:
        spe.create(request, parse(request))
    if answer.answer is not None:
        _state_query(answer, request, parse(request))
    if answer.decision == "APPROVE_STATISTICAL" and answer.answer is not None:
        cells = stats.Engine(parse(request)).cell_sets()
        if found := overlaps(request, cells):
            answer.review_reasons += found
            answer.needs_review = True
        register.store_cells(request.id, request.applicant.organisation, cells)
    register.store(request, answer, received, register.now())
    return answer


def reset() -> list[str]:
    """Demo clean slate, as after `make seed` on an empty `var/`: only R01–R10, as proposals, with a fresh audit log."""
    for entry in register.all_entries():
        spe.delete(entry["id"], "demo reset")  # also ends a running RStudio session
    register.clear()
    requests = load_requests()
    for r in requests:
        submit(r)
    return [r.id for r in requests]


def confirm(request_id: str, staff: str) -> Answer:
    entry = register.get(request_id)
    if entry["answer"].decision == "APPROVE_SPE" and not entry["answer"].permit:
        raise ValueError("No data permit can be issued for this application as written. Ask the applicant to correct it, or override.")
    register.set_status(request_id, entry["answer"], "confirmed", staff)
    register.log(request_id, staff, "confirmed", {"decision": entry["answer"].decision})
    return entry["answer"]


def override(request_id: str, staff: str, decision: Decision, reason: str, articles: list[str]) -> Answer:
    """S-042: staff replace the proposal; S-076: leaving APPROVE_SPE deletes the SPE, and the register says who."""
    entry = register.get(request_id)
    old: Answer = entry["answer"]
    new = old.model_copy(update={"decision": decision, "reason": reason, "articles": articles, "permit": None,
                                 "answer": None, "needs_review": False, "review_reasons": [],
                                 "sql": None, "sql_matches": None})
    if old.decision == "APPROVE_SPE" and decision != "APPROVE_SPE":
        spe.delete(request_id, staff)
    if decision == "APPROVE_SPE" and old.permit:
        new = new.model_copy(update={"permit": old.permit, "answer": old.answer, "sql": old.sql, "sql_matches": old.sql_matches})
    elif decision == "APPROVE_SPE":
        # shortcut: a request naming no cohort gets all patients not opted out (S-018 asks for one), demo only; before real use, make the officer name the cohort.
        plan = parse(entry["request"])
        plan.cohort, plan.cohort_size = plan.cohort or PSet("all patients"), True
        spe.create(entry["request"], plan)
        new = new.model_copy(update={"permit": spe.permit(entry["request"], plan, date.today()),
                                     "answer": stats.execute(plan, spe=True)})
        _state_query(new, entry["request"], plan)
    elif decision == "APPROVE_STATISTICAL":
        plan = parse(entry["request"])
        new.answer = stats.execute(plan, spe=False)
        _state_query(new, entry["request"], plan)
    register.set_status(request_id, new, "overridden", staff)
    register.log(request_id, staff, "overridden", {"from": old.decision, "to": decision, "reason": reason,
                                                   "articles": articles})
    if new.sql != old.sql:
        register.log_query(request_id, new)
    return new
