"""API tests. They run in demo mode or with a fake Claude client, so no API key or network is needed."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.config import settings
from app.demo import DemoChat
from app.llm import ClaudeChat, split_sources
from app.main import create_app

SESSION = "test-session-0001"


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    """Write saved questions/contacts to a temp folder and never send real notifications."""
    monkeypatch.setattr(storage, "settings", SimpleNamespace(data_dir=tmp_path, pushover_token="", pushover_user=""))
    return tmp_path


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# ---------------------------------------------------------------- demo mode

@pytest.fixture
def demo_client():
    return TestClient(create_app(DemoChat()))


def test_profile_and_health(demo_client):
    assert demo_client.get("/api/health").json() == {"status": "ok", "mode": "demo"}
    p = demo_client.get("/api/profile").json()
    assert p["name"] and p["suggested_questions"] and p["mode"] == "demo"


def test_index_served(demo_client):
    r = demo_client.get("/")
    assert r.status_code == 200 and "/static/app.js" in r.text


def test_known_question_has_sources(demo_client):
    r = demo_client.post("/api/chat", json={"session_id": SESSION, "message": "What's their background?"})
    data = r.json()
    assert r.status_code == 200
    assert data["sources"] == ["resume.md"] and not data["question_logged"]


def test_unknown_question_is_logged(demo_client, tmp_data_dir):
    r = demo_client.post("/api/chat", json={"session_id": SESSION, "message": "What's their salary expectation?"})
    assert r.json()["question_logged"] is True
    saved = read_jsonl(tmp_data_dir / "unknown_questions.jsonl")
    assert saved[0]["question"] == "What's their salary expectation?"


@pytest.mark.parametrize("body", [
    {"session_id": "bad id!", "message": "hi"},
    {"session_id": SESSION, "message": "   "},
])
def test_chat_validation(demo_client, body):
    assert demo_client.post("/api/chat", json=body).status_code == 422


def test_message_too_long(demo_client):
    r = demo_client.post("/api/chat", json={"session_id": SESSION, "message": "x" * 1001})
    assert r.status_code == 413


def test_contact_saved_and_validated(demo_client, tmp_data_dir):
    ok = demo_client.post("/api/contact", json={"name": "Priya Shah", "email": "priya@fieldstone.io", "company": "Fieldstone"})
    assert ok.status_code == 200
    assert read_jsonl(tmp_data_dir / "contacts.jsonl")[0]["email"] == "priya@fieldstone.io"
    bad = demo_client.post("/api/contact", json={"name": "Priya", "email": "not-an-email"})
    assert bad.status_code == 422


def test_rate_limit():
    client = TestClient(create_app(DemoChat(), rate_limit_per_minute=3))
    codes = [client.post("/api/chat", json={"session_id": SESSION, "message": "skills"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


# ---------------------------------------------------------------- Claude engine with a fake client

def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(name, args, id_="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=args, id=id_)


class FakeClient:
    """Returns scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def resp(stop_reason, *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def test_claude_answer_with_sources():
    fake = FakeClient([resp("end_turn", text_block("Alex has 7 years in analytics.\n[sources: resume.md]"))])
    result = ClaudeChat(client=fake).chat(SESSION, "Background?")
    assert result.reply == "Alex has 7 years in analytics."
    assert result.sources == ["resume.md"]
    call = fake.calls[0]
    assert call["model"] == settings.model
    assert call["fallbacks"] == "default"
    # Documents block carries the cache breakpoint and comes last in the system prompt.
    assert call["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "resume.md" in call["system"][-1]["text"]


def test_claude_unknown_question_tool_loop(tmp_data_dir):
    fake = FakeClient([
        resp("tool_use", text_block("I don't have that."), tool_block("record_unknown_question", {"question": "Salary?"})),
        resp("end_turn", text_block("I don't have that information. I've passed your question on.")),
    ])
    engine = ClaudeChat(client=fake)
    result = engine.chat(SESSION, "Salary?")
    assert result.question_logged and not result.contact_saved
    assert read_jsonl(tmp_data_dir / "unknown_questions.jsonl")[0]["question"] == "Salary?"
    # Second request carries the assistant turn and a single user turn with the tool result.
    second = fake.calls[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[2]["content"][0]["type"] == "tool_result"


def test_claude_contact_tool_rejects_bad_email(tmp_data_dir):
    fake = FakeClient([
        resp("tool_use", tool_block("record_contact", {"name": "Sam", "email": "nope", "company": "", "note": ""})),
        resp("end_turn", text_block("Could you double-check your email address?")),
    ])
    result = ClaudeChat(client=fake).chat(SESSION, "I'm Sam, email nope")
    assert not result.contact_saved
    assert fake.calls[1]["messages"][-1]["content"][0]["is_error"] is True
    assert read_jsonl(tmp_data_dir / "contacts.jsonl") == []


def test_claude_refusal_rolls_back_history():
    fake = FakeClient([resp("refusal"), resp("end_turn", text_block("Alex is in Toronto."))])
    engine = ClaudeChat(client=fake)
    engine.chat(SESSION, "something declined")
    engine.chat(SESSION, "Where are they based?")
    # The declined turn was removed, so the next request starts clean.
    assert [m["content"] for m in fake.calls[1]["messages"]] == ["Where are they based?"]


def test_split_sources():
    assert split_sources("Answer.\n[Sources: a.md, b.md]") == ("Answer.", ["a.md", "b.md"])
    assert split_sources("No sources here.") == ("No sources here.", [])
