"""What the applicant and the staff see of one register entry (S-024, S-041, S-055, S-071, S-076). Filters only."""

import csv
import io

from hdab import explain, vocab
from hdab.plan import parse
from hdab.spe import DUTIES, SPE_DUTIES

STATUS_TEXT = {
    "proposed": "Proposed decision; the access body still has to confirm it.",
    "confirmed": "Decision confirmed by the access body.",
    "overridden": "Decision changed by the access body.",
}


def ai_note(mode: str) -> str | None:
    """S-055: say when an AI model helped prepare the proposal."""
    model = mode.split("-")[0]
    if mode.endswith("-assisted"):
        return f"An AI model ({model}) double-checked this proposal; the decision comes from fixed rules and staff."
    if mode.endswith("-led"):
        return (f"An AI model ({model}) read the purpose of this request and helped decide whether it is allowed; "
                "staff confirm every decision.")
    return None


def released(entry: dict) -> bool:
    """Numbers, permit and SPE access reach the applicant only after staff confirmed or overrode (S-071, S-076)."""
    return entry["status"] != "proposed"


def applicant(entry: dict) -> dict:
    a = entry["answer"]
    out = {
        "id": entry["id"],
        "status": entry["status"],
        "status_text": STATUS_TEXT[entry["status"]],
        "request": entry["request"].model_dump(),
        "decision": a.decision,
        "articles": a.articles,
        "reason": a.reason,
        "steps": [f"{s.rule}: {'yes' if s.matched else 'no'}" for s in a.trace if not s.rule.startswith("text addressing")],
        "plan_text": a.plan_text,
        "notes": [vocab.for_applicant(n) for n in a.notes],
        "mode": a.mode,
        "ai_note": ai_note(a.mode),
        "answer": a.answer if released(entry) else None,
        "permit": a.permit if released(entry) else None,
        "duties": {"REJECT": [], "APPROVE_SPE": SPE_DUTIES}.get(a.decision, DUTIES),  # S-041
    }
    if not released(entry) and a.decision != "REJECT":
        out["withheld"] = "Results are released after the access body has confirmed the decision."
    return out


def staff(entry: dict) -> dict:
    return {
        "id": entry["id"],
        "status": entry["status"],
        "staff": entry["staff"],
        "received": entry["received"],
        "decided": entry["decided"],
        "applicant": entry["request"].applicant.model_dump(),
        "request": entry["request"].model_dump(),
        "answer": entry["answer"].model_dump(),
        "proposal": entry["proposal"].model_dump(),
        "explanations": explain.for_answer(entry["answer"]),
    }


def results_csv(entry: dict) -> str:
    """The released statistics as CSV, exactly as the applicant sees them: `<10` and `suppressed` stay (S-014, S-015)."""
    groups = parse(entry["request"]).groups

    def leaves(node: dict, path: tuple = ()):
        if node and all(isinstance(v, dict) for v in node.values()):
            for key, child in node.items():
                yield from leaves(child, (*path, key))
        else:
            yield path, node

    rows = list(leaves(entry["answer"].answer))
    measures = list(dict.fromkeys(m for _, values in rows for m in values))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([*groups[:len(rows[0][0])], *measures])
    for path, values in rows:
        writer.writerow([*path, *(values.get(m, "") for m in measures)])
    return "\ufeff" + out.getvalue()  # the BOM lets Excel read ü and ä


def queue_item(entry: dict) -> dict:
    a = entry["answer"]
    return {"id": entry["id"], "received": entry["received"], "organisation": entry["request"].applicant.organisation,
            "decision": a.decision, "needs_review": a.needs_review, "status": entry["status"], "mode": a.mode}
