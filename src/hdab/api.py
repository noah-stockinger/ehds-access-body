"""FastAPI app: submit, staff actions and the SPE."""

import os
import re
from datetime import UTC, datetime
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator

from hdab import assist, definitions, pipeline, register, rstudio, sanity, spe, views, vocab
from hdab.contracts import Answer, Applicant, Decision, Request
from hdab.plan import parse

load_dotenv()  # KEV_ENABLED, KEV_BASE_URL, ... from .env (gitignored)
app = FastAPI(title="hdab")
# The frontend dev server (Vite, :5173) runs on another port; CORS_ORIGINS overrides, comma-separated.
app.add_middleware(CORSMiddleware, allow_methods=["*"], allow_headers=["*"], allow_origins=os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","))


class Confirm(BaseModel):
    staff: str = ""  # officer name for the audit log


class Override(BaseModel):
    staff: str = ""
    decision: Decision
    reason: str
    articles: list[str] = []


class Form(BaseModel):
    """The guided form (S-045): builds the same request JSON as `R*.json` and submits it through `submit`."""

    id: str | None = None
    applicant: Applicant
    requested_as: Literal["health data request", "health data access application"]
    requested_format: str | None = None
    purpose: str
    question: str
    definitions: list[str]
    why_statistics_not_enough: str | None = None  # S-049: required for an access application
    plan_confirmed: bool = False  # S-057: the applicant has read the plain-English plan
    warnings_confirmed: bool = False  # S-070: the applicant wants to send despite the definition warnings
    assist_model: str | None = None  # S-087: the model whose suggestion the applicant took, for the register

    @model_validator(mode="after")
    def access_application_needs_a_reason(self):
        if self.requested_as == "health data access application" and not (self.why_statistics_not_enough or "").strip():
            raise ValueError("An access application must say why anonymised statistics are not enough (Art. 67(2)(e)).")
        return self

    def to_request(self) -> Request:
        purpose = self.purpose
        why = (self.why_statistics_not_enough or "").strip()
        if why and why not in purpose:
            purpose = f"{purpose} {why}"
        fmt = self.requested_format or ("pseudonymised records" if self.requested_as == "health data access application"
                                        else "anonymised statistics")
        return Request(id=self.id or f"F-{datetime.now(UTC):%Y%m%d%H%M%S%f}",
                       submitted=datetime.now(UTC).isoformat(timespec="seconds"), applicant=self.applicant,
                       requested_as=self.requested_as, requested_format=fmt, purpose=purpose, question=self.question,
                       definitions=self.definitions, why_statistics_not_enough=why or None)


def officer(name: str) -> str:
    """shortcut: the name is self-declared (no login, D-10), add accounts before any non-demo use."""
    return name.strip() or "staff"


def entry_or_404(request_id: str) -> dict:
    entry = register.get(request_id)
    if entry is None:
        raise HTTPException(404, f"no request {request_id} in the register")
    return entry


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/requests")
def submit(request: Request) -> Answer:
    return pipeline.submit(request)


@app.post("/precheck")
def precheck(request: Request) -> dict:
    """S-048: the likely decision for a draft; no register entry, no SPE, no numbers."""
    a = pipeline.decide(request)
    reasons = [r for r in a.review_reasons if not r.startswith(sanity.DATA)]  # nothing about the data before a decision
    return {"notice": "This is a pre-check, not the decision. Nothing has been submitted.",
            "likely_decision": a.decision, "articles": a.articles, "reason": a.reason,
            "needs_review": bool(reasons), "review_reasons": reasons, "plan_text": a.plan_text,
            "notes": [vocab.for_applicant(n) for n in a.notes if n not in {w.message for w in a.definition_warnings}],
            "definition_warnings": [w.model_copy(update={"message": vocab.for_applicant(w.message)}) for w in a.definition_warnings],
            "unclaimed_words": a.unclaimed_words,
            "unclaimed_parts": a.unclaimed_parts}


@app.post("/form/precheck")
def form_precheck(form: Form) -> dict:
    return precheck(form.to_request())


class AssistDraft(BaseModel):
    """Unlike `Form`, unfinished text is fine here: this is what the help is for."""

    applicant: Applicant
    requested_as: Literal["health data request", "health data access application"]
    purpose: str = ""
    question: str = ""
    definitions: list[str] = []
    why_statistics_not_enough: str | None = None


@app.get("/form/assist")
def form_assist_on() -> dict:
    return {"enabled": assist.enabled()}


@app.post("/form/assist")
def form_assist(draft: AssistDraft) -> dict:
    """S-087: an AI explanation and suggestion for a draft; nothing is stored or decided."""
    if not assist.enabled():
        raise HTTPException(503, "The writing help is switched off. The form and the check work without it.")
    fields = draft.model_dump(exclude={"why_statistics_not_enough"})
    why = draft.why_statistics_not_enough or "(not given yet)" if draft.requested_as != "health data request" else None
    try:
        return assist.help(Form(**fields, why_statistics_not_enough=why).to_request(), precheck)
    except assist.Unavailable as e:
        raise HTTPException(503, "The writing help does not answer right now. The form and the check work without it.") from e


