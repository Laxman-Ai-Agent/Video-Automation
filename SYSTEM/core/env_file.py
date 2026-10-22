"""Load settings and API keys from a local `.env` file into the environment (standard library only).

An environment variable that is already set always wins over the file, so a shell or CI setting overrides it. Values are never printed or logged:
a `.env` may hold API keys. A missing file is not an error.
"""
from __future__ import annotations

import os
from pathlib import Path


def parse(text: str) -> dict[str, str]:
    """KEY=VALUE lines: blank lines, `# comments` and lines without `=` are skipped; `export KEY=...` is accepted; one pair of quotes around a value is removed."""
    pairs: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            pairs[key] = value
    return pairs


def load(path: Path) -> dict[str, str]:
    """Set every variable in the file that the environment does not have yet; returns the ones it set."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    loaded = {}
    for key, value in parse(text).items():
        if key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded
