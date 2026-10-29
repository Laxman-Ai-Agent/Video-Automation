"""Unit tests for multi-provider LLM client and API endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import llm_client

client = TestClient(app)
_REAL_CLAUDE_CLI = llm_client._call_claude_cli      # conftest swaps the module attribute for a fake in every test


@pytest.fixture(autouse=True)
def private_settings(tmp_path, monkeypatch):
    """The settings and status files are this test's own: a test must never change the provider the real pipeline uses (config/llm_settings.json)."""
    monkeypatch.setattr(llm_client, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(llm_client, "CONFIG_FILE", tmp_path / "llm_settings.json")
    monkeypatch.setattr(llm_client, "STATUS_FILE", tmp_path / "llm_status.json")


def test_llm_get_settings():
    res = client.get("/llm/settings")
    assert res.status_code == 200
    data = res.json()
    assert "active_provider" in data
    assert "available_providers" in data
    assert len(data["available_providers"]) >= 5


def test_llm_update_settings():
    res = client.post("/llm/settings", json={"provider": "gemini", "model": "gemini-2.0-flash", "api_key": "test-key-123"})
    assert res.status_code == 200
    data = res.json()
    assert data["active_provider"] == "gemini" and data["active_model"] == "gemini-2.0-flash"
    assert llm_client.load_settings()["provider"] == "gemini"                                   # written to this test's own settings file


def test_a_provider_without_a_key_does_not_silently_fallback(monkeypatch):
    """Under Model Lock, a provider without a key stays locked to that provider and does NOT silently switch to Claude CLI."""
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude" if t == "claude" else None)
    for k in ("LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    res = client.post("/llm/settings", json={"provider": "gemini", "model": "gemini-3.5-flash"}).json()
    assert res["active_provider"] == "gemini"
    assert res["connection_status"] == "offline"
    assert "API key is missing" in res["status_message"]


def test_llm_test_connection_invalid_key_tests_the_provider_it_names(monkeypatch):
    """The key typed in for the test counts before the Claude CLI fallback: testing a Gemini key reaches Gemini (faked here), never the CLI."""
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude" if t == "claude" else None)
    seen = []

    def gemini(prompt, system, model, key, timeout=30):
        seen.append(key)
        raise llm_client.LlmError("Gemini API error: API key not valid")
    monkeypatch.setattr(llm_client, "_call_gemini", gemini)
    res = client.post("/llm/test", json={"provider": "gemini", "model": "gemini-2.0-flash", "api_key": "invalid_test_key_123"})
    assert res.status_code == 200
    data = res.json()
    assert seen == ["invalid_test_key_123"] and data["ok"] is False and data["provider"] == "gemini" and "API key" in data["message"]


def test_llm_generate_text_unsupported():
    try:
        llm_client.generate_text("hi", provider="invalid_provider")
        assert False, "Should have raised LlmError"
    except llm_client.LlmError as e:
        assert "Unknown or unsupported" in str(e)


# --- Connect page: detect what this machine offers, connect automatically, keep the header status true ---

ALL_KEYS = ("LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "DEEPSEEK_API_KEY")


@pytest.fixture
def bare_machine(monkeypatch):
    """No API key in the environment, no Claude CLI, no Antigravity, no Ollama."""
    for k in ALL_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: None)
    monkeypatch.setattr(llm_client, "_find_agy_exe", lambda: None)      # it is also found under ~/.gemini/bin, not only on PATH
    monkeypatch.setattr(llm_client, "_ollama_reachable", lambda: False)


def _with_claude_cli(monkeypatch, reply="ok"):
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude" if t == "claude" else None)
    monkeypatch.setattr(llm_client, "_call_claude_cli", lambda prompt, system, timeout, model=None: reply)


def test_detect_lists_what_this_machine_offers_without_revealing_a_key(bare_machine, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret_value_123")
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude" if t == "claude" else None)
    res = client.get("/llm/detect")
    assert res.status_code == 200
    assert [o["id"] for o in res.json()["options"]] == ["claude_cli", "groq"]
    assert "gsk_secret_value_123" not in res.text


def test_claude_code_is_tried_before_antigravity_and_an_api_key(bare_machine, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude" if t == "claude" else None)
    monkeypatch.setattr(llm_client, "_find_agy_exe", lambda: "/fake/agy")
    assert [o["id"] for o in client.get("/llm/detect").json()["options"]] == ["claude_cli", "antigravity", "groq"]
    assert llm_client.resolve_provider_config()[0] == "claude_cli"                    # provider `auto` follows the same order
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: None)
    assert llm_client.resolve_provider_config()[0] == "antigravity"


def test_detect_on_a_bare_machine_finds_nothing(bare_machine):
    assert client.get("/llm/detect").json()["options"] == []


def test_auto_connect_keeps_the_first_provider_that_answers(bare_machine, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude" if t == "claude" else None)
    calls = []

    def fake_test(provider=None, model=None, api_key=None, base_url=None):
        calls.append((provider, model, base_url))
        ok = provider == "groq"
        return {"ok": ok, "provider": provider, "model": model, "latency_ms": 5, "message": "up" if ok else "not signed in"}
    monkeypatch.setattr(llm_client, "test_connection", fake_test)
    data = client.post("/llm/auto-connect").json()
    assert data["connected"] is True and data["provider"] == "groq"
    assert [(r["id"], r["ok"]) for r in data["results"]] == [("claude_cli", False), ("groq", True)]
    assert llm_client.load_settings()["provider"] == "groq"
    assert calls[1] == ("groq", "llama-3.3-70b-versatile", "")          # that provider's own default model and URL, never a leftover of the previous one


def test_auto_connect_records_a_verified_status_and_updates_the_header(bare_machine, monkeypatch):
    llm_client.save_settings({"provider": "gemini", "model": "gemini-2.0-flash"})
    _with_claude_cli(monkeypatch)
    assert client.post("/llm/auto-connect").json()["connected"] is True
    assert llm_client.get_public_settings()["connection_status"] == "active"        # saving the new provider must not wipe the proof it answered
    health = client.get("/llm/health").json()
    assert health["ok"] is True and health["provider"] == "claude_cli"


def test_auto_connect_without_any_option_changes_nothing(bare_machine):
    llm_client.save_settings({"provider": "gemini", "model": "gemini-2.0-flash"})
    data = client.post("/llm/auto-connect").json()
    assert data["connected"] is False and data["results"] == [] and "Claude Code" in data["message"]
    assert llm_client.load_settings()["provider"] == "gemini"


def test_auto_connect_when_every_option_fails_changes_nothing(bare_machine, monkeypatch):
    llm_client.save_settings({"provider": "gemini", "model": "gemini-2.0-flash"})
    _with_claude_cli(monkeypatch)
    monkeypatch.setattr(llm_client, "_call_claude_cli", lambda prompt, system, timeout, model=None: (_ for _ in ()).throw(llm_client.LlmError("not signed in")))
    data = client.post("/llm/auto-connect").json()
    assert data["connected"] is False and [r["ok"] for r in data["results"]] == [False] and "not signed in" in data["results"][0]["message"]
    assert llm_client.load_settings()["provider"] == "gemini"


def test_an_unknown_provider_is_rejected_and_auto_is_accepted(bare_machine):
    assert client.post("/llm/settings", json={"provider": "not-a-provider"}).status_code == 422
    assert client.post("/llm/settings", json={"provider": "auto"}).status_code == 200


def _claude_command(monkeypatch, model):
    """The command line the real Claude CLI wrapper would run for `model` (the process itself is faked)."""
    monkeypatch.delenv("PROMPTGEN_MODEL", raising=False)
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude")
    seen = []

    def run(cmd, **kwargs):
        seen.append(cmd)
        return type("R", (), {"stdout": '{"result": "ok", "usage": {}}', "stderr": ""})()
    monkeypatch.setattr(llm_client.subprocess, "run", run)
    assert _REAL_CLAUDE_CLI("hi", "", 30, model=model) == "ok"
    return seen[0]


def test_claude_cli_runs_with_the_chosen_model(monkeypatch):
    cmd = _claude_command(monkeypatch, "claude-opus-5-5")
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"


def test_claude_cli_default_label_leaves_the_model_to_the_cli(monkeypatch):
    assert "--model" not in _claude_command(monkeypatch, llm_client.DEFAULT_MODELS["claude_cli"])


def test_the_model_saved_for_claude_cli_reaches_every_call(bare_machine, monkeypatch):
    seen = []
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/fake/claude")
    monkeypatch.setattr(llm_client, "_call_claude_cli", lambda prompt, system, timeout, model=None, images=None: seen.append(model) or "ok")
    client.post("/llm/settings", json={"provider": "claude_cli", "model": "sonnet"})
    llm_client.generate_text("hi")
    assert client.post("/llm/test", json={}).json()["ok"] is True
    assert seen == ["sonnet", "sonnet"]


def test_claude_cli_offers_a_model_pick_list():
    providers = {p["id"]: p for p in client.get("/llm/settings").json()["available_providers"]}
    ids = [m["id"] for m in providers["claude_cli"]["models"]]
    assert {"claude-code", "sonnet", "opus", "haiku"} <= set(ids)
    assert providers["gemini"]["models"] == []                           # providers without a list keep the typed model name


def test_checking_the_active_connection_updates_the_header_status(bare_machine, monkeypatch):
    _with_claude_cli(monkeypatch)
    client.post("/llm/settings", json={"provider": "claude_cli"})
    assert client.post("/llm/test", json={}).json()["ok"] is True
    health = client.get("/llm/health").json()
    assert health["ok"] is True and health["provider"] == "claude_cli"
