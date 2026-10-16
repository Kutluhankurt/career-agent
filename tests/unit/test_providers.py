"""Provider adapters, with the vendor SDK replaced by a recorder (no network)."""

import sys
import types
from types import SimpleNamespace

import pytest

from career.ai.base import AIError
from career.ai.claude import ClaudeProvider
from career.ai.factory import get_provider
from career.ai.local import LocalProvider
from career.analysis.context import ContextPacket
from career.config.settings import AISettings

CTX = ContextPacket(session_id="s", date="2026-10-16", time="09:00-10:00", active_minutes=60, applications={"VS Code": 60},
                    window_titles=[], sites=[], workspaces=["supervisor"], files=["a.py"], commands=[], tickets=[])
ANSWER = '{"activity": "Supervisor development", "project": null, "category": "Development", "confidence": 0.8, "skills": ["Python"], "evidence": ["a.py"]}'


class Recorder:
    def __init__(self, response):
        self.response, self.kwargs = response, None
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def claude_with(response):
    p = ClaudeProvider(api_key="test")
    rec = Recorder(response)
    p._client = lambda: rec
    return p, rec


def test_claude_request_shape_and_parsing():
    p, rec = claude_with(SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=ANSWER)]))
    result = p.analyze(CTX)
    assert result.activity == "Supervisor development"
    k = rec.kwargs
    assert k["model"] == "claude-opus-5-5"
    assert k["output_config"]["effort"] == "low"
    assert k["output_config"]["format"]["type"] == "json_schema"
    assert k["fallbacks"] == "default" and k["betas"] == ["server-side-fallback-2026-07-01"]
    assert k["messages"][0]["role"] == "user" and "supervisor" in k["messages"][0]["content"]
    assert "Never invent" in k["system"]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_claude_refusal_and_truncation_raise(stop):
    p, _ = claude_with(SimpleNamespace(stop_reason=stop, content=[]))
    with pytest.raises(AIError):
        p.analyze(CTX)


def test_local_provider_uses_ollama_chat(monkeypatch):
    import httpx

    calls = {}

    def fake_post(url, json, timeout):
        calls["url"], calls["body"] = url, json
        return httpx.Response(200, json={"message": {"content": ANSWER}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    result = LocalProvider(url="http://127.0.0.1:11434").analyze(CTX)
    assert result.skills == ["Python"]
    assert calls["url"].endswith("/api/chat")
    assert calls["body"]["format"]["type"] == "object" and calls["body"]["stream"] is False


def test_local_provider_unavailable_without_server(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("no")

    monkeypatch.setattr(httpx, "get", boom)
    assert LocalProvider().available() is False


def test_factory_and_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    p = get_provider(AISettings(provider="claude"))
    assert p.name == "claude" and p.api_key == "sk-ant-test"
    assert get_provider(AISettings(provider="none")) is None
    assert get_provider(AISettings(provider="openai", model="gpt-x")).model == "gpt-x"


def test_openai_adapter(monkeypatch):
    sent = {}

    class Completions:
        def create(self, **kw):
            sent.update(kw)
            msg = SimpleNamespace(content=ANSWER, refusal=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    class Client:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(completions=Completions())

    fake = types.ModuleType("openai")
    fake.OpenAI = Client
    fake.AuthenticationError = type("AuthenticationError", (Exception,), {})
    fake.APIError = type("APIError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "openai", fake)
    from career.ai.openai import OpenAIProvider

    assert OpenAIProvider(api_key="k").analyze(CTX).category == "Development"
    assert sent["response_format"]["json_schema"]["strict"] is True
