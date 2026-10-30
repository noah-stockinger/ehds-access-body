"""S-087: the writing help. The model is mocked; tests need no GPU."""

from types import SimpleNamespace

import anthropic
import pytest
from fastapi.testclient import TestClient

from hdab import assist, register
from hdab.api import app
from hdab.assist import Draft

client = TestClient(app)
APPLICANT = {"name": "Dr. T", "organisation": "Uni Graz", "country": "AT"}
GOOD = ["COPD = any condition with an ICD-10 code starting with J44.", "Report per region: patients with COPD."]
BAD = ["COPD means the lung thing", "gimme numbers"]


def body(purpose="Public health planning for lung disease.", question="How many patients have COPD per region?", **more):
    return {"applicant": APPLICANT, "requested_as": "health data request", "purpose": purpose, "question": question,
            "definitions": []} | more


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("ASSIST_ENABLED", "true")


def mock(monkeypatch, *drafts):
    calls = []

    def chat(user):
        calls.append(user)
        return drafts[min(len(calls), len(drafts)) - 1]
    monkeypatch.setattr(assist, "_chat", chat)
    return calls


def draft(definitions, question="How many patients have COPD per region?"):
    return Draft(message="I added the definitions.", question=question, definitions=definitions)


def test_off_by_default_sends_nothing(monkeypatch):
    monkeypatch.delenv("ASSIST_ENABLED", raising=False)
    calls = mock(monkeypatch, draft(GOOD))
    assert client.post("/form/assist", json=body()).status_code == 503
    assert client.get("/form/assist").json()["enabled"] is False
    assert not calls


def test_model_down_is_a_clean_503_and_the_check_still_works(on, monkeypatch):
    monkeypatch.setenv("ASSIST_PROVIDER", "ollama")
    monkeypatch.setenv("ASSIST_URL", "http://127.0.0.1:9")
    assert client.post("/form/assist", json=body()).status_code == 503
    form = body(definitions=GOOD, plan_confirmed=False)
    assert client.post("/form/precheck", json=form).status_code == 200


def test_suggestion_is_checked_by_the_rules_and_keeps_the_purpose(on, monkeypatch):
    calls = mock(monkeypatch, draft(GOOD))
    got = client.post("/form/assist", json=body()).json()
    assert len(calls) == 1
    assert got["suggestion"] == {"question": "How many patients have COPD per region?", "definitions": GOOD}
    assert "purpose" not in got["suggestion"]
    assert got["check"]["unclaimed_words"] == [] and got["left_out"] == []


def test_rejected_draft_gets_no_rewrite_and_no_model_call(on, monkeypatch):
    calls = mock(monkeypatch, draft(GOOD))
    got = client.post("/form/assist", json=body(purpose="We set insurance premiums from diabetes risk.")).json()
    assert got["check"]["likely_decision"] == "REJECT"
    assert got["suggestion"] is None and not calls


def test_unreadable_draft_gets_one_repair_and_the_better_one_is_kept(on, monkeypatch):
    calls = mock(monkeypatch, draft(BAD), draft(GOOD))
    got = client.post("/form/assist", json=body()).json()
    assert len(calls) == 2 and got["suggestion"]["definitions"] == GOOD


def test_a_worse_repair_does_not_replace_the_first_draft(on, monkeypatch):
    mock(monkeypatch, draft(GOOD, question="How many patients have COPD or asthma per region?"), draft([]))
    assert client.post("/form/assist", json=body()).json()["suggestion"]["definitions"] == GOOD


def test_a_readable_draft_beats_an_unreadable_one_with_fewer_words_left_out(on, monkeypatch):
    mock(monkeypatch, draft(GOOD, question="How many patients have COPD, asthma, gout or flu per region?"), draft(GOOD + ["gimme"]))
    assert client.post("/form/assist", json=body()).json()["suggestion"]["definitions"] == GOOD


@pytest.mark.parametrize("broken", [BAD, GOOD[:1]], ids=["unreadable", "no report line"])
def test_a_draft_that_stays_broken_is_never_offered(on, monkeypatch, broken):
    calls = mock(monkeypatch, draft(broken))
    got = client.post("/form/assist", json=body(definitions=["my own line"])).json()
    assert len(calls) == 2 and got["suggestion"] is None
    assert got["check"]["unclaimed_parts"] == ["my own line"]  # the findings are about the applicant's text, not the hidden draft


