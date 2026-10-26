"""The media registry (SYSTEM/core/media_kinds.py) and its contract: what an element can be is defined in ONE place, and every consumer must handle every kind in it.
A new kind added to KINDS without its handler makes `test_every_consumer_handles_every_kind` fail. Run: python -m pytest tests/test_media_kinds.py -q"""
import importlib
import json
import typing

import pytest

from SYSTEM.core import media_kinds as mk
from VIDEO_ENGINE.stages import asset_collection, motion_planning, motion_scenes, store
from VIDEO_ENGINE.stages import visual_planning as vp
from VIDEO_ENGINE.stages import visual_planning_rules as rules

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create


# ---------- the registry itself ----------
def test_every_kind_has_a_known_family_and_group():
    assert mk.FAMILIES == ("motion", "image", "video")
    for k in mk.KINDS.values():
        assert k.family in mk.FAMILIES and k.group in mk.GROUPS and k.about
    assert set(mk.TYPES) == set(mk.KINDS) and set(mk.TEXT_TYPES) == {"text", "label"} and set(mk.REAL_TYPES) == {"image", "video", "reference"}
    assert mk.family_of("reference") == "image" and mk.group_of("reference") == "page" and mk.family_of("diagram") == "motion" and mk.group_of("chart") == "graphic" and mk.is_text("label") and mk.is_real("video") and not mk.is_real("icon")


def test_the_only_media_choice_is_ai_pictures_and_the_old_shares_are_ignored():
    assert mk.normalise(None) == {"ai_images": False} == mk.DEFAULT_MEDIA
    assert mk.options({}) == mk.normalise(None)
    assert mk.options({"media": {"motion": 50, "image": 50, "video": 0, "ai_images": True}}) == {"ai_images": True}          # a project made with shares keeps working: the shares mean nothing now
    with pytest.raises(ValueError, match="true or false"):
        mk.normalise({"ai_images": "yes"})
    assert not hasattr(mk, "allowed")                                                                                          # every family is always available inside the motion graphics


# ---------- the setting is made at upload and stored with the project ----------
def test_a_project_stores_its_media_settings_at_creation(tmp_path, monkeypatch):
    from SYSTEM.core import config
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    pdir = store.create("Mix", "16:9", media={"ai_images": True})
    assert store.media(pdir) == {"ai_images": True} and json.loads((pdir / "project.json").read_text(encoding="utf-8"))["media"] == {"ai_images": True}
    assert store.media(store.create("Default")) == mk.DEFAULT_MEDIA
    with pytest.raises(ValueError):
        store.create("Bad", media={"ai_images": "maybe"})
    assert not any(p.name.startswith("bad") for p in tmp_path.iterdir())              # nothing is made for a setting that cannot be used


def test_the_api_takes_the_setting_at_upload_and_no_share_is_asked(client):
    ok = client.post("/projects", data={"name": "A", "ai_images": "true", "media_image": 30}, files={"audio": ("a.wav", _m7.wav_bytes(), "audio/wav")})     # a share sent by an old client is ignored
    assert ok.status_code == 201 and ok.json()["media"] == {"ai_images": True}
    default = create(client)
    assert default.status_code == 201 and default.json()["media"] == {"ai_images": False}


def test_there_is_no_route_that_changes_the_setting_afterwards(client):
    pid = create(client).json()["id"]
    client.patch(f"/projects/{pid}", json={"media": {"ai_images": True}})
    assert client.get(f"/projects/{pid}").json()["media"] == {"ai_images": False}


# ---------- the contract: every consumer handles every kind ----------
def test_every_consumer_handles_every_kind():
    # the planner's schema takes exactly the registry's types
    assert typing.get_args(vp.Element.model_fields["type"].annotation) == mk.TYPES
    # the per-scene counts have a place for every kind
    got = rules.counts([{"element_id": t, "type": t} for t in mk.TYPES])
    assert sum(got.values()) == len(mk.TYPES) and set(got) == set(mk.GROUPS)
    # the planner is told about every kind, whatever the project's settings
    assert all(f"- {t} (" in vp.spec(mk.normalise(raw)) for t in mk.TYPES for raw in (None, {"ai_images": True}))
    # Asset Collection knows what to collect for every real kind
    assert set(asset_collection.KIND_OF) == set(mk.REAL_TYPES)
    # Motion Planning resolves every kind to something (drawn, collected or a recorded fallback), never an exception
    vps = {"elements": [{"element_id": f"e_{t}", "type": t, "role": "supporting", "required": False, "content": "x" if mk.is_text(t) else None, "visual_description": "d",
                         "placement": {"region": "center", "priority": 1, "avoid_overlap": True}, "registry_requirements": None, "media": {"fallback": "a flat graphic"} if mk.is_real(t) else None}
                        for t in mk.TYPES], "motion_hints": []}
    m = {"id": 1, "texts": [{"text": "x", "preset": "p"}], "graphics": [], "icons": [], "classic_texts": []}
    els_out, *_ = motion_scenes.resolve(vps, m, "scene_01", motion_planning.Run(), {})
    by = {e["element_id"]: e for e in els_out}
    assert all(f"e_{t}" in by for t in mk.TYPES) and by["e_image"]["status"] == "fallback" and by["e_video"]["status"] == "fallback"
    got = motion_scenes.resolve(vps, m, "scene_01", motion_planning.Run(), {"e_image": {"element_id": "e_image", "kind": "photo", "file": "projects/t/assets/a.jpg", "credit": "Photo by Ann"}})[0]
    assert next(e for e in got if e["element_id"] == "e_image")["registry_kind"] == "real_media"
