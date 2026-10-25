import json
import urllib.request
from pathlib import Path
from VIDEO_ENGINE.stages.sfx_manager import list_builtin_sfx, search_freesound, ensure_sfx_asset

def test_list_builtin_sfx():
    sfx = list_builtin_sfx()
    assert len(sfx) >= 4
    ids = [item["id"] for item in sfx]
    assert "whoosh" in ids
    assert "pop" in ids
    assert "ding" in ids

def test_ensure_sfx_asset(tmp_path):
    dest = ensure_sfx_asset("whoosh", tmp_path / "sfx")
    assert dest is not None
    assert dest.exists()
    assert dest.name == "whoosh.wav"
    assert dest.stat().st_size > 0

def test_ensure_sfx_asset_invalid(tmp_path):
    res = ensure_sfx_asset("non_existent_sfx", tmp_path / "sfx")
    assert res is None

def test_search_freesound_no_key(monkeypatch):
    monkeypatch.delenv("FREESOUND_API_KEY", raising=False)
    assert search_freesound("laser") == []

def test_search_freesound_with_key(monkeypatch):
    monkeypatch.setenv("FREESOUND_API_KEY", "test_key")
    
    class FakeFreesoundResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps({
                "results": [{
                    "id": 12345,
                    "name": "cinematic_whoosh.wav",
                    "duration": 0.8,
                    "previews": {"preview-hq-mp3": "https://freesound.org/preview.mp3"},
                    "license": "CC0",
                    "username": "sound_creator"
                }]
            }).encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=12: FakeFreesoundResponse())
    res = search_freesound("whoosh")
    assert len(res) == 1
    assert res[0]["name"] == "cinematic_whoosh.wav"
    assert res[0]["download_url"] == "https://freesound.org/preview.mp3"