@pytest.mark.parametrize("messy", [[f"- {GOOD[0]}", f"- {GOOD[1]}"], [f"1. {GOOD[0]}", f"2) {GOOD[1]}"], ["\n".join(GOOD)],
                                   [GOOD[0].replace("COPD", "**COPD**"), GOOD[1]]],
                         ids=["bullets", "numbers", "line break inside an item", "bold"])
def test_suggestion_fits_the_box_one_definition_per_line(on, monkeypatch, messy):
    calls = mock(monkeypatch, draft(messy))
    got = client.post("/form/assist", json=body()).json()
    assert len(calls) == 1 and got["suggestion"]["definitions"] == GOOD
    assert got["check"]["unclaimed_parts"] == []


def test_the_repair_is_told_a_report_line_is_missing(on, monkeypatch):
    calls = mock(monkeypatch, draft(GOOD[:1]), draft(GOOD))
    assert client.post("/form/assist", json=body()).json()["suggestion"]["definitions"] == GOOD
    assert "no report line" in calls[1]


def test_left_out_names_dropped_conditions_and_changed_numbers():
    from hdab.contracts import Request
    r = Request(id="x", submitted="2026-10-30", applicant=APPLICANT, requested_as="health data request",
                requested_format="anonymised statistics", purpose="p", question="q", definitions=["Age groups 18-64 and 65+."])
    d = draft(["Women = sex 'female'.", "Age bands on 31 December 2025: 18-49, 50-64, 65+."],
              question="Mean BMI of women with breast cancer?")
    missing = assist.left_out(r, d)
    assert {"breast", "cancer", "bmi", "18-64"} <= set(missing) and "65+" not in missing and "women" not in missing


def test_empty_answer_is_no_suggestion(on, monkeypatch):
    mock(monkeypatch, draft([]))
    assert client.post("/form/assist", json=body()).json()["suggestion"] is None


def test_register_notes_when_the_applicant_took_a_suggestion():
    form = body(definitions=GOOD, id="ASSIST-LOG", plan_confirmed=True, assist_model="qwen3.8:27b")
    assert client.post("/form/submit", json=form).status_code == 200, form
    assert any("AI help" in e["action"] for e in register.events("ASSIST-LOG"))


class FakeClaude:
    """Stands in for `anthropic.Anthropic`, so no test reaches the API."""

    def __init__(self, stop="end_turn", text='{"message": "m", "question": "q", "definitions": ["d"]}', error=None):
        block = SimpleNamespace(type="text", text=text)
        self.response = SimpleNamespace(stop_reason=stop, content=[block], model="claude-other")
        self.error = error
        self.sent = {}
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def __call__(self, **_):
        return self

    def create(self, **kw):
        self.sent = kw
        if self.error:
            raise self.error
        return self.response


def test_claude_is_the_default_and_gets_only_the_text_it_was_given(monkeypatch):
    monkeypatch.delenv("ASSIST_PROVIDER", raising=False)
    monkeypatch.delenv("ASSIST_MODEL", raising=False)
    fake = FakeClaude()
    monkeypatch.setattr(assist.anthropic, "Anthropic", fake)
    got = assist._chat("DRAFT")
    assert fake.sent["model"] == "claude-opus-5-5" and fake.sent["messages"] == [{"role": "user", "content": "DRAFT"}]
    assert got.definitions == ["d"] and got.model == "claude-other"  # the answering model is what the register names


@pytest.mark.parametrize("fake", [FakeClaude(stop="refusal"), FakeClaude(stop="max_tokens"), FakeClaude(text="not json"),
                                  FakeClaude(error=anthropic.AnthropicError("no key"))])
def test_claude_failure_is_unavailable_not_a_crash(monkeypatch, fake):
    monkeypatch.delenv("ASSIST_PROVIDER", raising=False)
    monkeypatch.setattr(assist.anthropic, "Anthropic", fake)
    with pytest.raises(assist.Unavailable):
        assist._chat("DRAFT")


def test_ollama_stays_selectable(monkeypatch):
    monkeypatch.setenv("ASSIST_PROVIDER", "ollama")
    monkeypatch.delenv("ASSIST_MODEL", raising=False)
    assert assist.model() == "qwen3.8:27b"
