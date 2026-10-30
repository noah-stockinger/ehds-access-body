from datetime import date

import duckdb
from fastapi.testclient import TestClient

from hdab import spe
from hdab.api import app
from hdab.data import load_requests, load_tables

R05 = next(r for r in load_requests() if r.id == "R05")
client = TestClient(app)
APPLICANT = R05.applicant.name


def submit_and_confirm():
    answer = client.post("/requests", json=R05.model_dump()).json()
    client.post("/staff/requests/R05/confirm", json={"staff": "officer.a"})
    return answer


def test_s018_s019_spe_holds_exactly_the_cohort_and_requested_types():
    answer = submit_and_confirm()
    assert answer["answer"] == {"cohort_size": 1152}  # S-019: exact, not masked
    with duckdb.connect(str(spe.path("R05")), read_only=True) as con:
        tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        assert tables == {"conditions", "medications", "observations"}
        assert con.execute("SELECT DISTINCT loinc FROM observations").fetchall() == [("4548-4",)]
        ids = {r[0] for r in con.execute(
            "SELECT patient_id FROM conditions UNION SELECT patient_id FROM medications "
            "UNION SELECT patient_id FROM observations").fetchall()}
    assert len(ids) == 1152
    opted_out = set(load_tables()["patients"].query("opted_out")["patient_id"])
    assert not ids & opted_out  # S-008


def test_s039_s083_permit_fields():
    permit = submit_and_confirm()["permit"]
    for key in ["data", "format", "purpose", "authorised_persons", "valid_from", "valid_until", "duration_years",
                "spe_tools", "conditions_of_use", "fees"]:
        assert permit[key]
    assert permit["authorised_persons"] == [APPLICANT]
    assert 1 <= permit["duration_years"] <= 10
    assert date.fromisoformat(permit["valid_until"]) <= date.fromisoformat(permit["valid_from"]).replace(
        year=date.fromisoformat(permit["valid_from"]).year + 10)
    assert "pseudonymised" in permit["format"] and permit["fees"] == "not charged in this prototype"


def test_s040_unlisted_user_refused_and_logged():
    submit_and_confirm()
    assert client.get("/spe/R05", params={"user": "mallory"}).status_code == 403
    r = client.get("/spe/R05", params={"user": APPLICANT})
    assert r.status_code == 200 and r.json()["proof"] == {
        "cohort_size": 1152, "tables": r.json()["proof"]["tables"], "opted_out_ids_inside": 0}
    actions = [(e["actor"], e["action"]) for e in client.get("/register/R05/log").json()]
    assert ("mallory", "spe_open_refused") in actions and (APPLICANT, "spe_opened") in actions


def test_s020_s081_download_always_refused_with_art73_text_and_logged():
    submit_and_confirm()
    r = client.get("/spe/R05/download", params={"user": APPLICANT})
    assert r.status_code == 403 and "Art. 73" in r.json()["detail"] and "out of scope" in r.json()["detail"]
    assert any(e["action"] == "spe_download_refused" for e in client.get("/register/R05/log").json())


def test_s076_spe_closed_until_staff_confirm():
    client.post("/requests", json=R05.model_dump())
    assert client.get("/spe/R05", params={"user": APPLICANT}).status_code == 403


def test_s018_spe_without_a_cohort_cannot_be_confirmed():
    draft = R05.model_copy(update={"id": "R05-NC", "definitions": [d for d in R05.definitions if not d.startswith("Cohort") and "size of the cohort" not in d]})
    assert any(r.startswith("S-018: ") for r in client.post("/precheck", json=draft.model_dump()).json()["review_reasons"])
    answer = client.post("/requests", json=draft.model_dump()).json()
    assert answer["decision"] == "APPROVE_SPE" and answer["permit"] is None
    r = client.post("/staff/requests/R05-NC/confirm", json={"staff": "officer.a"})
    assert r.status_code == 409 and "No data permit" in r.json()["detail"]
    assert client.get("/staff/requests/R05-NC").json()["status"] == "proposed"
    assert not any(e["action"] == "confirmed" for e in client.get("/register/R05-NC/log").json())
