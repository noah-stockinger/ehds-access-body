import pytest
from fastapi.testclient import TestClient

from hdab import icd10, register, spe, vocab
from hdab.api import app
from hdab.data import load_requests
from hdab.pipeline import decide

REQUESTS = {r.id: r for r in load_requests()}
client = TestClient(app)


def post(rid):
    return client.post("/requests", json=REQUESTS[rid].model_dump())


def form_of(rid, **changes):
    r = REQUESTS[rid]
    body = {"id": r.id, "applicant": r.applicant.model_dump(), "requested_as": r.requested_as,
            "requested_format": r.requested_format, "purpose": r.purpose, "question": r.question,
            "definitions": r.definitions, "plan_confirmed": True}
    if r.requested_as == "health data access application":
        body["why_statistics_not_enough"] = "Training needs individual-level histories; aggregates are not enough."
    return body | changes


def test_demo_reset_restores_the_seeded_state():
    client.post("/form/submit", json=form_of("R01", id="F-1", warnings_confirmed=True))
    post("R01")
    client.post("/staff/requests/R01/override", json={"staff": "a", "decision": "APPROVE_SPE", "reason": "x", "articles": []})
    assert spe.path("R01").exists() and not spe.path("R05").exists()

    assert client.post("/demo/reset").json()["requests"] == sorted(REQUESTS)

    assert sorted(a["id"] for a in client.get("/applicant/requests").json()) == sorted(REQUESTS)
    assert {a["status"] for a in client.get("/applicant/requests").json()} == {"proposed"}
    assert not spe.path("R01").exists() and spe.path("R05").exists() and not spe.path("F-1").exists()
    actions = [e["action"] for e in client.get("/register/R01/log").json()]
    assert actions[0] == "received" and actions[-1] == "decided" and "confirmed" not in actions


def test_applicant_view_before_and_after_release():
    post("R01")
    v = client.get("/applicant/requests/R01").json()
    assert v["decision"] == "APPROVE_STATISTICAL" and v["reason"] and v["steps"]
    assert v["answer"] is None and "withheld" in v
    assert v["request"]["purpose"] and v["request"]["definitions"]  # the applicant can reread their application
    assert any("re-identify" in d for d in v["duties"]) and any("18 months" in d for d in v["duties"])  # S-041
    assert v["mode"] == "Rules only" and v["ai_note"] is None  # S-055
    assert "review_reasons" not in v and "signals" not in v
    client.post("/staff/requests/R01/confirm", json={"staff": "officer.a"})
    assert client.get("/applicant/requests/R01").json()["answer"]["Wien"]["adults"] == 3247


def test_audit_log_names_the_officer_or_staff():
    post("R01")
    post("R02")
    client.post("/staff/requests/R01/confirm", json={"staff": " Maria Huber "})
    client.post("/staff/requests/R02/confirm", json={})
    assert any(e["actor"] == "Maria Huber" and e["action"] == "confirmed" for e in client.get("/register/R01/log").json())
    assert any(e["actor"] == "staff" and e["action"] == "confirmed" for e in client.get("/register/R02/log").json())


def test_s041_duties_for_spe_and_none_for_reject():
    post("R05")
    post("R02")
    post("R01")
    spe_duties = client.get("/applicant/requests/R05").json()["duties"]
    assert any("Art. 61(5)" in d for d in spe_duties)  # significant findings: record-level access only
    assert not any("Art. 61(5)" in d for d in client.get("/applicant/requests/R01").json()["duties"])
    assert client.get("/applicant/requests/R02").json()["duties"] == []


def test_staff_queue_and_detail():
    post("R02")
    post("R08")
    queue = client.get("/staff/queue").json()
    assert [q["id"] for q in queue] == ["R02", "R08"]
    d = client.get("/staff/requests/R02").json()
    assert d["answer"]["trace"] and d["answer"]["signals"] and d["answer"]["mode"] == "Rules only"
    assert d["log"][0]["action"] == "received"
    assert client.get("/staff/requests/R08").json()["answer"]["plan_text"]


