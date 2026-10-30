"""RStudio in the SPE (M-29, D-11): who may open it, how the container is locked down, and that revoking ends it."""

import pytest
from fastapi.testclient import TestClient

from hdab import rstudio, spe
from hdab.api import app
from hdab.data import load_requests

R05 = next(r for r in load_requests() if r.id == "R05")
APPLICANT = R05.applicant.name
client = TestClient(app)


@pytest.fixture
def docker(monkeypatch):
    """Fake docker: records every call; `current` is what `docker inspect` of the session container answers."""
    calls = []
    state = {"current": ""}

    def fake(*args, check=True):
        calls.append(args)
        return state["current"] if args[0] == "inspect" else ""

    monkeypatch.setattr(rstudio, "_docker", fake)
    monkeypatch.setattr(rstudio, "_wait_ready", lambda: None)
    calls_state = type("Docker", (), {"calls": calls, "state": state})
    return calls_state


def confirmed():
    client.post("/requests", json=R05.model_dump())
    client.post("/staff/requests/R05/confirm", json={"staff": "officer.a"})


def log():
    return [(e["actor"], e["action"]) for e in client.get("/register/R05/log").json()]


def test_session_has_no_network_and_reads_the_data_read_only(docker, tmp_path):
    assert rstudio.start("R05", tmp_path / "R05.duckdb") == {"url": rstudio.URL}
    run = next(c for c in docker.calls if c[0] == "run" and rstudio.IMAGE in c)
    assert run[run.index("--network") + 1] == "none"
    assert any(a.startswith("type=bind") and a.endswith(",readonly") for a in run)
    assert "DISABLE_AUTH=true" in run
    proxy = next(c for c in docker.calls if c[0] == "run" and rstudio.PROXY_IMAGE in c)
    assert proxy[proxy.index("-p") + 1].startswith("127.0.0.1:")  # never on all interfaces (S-032 style)


def test_second_click_keeps_the_running_session(docker, tmp_path):
    docker.state["current"] = "R05 true"
    rstudio.start("R05", tmp_path / "R05.duckdb")
    assert not [c for c in docker.calls if c[0] in ("run", "rm")]


def test_another_permit_replaces_the_session(docker, tmp_path):
    docker.state["current"] = "R09 true"
    rstudio.start("R05", tmp_path / "R05.duckdb")
    assert ("rm", "-f", rstudio.NAME, rstudio.PROXY) in docker.calls


@pytest.mark.parametrize("bad", ["../x", "a,dst=/etc", "", "-v"])
def test_unsafe_request_id_never_reaches_docker(docker, tmp_path, bad):
    with pytest.raises(rstudio.Unavailable):
        rstudio.start(bad, tmp_path / "x.duckdb")
    assert not docker.calls


def test_s040_only_permit_holders_after_confirm_and_logged(docker):
    client.post("/requests", json=R05.model_dump())
    assert client.post("/spe/R05/rstudio", params={"user": APPLICANT}).status_code == 403  # S-076: not confirmed yet
    client.post("/staff/requests/R05/confirm", json={"staff": "officer.a"})
    assert client.post("/spe/R05/rstudio", params={"user": "mallory"}).status_code == 403
    assert not [c for c in docker.calls if c[0] == "run"]
    assert client.post("/spe/R05/rstudio", params={"user": APPLICANT}).status_code == 200
    assert ("mallory", "spe_rstudio_refused") in log() and (APPLICANT, "spe_rstudio_opened") in log()


def test_s076_override_to_reject_ends_the_session(docker):
    confirmed()
    docker.state["current"] = "R05 true"
    docker.calls.clear()
    r = client.post("/staff/requests/R05/override", json={"staff": "officer.a", "decision": "REJECT", "reason": "x", "articles": ["54"]})
    assert r.status_code == 200 and ("rm", "-f", rstudio.NAME, rstudio.PROXY) in docker.calls
    assert ("officer.a", "spe_rstudio_stopped") in log() and not spe.path("R05").exists()


def test_override_does_not_end_another_permits_session(docker):
    confirmed()
    docker.state["current"] = "R09 true"
    docker.calls.clear()
    client.post("/staff/requests/R05/override", json={"staff": "officer.a", "decision": "REJECT", "reason": "x", "articles": ["54"]})
    assert not [c for c in docker.calls if c[0] == "rm"]


def test_no_docker_answers_503_and_an_override_still_works(monkeypatch):
    def no_docker(*args, check=True):
        raise rstudio.Unavailable("Docker is not available")

    confirmed()
    monkeypatch.setattr(rstudio, "_docker", no_docker)
    assert client.post("/spe/R05/rstudio", params={"user": APPLICANT}).status_code == 503
    assert client.post("/staff/requests/R05/override", json={"staff": "a", "decision": "REJECT", "reason": "x", "articles": ["54"]}).status_code == 200


def test_spe_file_is_in_a_format_the_r_driver_reads():
    confirmed()
    version = int.from_bytes(spe.path("R05").read_bytes()[12:20], "little")
    assert version <= 67  # the R driver of docker/rstudio (duckdb 1.4.1) reads storage versions 64 to 67
