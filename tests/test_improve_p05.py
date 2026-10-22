"""Phase 0.5 of improvement/MASTER_PLAN.md: flags, contracts, locks, fingerprints, safe-area table, golden plan preview."""
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import config, contracts, plan_preview
from backend.fingerprint import versioned
from backend.theme import THEME

FIX = Path(__file__).parent / "fixtures"


def test_flags_default_off(monkeypatch):
    for n in ("fingerprints", "highlights", "match_detail", "shots", "validation"):
        monkeypatch.delenv(f"A2V_{n.upper()}", raising=False)
        assert config.improve(n) is False
    monkeypatch.setenv("A2V_SHOTS", "1")
    assert config.improve("shots") is True


def test_fingerprint_unchanged_when_flag_off(monkeypatch):
    monkeypatch.delenv("A2V_FINGERPRINTS", raising=False)
    assert versioned("match", "abc") == "abc" and versioned("match", None) is None


def test_fingerprint_changes_with_config_and_stage_version(monkeypatch):
    monkeypatch.setenv("A2V_FINGERPRINTS", "1")
    base = versioned("match", "abc")
    assert base != "abc" and versioned("match", "abc") == base          # deterministic
    monkeypatch.setattr(config, "CLIP_MIN_MARGIN", 0.05)
    assert versioned("match", "abc") != base                              # a threshold change invalidates match
    monkeypatch.setattr(config, "CLIP_MIN_MARGIN", 0.03)
    monkeypatch.setitem(config.STAGE_VERSIONS, "match", 2)
    assert versioned("match", "abc") != base                              # a logic-version bump invalidates match
    assert versioned("cuts", "abc") == versioned("cuts", "abc")


@pytest.mark.parametrize("score,margin,has_file,want", [
    (0.38, 0.12, True, "high"), (0.30, 0.06, True, "high"), (0.35, 0.04, True, "medium"), (0.25, 0.03, True, "medium"),
    (0.35, -0.02, True, "low"), (0.20, 0.10, True, "low"), (None, None, True, "none"), (0.40, 0.2, False, "none")])
def test_band(score, margin, has_file, want):
    assert contracts.band(score, margin, has_file) == want


def test_contracts_reject_unknown_fields():
    with pytest.raises(ValidationError):
        contracts.Reason(rule="x", surprise=1)
    with pytest.raises(ValidationError):
        contracts.Shot(id="a", scene=1, start=0, end=1, kind="camera_move", reason=contracts.Reason(rule="x"))   # a camera move is not a shot kind


def test_locks(tmp_path):
    class M:
        def __init__(self, n, method): self.n, self.method = n, method
    assert contracts.locked_numbers(tmp_path, [M(1, "clip"), M(2, "manual")]) == {2}
    contracts.set_lock(tmp_path, 5)
    assert contracts.locked_numbers(tmp_path, [M(1, "clip")]) == {5}
    contracts.set_lock(tmp_path, 5, False)
    assert contracts.locked_numbers(tmp_path) == set()


def test_safe_area_table_matches_existing_definitions():
    from backend import prerender_checks
    pct = lambda s: float(s.rstrip("%")) / 100
    p = THEME["portrait"]
    assert config.SAFE_AREA["margin"] == THEME["safeMargin"]
    assert config.SAFE_AREA["portrait_caption_bottom"] == pct(p["captionBottom"])
    assert config.SAFE_AREA["portrait_lower_third_bottom"] == pct(p["lowerThirdBottom"])
    assert config.SAFE_AREA["portrait_label_top"] == pct(p["labelTop"])
    assert config.SAFE_AREA["portrait_ui_bottom"] == prerender_checks.UI_BOTTOM
    assert config.SAFE_AREA["portrait_ui_bottom"] <= config.SAFE_AREA["portrait_caption_bottom"]    # captions sit above the covered zone


def test_thresholds_are_consistent():
    assert config.MATCH_HIGH_SCORE > config.CLIP_MIN_SCORE and config.MATCH_HIGH_MARGIN > config.CLIP_MIN_MARGIN
    assert config.MIN_SHOT_SEC * 2 <= config.LONG_SCENE_SEC
    lo, hi = config.HIGHLIGHT_DURATION_SEC
    assert 0 < lo < hi


def _golden_project(tmp_path: Path) -> Path:
    for f in ("transcript.json", "scene_plan.json", "prompts_map.json", "composition.json"):
        shutil.copy(FIX / "plan_sample" / f, tmp_path / f)
    shutil.copy(FIX / "golden" / "match_report.json", tmp_path / "match_report.json")
    return tmp_path


def test_plan_preview_matches_golden(tmp_path):
    got = plan_preview.dump(plan_preview.build(_golden_project(tmp_path)))
    assert got == (FIX / "golden" / "expected_plan_preview.json").read_text(encoding="utf-8")


def test_plan_preview_without_matches_is_never_all_clear(tmp_path):
    pdir = _golden_project(tmp_path)
    (pdir / "match_report.json").unlink()
    out = plan_preview.build(pdir)
    assert out["summary"]["matches"] == {"high": 0, "medium": 0, "low": 0, "none": 14}
    assert sum(1 for i in out["issues"] if i["rule"] == "missing_image") == 14      # missing media must show up, never "all clear"


def test_plan_preview_locks_manual_choice_and_reasons(tmp_path):
    pdir = _golden_project(tmp_path)
    out = plan_preview.build(pdir)
    ms = [m for s in out["scenes"] for m in s["matches"]]
    manual = next(m for m in ms if m["reason"]["rule"] == "user_choice")
    assert manual["locked"] is True and manual["band"] == "none"
    assert all(m["reason"]["rule"] for m in ms)
    assert all(s["shots"][0]["kind"] == "whole_scene" and s["shots"][0]["reason"]["rule"] for s in out["scenes"])
