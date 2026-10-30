"""Typed shapes of the challenge's input and output. Shapes only, no logic.

Mirrors `data/track3/requests/R*.json` (input) and `expected.json` (output); see SPECS.md S-001, S-002.
"""

import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Decision = Literal["REJECT", "APPROVE_STATISTICAL", "APPROVE_SPE"]
Mode = Literal["Rules only", "Kev-assisted", "Jev-assisted", "Kev-led", "Jev-led",  # S-055; -led: DECISIONS.md D-08
               "Rules only (Kev unreachable)", "Rules only (Jev unreachable)"]  # S-072


class Applicant(BaseModel):
    name: str
    organisation: str
    country: str


class Request(BaseModel):
    """One data request or access application submitted to the access body. Unknown fields are kept."""

    model_config = ConfigDict(extra="allow")

    # Bookkeeping fields may be missing in a hand-written request; the content fields may not (tests/jury W05, E15).
    id: str = Field(default_factory=lambda: f"J-{datetime.now(UTC):%Y%m%d%H%M%S%f}")
    submitted: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    applicant: Applicant
    requested_as: Literal["health data request", "health data access application"]
    requested_format: str = ""
    purpose: str
    question: str
    definitions: list[str]
    why_statistics_not_enough: str | None = None  # the form's answer as written; also added to `purpose` for the rules

    @field_validator("requested_as", mode="before")
    @classmethod
    def _request_type(cls, v):
        return " ".join(v.lower().split()) if isinstance(v, str) else v  # "Health Data Request" (W06)

    @field_validator("definitions", mode="before")
    @classmethod
    def _definitions(cls, v):
        """One text instead of a list (W04): one definition per line, or per sentence on a single line."""
        if not isinstance(v, str):
            return v
        lines = [x.strip() for x in v.splitlines() if x.strip()]
        if len(lines) == 1:
            lines = [x for x in re.split(r"(?<=\.)\s+(?=[A-Z])", lines[0]) if x]
        return lines


class TraceStep(BaseModel):
    """One checked rule step (S-043): what was checked, whether it matched, and the words that made it match."""

    rule: str
    matched: bool
    evidence: list[str] = []


class DefinitionWarning(BaseModel):
    """A name and code that do not seem to agree (S-070). `wrong` and `unsure` also go to review, `unsure` needs no confirmation."""

    severity: Literal["wrong", "check", "unsure"]
    definition: str
    message: str


class Answer(BaseModel):
    """The access body's answer. `answer` holds grouped statistics or the SPE cohort size; None if rejected.

    `needs_review` sits on top of the decision (S-071): the decision stays the rules' proposal, and while the flag is
    set nothing in `answer` is released to the applicant until staff confirm.
    """

    decision: Decision
    articles: list[str]
    reason: str
    answer: dict[str, Any] | None = None
    needs_review: bool = False
    review_reasons: list[str] = []
    trace: list[TraceStep] = []
    signals: list[str] = []  # staff-only hints that change nothing (S-074, S-078)
    plan_text: list[str] = []  # the query plan in plain English (S-057)
    notes: list[str] = []  # inferred mappings and definition mismatches (S-058, S-070)
    unclaimed_words: list[str] = []  # words of the definitions no plan element understood (S-056)
    unclaimed_parts: list[str] = []  # the sentences those words come from
    definition_warnings: list[DefinitionWarning] = []  # S-070; the same messages are in `notes` for the staff view
    kev: list[dict[str, Any]] = []  # Kev questions, answers, probabilities and agreement (S-038, S-054)
    permit: dict[str, Any] | None = None  # data permit of an APPROVE_SPE decision (S-039, S-083)
    sql: str | None = None  # the query behind `answer`, as SQL, for the audit log (hdab.sql)
    sql_matches: bool | None = None  # did running that SQL give exactly `answer`?
    mode: Mode = "Rules only"
