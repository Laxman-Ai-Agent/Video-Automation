"""The user's switches for the deterministic rules (checks) of the stages: a rule that is switched OFF is not evaluated, so it can never block, warn or fail a stage.

One file, `config/rule_switches.json`: {"off": {"<stage_id>:<rule>": {"at": <epoch>, "note": "<why>"}}}. No file = every rule ON (the default). A rule is named by its stage and its own
name (the same names the stage reports show). The stages ask `is_off(stage, rule)` at the one place where they record a rule; nothing else decides whether a rule runs. The catalog of all
rules is `rule_catalog.py`. A rule that is OFF is told to the LLM reviewers (`off_in(stage)`), so a check that was not made is never read as a check that passed."""
from __future__ import annotations

import json
import os
import threading
import time

from SYSTEM.core import config

FILE = config.PROJECT_ROOT / "config" / "rule_switches.json"
_lock = threading.Lock()
_cache: dict = {"key": None, "off": {}}


def _key(stage: str, rule: str) -> str:
    return f"{stage}:{rule}"


def off() -> dict[str, dict]:
    """Every rule that is switched off, with when and why (cached until the file changes: the stages ask this thousands of times per run)."""
    try:
        st = FILE.stat()
    except OSError:
        return {}
    sig = (str(FILE), st.st_mtime_ns, st.st_size)
    if _cache["key"] != sig:
        try:
            data = json.loads(FILE.read_text(encoding="utf-8")).get("off", {})
        except (OSError, ValueError, AttributeError):
            data = {}
        _cache.update(key=sig, off=data if isinstance(data, dict) else {})
    return _cache["off"]


def is_off(stage: str, rule: str) -> bool:
    return _key(stage, rule) in off()


def off_in(stage: str) -> list[str]:
    """The rules of one stage that are switched off (what the LLM reviewers are told)."""
    prefix = f"{stage}:"
    return sorted(k[len(prefix):] for k in off() if k.startswith(prefix))


def _write(data: dict) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"off": data}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, FILE)                                          # atomic: a stage never reads a half-written file


def set_many(rules: list[tuple[str, str]], on: bool, note: str = "") -> None:
    """Switch rules ON or OFF (one rule, a whole stage, or everything back on)."""
    with _lock:
        data = dict(off())
        for stage, rule in rules:
            if on:
                data.pop(_key(stage, rule), None)
            else:
                data[_key(stage, rule)] = {"at": time.time(), "note": note[:300]}
        _write(data)
