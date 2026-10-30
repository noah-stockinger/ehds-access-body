import pytest

from hdab import kev, pipeline, register, spe, views
from hdab.data import load_requests

REQUESTS = {r.id: r for r in load_requests()}


@pytest.mark.parametrize("rid", sorted(REQUESTS))
def test_s038_s055_register_entry_for_each_request(rid):
    pipeline.submit(REQUESTS[rid])
    entry = register.get(rid)
    assert entry["received"] and entry["decided"] and entry["status"] == "proposed"
    a = entry["answer"]
    assert a.decision and a.articles and a.reason and a.mode == "Rules only"
    decided = next(e for e in register.events(rid) if e["action"] == "decided")["detail"]
    assert decided["decision"] == a.decision and decided["mode"] == "Rules only"


def test_s071_flagged_answer_shows_no_numbers_to_applicant_until_confirm():
    r = REQUESTS["R01"].model_copy(update={"definitions": REQUESTS["R01"].definitions + ["Flurble the wibbles."]})
    pipeline.submit(r)
    assert views.applicant(register.get("R01"))["answer"] is None


def test_s076_numbers_released_only_after_confirm():
    pipeline.submit(REQUESTS["R01"])
    assert views.applicant(register.get("R01"))["answer"] is None
    assert views.staff(register.get("R01"))["answer"]["answer"] is not None  # staff see the result at once
    pipeline.confirm("R01", "officer.a")
    assert views.applicant(register.get("R01"))["answer"]["Wien"]["adults"] == 3247
    assert any(e["actor"] == "officer.a" and e["action"] == "confirmed" for e in register.events("R01"))


def test_override_to_spe_creates_a_working_spe_without_opted_out_patients():
    pipeline.submit(REQUESTS["R01"])  # names neither a cohort nor record types
    new = pipeline.override("R01", "officer.b", "APPROVE_SPE", "Records are needed.", ["68"])
    assert new.permit["permit_id"] == "PERMIT-R01" and new.answer["cohort_size"] > 0
    proof = spe.proof("R01")
    assert proof["tables"]["conditions"] > 0 and proof["opted_out_ids_inside"] == 0
    assert any(e["action"] == "spe_created" for e in register.events("R01"))


def test_s042_s076_override_of_r05_deletes_spe_and_logs_who_and_when():
    pipeline.submit(REQUESTS["R05"])
    assert spe.path("R05").exists()
    new = pipeline.override("R05", "officer.b", "REJECT", "Purpose not sufficiently specified.", [])
    assert new.decision == "REJECT" and new.answer is None and new.permit is None
    assert not spe.path("R05").exists()
    deleted = next(e for e in register.events("R05") if e["action"] == "spe_deleted")
    assert deleted["actor"] == "officer.b" and deleted["ts"]
    entry = register.get("R05")
    assert entry["status"] == "overridden" and entry["proposal"].decision == "APPROVE_SPE"


def fake_model(payload):
    """Every model question answered: nothing prohibited, the rest no."""
    (key, q), = payload["questions"].items()
    if q["type"] == "choice":
        options = list(q["criteria"])
        answer = {"type": "choice", "choice": options[-1], "confidence": 0.9, "probabilities": dict.fromkeys(options, 0.1)}
    else:
        answer = {"type": "noul", "noul": 0.1}
    return {"answers": {key: answer}, "model": "fake-1"}


def test_s038_every_rule_step_and_model_answer_is_its_own_log_entry(monkeypatch):
    monkeypatch.setenv("KEV_MODE", "led")
    monkeypatch.setattr(kev, "post", fake_model)
    answer = pipeline.submit(REQUESTS["R05"])
    events = register.events("R05")
    rules_logged = [e["detail"] for e in events if e["action"] == "rule_checked"]
    assert rules_logged == [s.model_dump() for s in answer.trace] and rules_logged
    models = [e for e in events if e["action"] == "model_answered"]
    assert len(models) == len(answer.kev) >= 6 and {e["actor"] for e in models} == {"fake-1"}
    k1 = next(e["detail"] for e in models if e["detail"]["question"] == "K1_category")
    assert "Art. 54" in k1["instructions"] and REQUESTS["R05"].purpose in k1["sent"] and k1["answer"]["probabilities"]
    assert events[-1]["action"] == "decided"


def test_s071_the_log_never_holds_numbers():
    answer = pipeline.submit(REQUESTS["R01"])
    assert answer.answer["Wien"]["adults"] == 3247
    assert not [e for e in register.events("R01") if "3247" in str(e["detail"])]
    assert next(e for e in register.events("R01") if e["action"] == "numbers_computed")["detail"] == {"computed": True}


def test_a_rejection_logs_that_no_numbers_were_computed():
    pipeline.submit(REQUESTS["R02"])
    assert next(e for e in register.events("R02") if e["action"] == "numbers_computed")["detail"] == {"computed": False}
