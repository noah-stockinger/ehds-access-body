"""Register and audit log (S-038, S-040, S-042, S-076) in one SQLite file under `$HDAB_VAR`."""

import json
import sqlite3
from datetime import UTC, datetime

from hdab.contracts import Answer, Request
from hdab.data import VAR_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, ts TEXT, request_id TEXT, actor TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, received TEXT, decided TEXT, request TEXT, answer TEXT,
    proposal TEXT, status TEXT, staff TEXT);
CREATE TABLE IF NOT EXISTS cells (request_id TEXT, applicant TEXT, cell TEXT, ids TEXT);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    VAR_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(VAR_DIR / "register.db")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def log(request_id: str, actor: str, action: str, detail: dict | None = None) -> None:
    with connect() as con:
        con.execute("INSERT INTO audit (ts, request_id, actor, action, detail) VALUES (?, ?, ?, ?, ?)",
                    (now(), request_id, actor, action, json.dumps(detail or {}, ensure_ascii=False)))


def events(request_id: str) -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT * FROM audit WHERE request_id = ? ORDER BY id", (request_id,)).fetchall()
    return [dict(r) | {"detail": json.loads(r["detail"])} for r in rows]


def log_query(request_id: str, a: Answer) -> None:
    if a.sql is not None:
        log(request_id, "system", "query_run", {
            "sql": a.sql, "matches_computed_numbers": a.sql_matches,
            "how": "The app computes the numbers with its statistics engine. This SQL states the same query over the same "
                   "tables and was run as a check against those numbers."})


def _log_steps(request_id: str, a: Answer) -> None:
    """Every rule check and model answer as its own entry, in order, for staff to open.

    No numbers: this log is readable before staff release them (S-071).
    """
    for s in a.trace:
        log(request_id, "decision model" if "decision model" in s.rule else "rules", "rule_checked", s.model_dump())
    for k in a.kev:
        log(request_id, k["model"], "model_answered", k)
    if a.plan_text or a.notes or a.unclaimed_words:
        log(request_id, "rules", "definitions_read", {"plan": a.plan_text, "notes": a.notes, "not_understood": a.unclaimed_words})
    for w in a.definition_warnings:
        log(request_id, "rules", "definition_warning", w.model_dump())
    for reason in a.review_reasons:
        log(request_id, "system", "review_reason", {"reason": reason})
    for signal in a.signals:
        log(request_id, "rules", "signal", {"signal": signal})
    log(request_id, "system", "numbers_computed", {"computed": a.answer is not None})
    log_query(request_id, a)


def store(request: Request, answer: Answer, received: str, decided: str) -> None:
    """S-038: request, decision, articles, reason, mode and flags; the app's answer is only a proposal (S-042)."""
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO requests VALUES (?, ?, ?, ?, ?, ?, 'proposed', NULL)",
                    (request.id, received, decided, request.model_dump_json(), answer.model_dump_json(),
                     answer.model_dump_json()))
    log(request.id, "system", "received", {"at": received})
    _log_steps(request.id, answer)
    log(request.id, "system", "decided", {"decision": answer.decision, "articles": answer.articles,
                                          "reason": answer.reason, "mode": answer.mode,
                                          "needs_review": answer.needs_review, "review_reasons": answer.review_reasons,
                                          "kev": answer.kev})


def get(request_id: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        return None
    return dict(row) | {"request": Request.model_validate_json(row["request"]),
                        "answer": Answer.model_validate_json(row["answer"]),
                        "proposal": Answer.model_validate_json(row["proposal"])}


def all_entries() -> list[dict]:
    with connect() as con:
        ids = [r[0] for r in con.execute("SELECT id FROM requests ORDER BY received, id").fetchall()]
    return [get(i) for i in ids]


def set_status(request_id: str, answer: Answer, status: str, staff: str) -> None:
    with connect() as con:
        con.execute("UPDATE requests SET answer = ?, status = ?, staff = ? WHERE id = ?",
                    (answer.model_dump_json(), status, staff, request_id))


def store_cells(request_id: str, applicant: str, cells: dict[str, set[str]]) -> None:
    """S-051: patient IDs behind released counts, never shown; only compared with later requests."""
    with connect() as con:
        con.execute("DELETE FROM cells WHERE request_id = ?", (request_id,))
        con.executemany("INSERT INTO cells VALUES (?, ?, ?, ?)",
                        [(request_id, applicant, c, json.dumps(sorted(ids))) for c, ids in cells.items()])


def earlier_cells(applicant: str, exclude: str) -> list[tuple[str, str, set[str]]]:
    with connect() as con:
        rows = con.execute("SELECT request_id, cell, ids FROM cells WHERE applicant = ? AND request_id != ?",
                           (applicant, exclude)).fetchall()
    return [(r["request_id"], r["cell"], set(json.loads(r["ids"]))) for r in rows]


def clear() -> None:
    """Empty everything, the audit log too; only for the demo reset."""
    with connect() as con:
        con.executescript("DELETE FROM audit; DELETE FROM requests; DELETE FROM cells;")
