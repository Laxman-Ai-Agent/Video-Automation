"""The `claude` subprocess signs in with the pipeline's own login folder even when the backend was started without CLAUDE_CONFIG_DIR."""
from SYSTEM.core import llm_client


def test_the_pipeline_login_folder_is_used_when_the_variable_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client, "PIPELINE_LOGIN_DIR", tmp_path)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert llm_client._claude_env()["CLAUDE_CONFIG_DIR"] == str(tmp_path)


def test_an_explicit_variable_wins_and_a_missing_folder_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client, "PIPELINE_LOGIN_DIR", tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "X:/other")
    assert llm_client._claude_env()["CLAUDE_CONFIG_DIR"] == "X:/other"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    monkeypatch.setattr(llm_client, "PIPELINE_LOGIN_DIR", tmp_path / "missing")
    assert "CLAUDE_CONFIG_DIR" not in llm_client._claude_env()
