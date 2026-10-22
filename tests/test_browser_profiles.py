"""backend/browser_profiles.py: only finished Remotion Chrome profiles, webpack bundles and asset folders are removed. Run: python -m pytest tests/test_browser_profiles.py -q"""
import os
import time

import pytest

from backend import browser_profiles as bp


@pytest.fixture
def tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(bp, "_tmp", lambda: tmp_path)
    monkeypatch.setattr(bp, "_in_use", lambda: "chrome.exe --headless")
    return tmp_path


def profile(root, name, age=0, marker="Default"):
    p = root / (bp.PREFIX + name)
    (p / marker).mkdir(parents=True)
    (p / marker / "f.bin").write_bytes(b"x" * 100)
    if age:
        t = time.time() - age
        os.utime(p, (t, t))
    return p


def test_only_profiles_made_by_the_run_are_removed(tmp):
    old = profile(tmp, "before")                       # existed before the run: not ours
    snap = bp.snapshot()
    new = profile(tmp, "new")
    other = tmp / "some_other_temp"; other.mkdir()
    fake = tmp / (bp.PREFIX + "nomarker"); fake.mkdir()        # same prefix but not a Chrome profile
    r = bp.sweep(snap, retries=1, wait=0)
    assert not new.exists() and old.exists() and other.exists() and fake.exists()
    assert r["removed"] == 1 and r["bytes"] == 100


def test_remotion_bundles_and_asset_folders_a_run_made_are_removed_too(tmp):
    snap = bp.snapshot()
    bundle = tmp / "remotion-webpack-bundle-AbC123"; (bundle / "public").mkdir(parents=True); (bundle / "index.html").write_text("x")
    assets = tmp / "remotion-v4.0.534-assetsxyz"; (assets / "remotion-assets-dir").mkdir(parents=True)
    unrelated = tmp / "remotion-notes"; unrelated.mkdir()                 # the prefix alone is not enough: no marker, kept
    r = bp.sweep(snap, retries=1, wait=0)
    assert not bundle.exists() and not assets.exists() and unrelated.exists() and r["removed"] == 2


def test_a_profile_a_running_process_uses_is_kept(tmp, monkeypatch):
    p = profile(tmp, "busy")
    monkeypatch.setattr(bp, "_in_use", lambda: f'chrome.exe --user-data-dir="{p}"'.lower())
    r = bp.sweep(set(), retries=1, wait=0)
    assert p.exists() and r["kept_in_use"] == 1 and r["removed"] == 0


def test_stale_leftovers_go_but_fresh_ones_without_a_snapshot_stay(tmp):
    stale, fresh = profile(tmp, "stale", age=2 * bp.STALE_SECONDS), profile(tmp, "fresh")
    bp.sweep(None, retries=1, wait=0)
    assert not stale.exists() and fresh.exists()


def test_nothing_is_deleted_when_the_process_list_cannot_be_read(tmp, monkeypatch):
    p = profile(tmp, "x")
    monkeypatch.setattr(bp, "_in_use", lambda: None)
    assert bp.sweep(set(), retries=1, wait=0)["removed"] == 0 and p.exists()


def test_cleanup_runs_after_an_error_too(tmp, monkeypatch):
    monkeypatch.setattr(bp.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        with bp.cleaned_after():
            profile(tmp, "made-during-run")
            raise RuntimeError("render failed")
    assert not list(tmp.glob(bp.PREFIX + "*"))
