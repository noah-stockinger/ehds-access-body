"""Secure processing environment (S-018 to S-020, S-039, S-040, S-081, S-083): one DuckDB file per permit.

shortcut: the user is a name passed by the caller, there is no login; upgrade to real authentication before any
non-synthetic use.
"""

import re
from datetime import date

import duckdb

from hdab import register, rstudio
from hdab.contracts import Request
from hdab.data import VAR_DIR, load_tables
from hdab.plan import Plan
from hdab.stats import Engine

MAX_YEARS = 10  # Art. 68(12)
DOWNLOAD_REFUSED = ("Download refused. Only anonymised results may leave the secure processing environment (Art. 73); "
                    "exporting results is out of scope for this prototype.")
DUTIES = ["Do not try to re-identify any person (Art. 61).",
          "Publish the results within 18 months of the end of the processing (Art. 61).",
          "Credit the European Health Data Space as the source of the data (Art. 61)."]
# Only record-level access can show something about one person's health (docs/findings/article-check.md).
SPE_DUTIES = [*DUTIES, ("Report any significant finding about a person's health in the data to the access body "
                         "(Art. 61(5)).")]


def path(request_id: str):
    return VAR_DIR / "spe" / f"{request_id}.duckdb"


def record_types(request: Request, plan: Plan) -> dict[str, tuple[str, ...] | None]:
    """Record types the request asks for: table → LOINC codes (observations) or None (all rows of that table)."""
    text = f"{request.question} {request.purpose}"
    types: dict[str, tuple[str, ...] | None] = {}
    if re.search(r"\b(conditions?|diagnos[ei]s)\b", text, re.IGNORECASE):
        types["conditions"] = None
    if re.search(r"\b(medications?|prescriptions?|drugs)\b", text, re.IGNORECASE):
        types["medications"] = None
    if re.search(r"\b(observations|measurements|lab (results|values))\b", text, re.IGNORECASE):
        types["observations"] = None
    else:
        obs = [t for t in plan.terms.values() if t.kind == "observation"
               and re.search(rf"\b{re.escape(t.name)}\s+(values?|results?|measurements?)\b", text, re.IGNORECASE)]
        if obs:
            types["observations"] = tuple(c for t in obs for c in t.codes)
    return types


def held_types(request: Request, plan: Plan) -> dict[str, tuple[str, ...] | None]:
    """What the SPE holds. Only an officer's override reaches this with no types named: then all of them (demo)."""
    return record_types(request, plan) or dict.fromkeys(("conditions", "medications", "observations"))


def permit(request: Request, plan: Plan, decided: date) -> dict:
    types = held_types(request, plan)
    years = min(int((request.model_extra or {}).get("duration_years", 1)), MAX_YEARS)
    persons = (request.model_extra or {}).get("authorised_persons") or [request.applicant.name]
    data = [f"{t} (LOINC {', '.join(c)})" if c else t for t, c in types.items()]
    return {
        "permit_id": f"PERMIT-{request.id}",
        "data": data,
        "cohort": plan.cohort.describe() if plan.cohort else None,
        "format": "pseudonymised (patient IDs are pseudonyms)",
        "purpose": request.purpose,
        "authorised_persons": persons,
        "organisation": request.applicant.organisation,
        "valid_from": decided.isoformat(),
        "valid_until": decided.replace(year=decided.year + years).isoformat(),
        "duration_years": years,
        "spe_tools": ["SQL (DuckDB) inside the secure processing environment", "RStudio with no network access"],
        "conditions_of_use": SPE_DUTIES + ["Process the data only inside the secure processing environment (Art. 68(11))."],
        "fees": "not charged in this prototype",
    }


def create(request: Request, plan: Plan) -> dict:
    """Copy the cohort's records of the requested types into `var/spe/<id>.duckdb`, keeping patient IDs (S-018)."""
    ids = set(Engine(plan).cohort())
    t = load_tables()
    file = path(request.id)
    file.parent.mkdir(parents=True, exist_ok=True)
    rstudio.stop(request.id)  # a session must not keep working on the file this replaces
    file.unlink(missing_ok=True)
    with duckdb.connect() as con:
        # The R driver in the RStudio image reads files up to this format, not the newer default of the Python driver.
        con.execute(f"ATTACH '{str(file).replace(chr(39), chr(39) * 2)}' AS spe (STORAGE_VERSION 'v1.4.0')")
        for table, codes in held_types(request, plan).items():
            rows = t[table][t[table]["patient_id"].isin(ids)]
            if codes:
                rows = rows[rows["loinc"].isin(codes)]
            con.register("rows", rows)
            con.execute(f'CREATE TABLE spe."{table}" AS SELECT * FROM rows')
            con.unregister("rows")
        con.execute("DETACH spe")
    register.log(request.id, "system", "spe_created", {"file": file.name, "cohort_size": len(ids)})
    return proof(request.id)


def proof(request_id: str) -> dict:
    """What the demo's proof panel shows: cohort size, tables, and that no opted-out patient is inside."""
    opted_out = set(load_tables()["patients"].query("opted_out")["patient_id"])
    with duckdb.connect(str(path(request_id)), read_only=True) as con:
        tables = [r[0] for r in con.execute("SELECT table_name FROM information_schema.tables ORDER BY 1").fetchall()]
        ids: set[str] = set()
        rows = {}
        for table in tables:
            ids |= {r[0] for r in con.execute(f'SELECT DISTINCT patient_id FROM "{table}"').fetchall()}
            rows[table] = con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    return {"cohort_size": len(ids), "tables": rows, "opted_out_ids_inside": len(ids & opted_out)}


def allowed(permit_: dict, user: str) -> bool:
    return user in permit_["authorised_persons"]


def delete(request_id: str, actor: str) -> None:
    if rstudio.stop(request_id):
        register.log(request_id, actor, "spe_rstudio_stopped")
    path(request_id).unlink(missing_ok=True)
    register.log(request_id, actor, "spe_deleted")
