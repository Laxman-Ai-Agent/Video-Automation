"""Letting a model look at pictures (contact sheets): only Claude Code is wired to show them, with the Read tool and nothing else; any other provider refuses so the caller falls back to text;
the gateway passes `images` to the client only when a request has some. Nothing here calls a real model. Run: python -m pytest tests/test_llm_images.py -q"""
import json
import uuid
from types import SimpleNamespace

import pytest

from SYSTEM.core import llm_client, llm_gateway

_REAL_CLAUDE_CLI = llm_client._call_claude_cli          # tests/conftest.py replaces it with a stub that refuses a live model; here the subprocess itself is replaced instead


def _fake_cli(monkeypatch):
    monkeypatch.setattr(llm_client, "_call_claude_cli", _REAL_CLAUDE_CLI)
    seen = {}

    def run(cmd, **kw):
        seen.update(cmd=cmd, stdin=kw.get("input"))
        return SimpleNamespace(stdout=json.dumps({"result": "ok", "usage": {}}) + "\n", stderr="", returncode=0)
    monkeypatch.setattr(llm_client.subprocess, "run", run)
    monkeypatch.setattr(llm_client.shutil, "which", lambda name: "claude")
    return seen


def test_claude_code_gets_only_the_read_tool_and_the_picture_folder_when_it_must_look(monkeypatch, tmp_path):
    seen = _fake_cli(monkeypatch)
    sheet = tmp_path / "sheets" / "a.jpg"
    sheet.parent.mkdir()
    sheet.write_bytes(b"x")
    assert llm_client._call_claude_cli("which one?", "rank", 30, images=[str(sheet)]) == "ok"
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "Read" and cmd[cmd.index("--allowedTools") + 1] == "Read"
    assert cmd[cmd.index("--add-dir") + 1] == str(sheet.parent.resolve()) and int(cmd[cmd.index("--max-turns") + 1]) > 1
    assert str(sheet.resolve()) in seen["stdin"] and "Read tool" in seen["stdin"]


def test_without_images_claude_code_keeps_no_tool_and_one_turn(monkeypatch):
    seen = _fake_cli(monkeypatch)
    llm_client._call_claude_cli("hello", "", 30)
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "" and cmd[cmd.index("--max-turns") + 1] == "1" and "--allowedTools" not in cmd and "--add-dir" not in cmd


def test_a_provider_that_cannot_look_refuses_instead_of_ignoring_the_pictures(monkeypatch):
    monkeypatch.setattr(llm_client, "resolve_provider_config", lambda **kw: ("gemini", "m", "k", ""))
    with pytest.raises(llm_client.LlmError, match="look at pictures"):
        llm_client.generate_text("rank", images=["a.jpg"])


def test_the_gateway_passes_images_only_when_a_request_has_some(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_gateway.gateway.client, "resolve_provider_config", lambda **kw: ("claude_cli", "m", "", ""))
    monkeypatch.setattr(llm_gateway.gateway.client, "generate_text", lambda **kw: calls.append(kw) or "plain answer")
    base = dict(project_id="p", stage_id="assets", agent_id="vision_probe", purpose="generation", user_prompt=f"u-{uuid.uuid4().hex}", system_prompt="s")
    llm_gateway.gateway.execute(llm_gateway.LlmGatewayRequest(**base))
    llm_gateway.gateway.execute(llm_gateway.LlmGatewayRequest(**{**base, "user_prompt": base["user_prompt"] + "-2"}, images=["sheet.jpg"]))
    assert "images" not in calls[0] and calls[1]["images"] == ["sheet.jpg"]
