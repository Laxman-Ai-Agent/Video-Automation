"""The GSAP adapter of the Remotion effects (VIDEO_ENGINE/remotion/src/gsapTimeline.ts) is deterministic: the same frame gives the same values in any order of
evaluation. Runs VIDEO_ENGINE/remotion/scripts/gsap_determinism.ts with tsx (no render). Run: python -m pytest tests/test_gsap_adapter.py -q"""
import json
import shutil
import subprocess

import pytest

from backend import config


def test_checkmark_timeline_is_frame_deterministic():
    if shutil.which("npx") is None:
        pytest.skip("node/npx not on PATH")
    r = subprocess.run("npx tsx scripts/gsap_determinism.ts", cwd=config.REMOTION_DIR, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert r.returncode == 0 and out["ok"], out
    assert all(out["checks"].values()) and len(out["checks"]) >= 7