@app.post("/form/submit")
def form_submit(form: Form) -> dict:
    if not form.plan_confirmed:
        raise HTTPException(422, "Please confirm the plain-English plan before submitting (S-057).")
    request = form.to_request()
    warnings = [w for w in definitions.check(parse(request)).warnings if w.severity != "unsure"]
    if warnings and not form.warnings_confirmed:
        raise HTTPException(422, "Please confirm that you want to send despite the warnings on your definitions (S-070).")
    pipeline.submit(request)
    if warnings:
        register.log(request.id, form.applicant.name, "sent despite definition warnings", {"warnings": [w.message for w in warnings]})
    if form.assist_model:
        register.log(request.id, form.applicant.name, "question and definitions drafted with AI help", {"model": form.assist_model})
    return views.applicant(register.get(request.id))


@app.get("/applicant/requests")
def applicant_list() -> list[dict]:
    """Demo applicant portal (no applicant accounts): id, organisation, what was asked for and whether it is decided.
    The decision only once final, as in `/public/decisions` (S-082); a proposal stays hidden."""
    return [{"id": e["id"], "received": e["received"], "organisation": e["request"].applicant.organisation,
             "requested_as": e["request"].requested_as, "status": e["status"],
             "decision": e["answer"].decision if views.released(e) else None}
            for e in register.all_entries()]


@app.get("/applicant/requests/{request_id}")
def applicant_view(request_id: str) -> dict:
    return views.applicant(entry_or_404(request_id))


@app.get("/applicant/requests/{request_id}/results.csv")
def applicant_results(request_id: str) -> Response:
    """Released, anonymised statistics only: never before staff confirm (S-071), never records (Art. 73)."""
    entry = entry_or_404(request_id)
    answer: Answer = entry["answer"]
    if answer.decision != "APPROVE_STATISTICAL" or answer.answer is None or not views.released(entry):
        raise HTTPException(404, "this application has no released statistics")
    register.log(request_id, "applicant", "results_exported", {"format": "csv"})
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", request_id)
    return Response(views.results_csv(entry), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}-results.csv"'})


@app.get("/staff/queue")
def staff_queue() -> list[dict]:
    return [views.queue_item(e) for e in register.all_entries()]


@app.get("/staff/requests/{request_id}")
def staff_view(request_id: str) -> dict:
    return views.staff(entry_or_404(request_id)) | {"log": register.events(request_id)}


@app.post("/staff/requests/{request_id}/confirm")
def confirm(request_id: str, body: Confirm) -> Answer:
    entry_or_404(request_id)
    try:
        return pipeline.confirm(request_id, officer(body.staff))
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/staff/requests/{request_id}/override")
def override(request_id: str, body: Override) -> Answer:
    entry_or_404(request_id)
    try:
        return pipeline.override(request_id, officer(body.staff), body.decision, body.reason, body.articles)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/demo/reset")
def demo_reset() -> dict:
    """shortcut: open like every endpoint (no login, D-10) and it wipes the audit log, remove before any non-demo use."""
    return {"requests": pipeline.reset()}


@app.get("/public/decisions")
def public_decisions() -> list[dict]:
    """S-082 (Art. 57(1)(j)(iii)): who asked for what and the decision; no numbers, no patient data."""
    return [{"id": e["id"], "organisation": e["request"].applicant.organisation, "purpose": e["request"].purpose,
             "decision": e["answer"].decision, "articles": e["answer"].articles, "reason": e["answer"].reason}
            for e in register.all_entries() if e["status"] != "proposed"]


@app.get("/register/{request_id}/log")
def audit_log(request_id: str) -> list[dict]:
    entry_or_404(request_id)
    return register.events(request_id)


def spe_entry(request_id: str, user: str, action: str) -> dict:
    """S-040: only persons named in the permit, only after staff confirmed (S-076); every attempt is logged."""
    entry = entry_or_404(request_id)
    answer: Answer = entry["answer"]
    if answer.decision != "APPROVE_SPE" or not answer.permit or not spe.path(request_id).exists():
        register.log(request_id, user, f"spe_{action}_refused", {"why": "no SPE for this request"})
        raise HTTPException(404, "this request has no secure processing environment")
    if entry["status"] == "proposed":
        register.log(request_id, user, f"spe_{action}_refused", {"why": "not confirmed by staff yet"})
        raise HTTPException(403, "The access body has not confirmed this decision yet.")
    if not spe.allowed(answer.permit, user):
        register.log(request_id, user, f"spe_{action}_refused", {"why": "not named in the data permit"})
        raise HTTPException(403, f"{user} is not named in data permit {answer.permit['permit_id']}.")
    return entry


@app.get("/spe/{request_id}")
def spe_open(request_id: str, user: str) -> dict:
    entry = spe_entry(request_id, user, "open")
    register.log(request_id, user, "spe_opened")
    return {"permit": entry["answer"].permit, "proof": spe.proof(request_id)}


@app.post("/spe/{request_id}/rstudio")
def spe_rstudio(request_id: str, user: str) -> dict:
    spe_entry(request_id, user, "rstudio")
    try:
        session = rstudio.start(request_id, spe.path(request_id))
    except rstudio.Unavailable as e:
        raise HTTPException(503, f"RStudio could not start: {e}") from e
    register.log(request_id, user, "spe_rstudio_opened")
    return session


@app.get("/spe/{request_id}/download")
def spe_download(request_id: str, user: str) -> None:
    spe_entry(request_id, user, "download")
    register.log(request_id, user, "spe_download_refused", {"why": "downloads are blocked (Art. 73)"})
    raise HTTPException(403, spe.DOWNLOAD_REFUSED)  # S-020, S-081: always, also for permit holders
