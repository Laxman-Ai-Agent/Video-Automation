"""The .env loader: settings and API keys from a local file reach the environment without overriding what is already set."""
import os

from SYSTEM.core import env_file


def test_key_value_lines_are_loaded_and_comments_blank_lines_and_quotes_are_handled(tmp_path, monkeypatch):
    for name in ("ABS_T_PLAIN", "ABS_T_QUOTED", "ABS_T_SINGLE", "ABS_T_EXPORTED", "ABS_T_EMPTY", "ABS_T_SPACED"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "# a comment\n\nABS_T_PLAIN=value1\nABS_T_QUOTED=\"two words\"\nABS_T_SINGLE='x y'\nexport ABS_T_EXPORTED=exp\nABS_T_EMPTY=\n  ABS_T_SPACED = padded  \nnot a setting\n",
        encoding="utf-8")
    loaded = env_file.load(tmp_path / ".env")
    assert loaded == {"ABS_T_PLAIN": "value1", "ABS_T_QUOTED": "two words", "ABS_T_SINGLE": "x y", "ABS_T_EXPORTED": "exp", "ABS_T_EMPTY": "", "ABS_T_SPACED": "padded"}
    assert os.environ["ABS_T_QUOTED"] == "two words" and os.environ["ABS_T_SPACED"] == "padded"
    for name in loaded:
        monkeypatch.delenv(name, raising=False)


def test_an_existing_environment_variable_wins_over_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ABS_T_KEEP", "from-the-shell")
    (tmp_path / ".env").write_text("ABS_T_KEEP=from-the-file\nABS_T_NEW=new\n", encoding="utf-8")
    monkeypatch.delenv("ABS_T_NEW", raising=False)
    loaded = env_file.load(tmp_path / ".env")
    assert os.environ["ABS_T_KEEP"] == "from-the-shell" and "ABS_T_KEEP" not in loaded
    assert os.environ["ABS_T_NEW"] == "new"
    monkeypatch.delenv("ABS_T_NEW", raising=False)


def test_a_missing_file_is_not_an_error(tmp_path):
    assert env_file.load(tmp_path / "does-not-exist.env") == {}


def test_blank_values_do_not_replace_a_real_one_but_do_fill_an_unset_name(tmp_path, monkeypatch):
    monkeypatch.setenv("ABS_T_REAL", "secret")
    monkeypatch.delenv("ABS_T_UNSET", raising=False)
    (tmp_path / ".env").write_text("ABS_T_REAL=\nABS_T_UNSET=\n", encoding="utf-8")
    env_file.load(tmp_path / ".env")
    assert os.environ["ABS_T_REAL"] == "secret" and os.environ["ABS_T_UNSET"] == ""
    monkeypatch.delenv("ABS_T_UNSET", raising=False)