def test_s048_precheck_leaves_register_unchanged():
    r = client.post("/precheck", json=REQUESTS["R05"].model_dump()).json()
    assert r["likely_decision"] == "APPROVE_SPE" and "not the decision" in r["notice"]
    assert register.all_entries() == []
    assert "answer" not in r and "permit" not in r


def test_s045_form_and_api_give_identical_answers():
    via_form = client.post("/form/submit", json=form_of("R05")).json()
    form_answer = register.get("R05")["answer"]
    api_answer = post("R05").json()
    assert via_form["decision"] == "APPROVE_SPE"
    assert form_answer.model_dump(mode="json") == api_answer


def test_s049_unrecognised_reason_gets_statistics_and_goes_to_an_officer():
    why = "We need to follow each treatment sequence from one drug to the next."
    v = client.post("/form/submit", json=form_of("R09", why_statistics_not_enough=why)).json()
    assert v["decision"] == "APPROVE_STATISTICAL" and v["request"]["why_statistics_not_enough"] == why
    answer = register.get("R09")["answer"]
    assert answer.needs_review and any(why in x for x in answer.review_reasons)


def test_downgrade_examples_on_screen_are_accepted_by_the_rules():
    for why in ("to link records of each patient over time", "to train a model on patient histories"):
        v = client.post("/form/submit", json=form_of("R09", why_statistics_not_enough=f"We need individual data {why}.")).json()
        assert v["decision"] == "APPROVE_SPE", why


def test_applicant_list_shows_the_decision_only_once_final():
    post("R09")
    item = lambda: next(a for a in client.get("/applicant/requests").json() if a["id"] == "R09")
    assert item()["decision"] is None
    client.post("/staff/requests/R09/confirm", json={"staff": "a"})
    assert item()["decision"] == "APPROVE_STATISTICAL"


def test_s049_access_application_without_reason_is_refused():
    body = form_of("R05")
    del body["why_statistics_not_enough"]
    r = client.post("/form/submit", json=body)
    assert r.status_code == 422 and "statistics are not enough" in r.text


def test_s057_form_needs_plan_confirmation():
    r = client.post("/form/submit", json=form_of("R01", plan_confirmed=False))
    assert r.status_code == 422
    assert client.post("/form/precheck", json=form_of("R01", plan_confirmed=False)).json()["plan_text"]


def test_cors_allows_the_vite_dev_server():
    r = client.options("/staff/queue", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.skipif(not icd10.XML.exists(), reason="WHO ICD-10 file not installed")
def test_applicant_is_not_told_what_the_data_holds():
    r = REQUESTS["R03"]
    draft = r.model_copy(update={  # I21: WHO knows it, the data does not
        "question": r.question.replace("atrial fibrillation", "acute myocardial infarction"),
        "definitions": [d.replace("Atrial fibrillation", "Acute myocardial infarction").replace("atrial fibrillation", "acute myocardial infarction").replace("I48", "I21") for d in r.definitions]})
    a = decide(draft)
    assert any(x.startswith("Data:") and "occurs nowhere" in x for x in a.review_reasons)  # staff still see it
    got = client.post("/precheck", json=draft.model_dump()).json()
    assert not got["needs_review"] and not got["review_reasons"]
    r03 = client.post("/precheck", json=r.model_dump()).json()
    assert "I48.3" in r03["definition_warnings"][0]["message"] and "this data" not in str(r03)
    assert "this data" in " ".join(decide(r).notes)  # S-070: the answer and the staff view keep it
    post("R03")
    assert "this data" not in str(client.get("/applicant/requests/R03").json()["notes"])


def test_names_do_not_resolve_from_the_data():
    assert vocab.lookup("metformin") == [] and vocab.lookup("unspecified") == []  # both words occur only in the data's columns
    assert vocab.lookup("heart failure")[0].codes == ("I50",)
