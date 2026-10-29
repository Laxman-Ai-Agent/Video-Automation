"""The optional motion kit: chosen at upload (own project key, default off, no route changes it), imports of `../kit` pass the audit only when it is on,
the fingerprint changes only when it is on. Run: python -m pytest tests/test_motion_kit.py -q"""
import importlib
import json
import re

import pytest

from SYSTEM.core import config
from VIDEO_ENGINE.stages import motion_animation as ma
from VIDEO_ENGINE.stages import store

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create

KIT_SCENE = 'import { CameraRig, KineticWords, ART_DIRECTIONS } from "../kit";\nexport const Scene1 = () => null;'


def test_kit_import_passes_the_audit_only_when_the_kit_is_on():
    off = ma.audit_scene_tsx_security(KIT_SCENE)
    assert not off["passed"] and any("motion kit is off" in f for f in off["findings"])
    assert ma.audit_scene_tsx_security(KIT_SCENE, motion_kit=True)["passed"]
    assert ma.audit_scene_tsx_security('import { CameraRig } from "../kit/CameraRig";', motion_kit=True)["passed"]
    assert not ma.KIT_IMPORT.search('import { x } from "../kitten";')                    # only ../kit and ../kit/... are the kit


def test_the_hint_names_the_kit_only_when_it_is_on_and_matches_what_the_kit_exports():
    assert "MOTION KIT" not in ma.approved_libraries_hint() and "MOTION KIT" in ma.approved_libraries_hint(motion_kit=True)
    index = (config.REMOTION_DIR / "src" / "kit" / "index.ts").read_text(encoding="utf-8")
    names = {n.strip() for group in re.findall(r"export (?:type )?\{ ([^}]+) \}", index) for n in group.split(",")}
    for used in ("CameraRig", "KineticWords", "ART_DIRECTIONS", "ArtDirectionKey"):
        assert used in names and used in ma.KIT_HINT


def test_the_fingerprint_changes_only_when_the_kit_is_on():
    base = dict(duration=3.0, headline="h", subtext="", texts=["h"], elements=[], palette=["#000"], aspect="16:9", shots=[])
    assert ma.scene_input_fingerprint(**base) == ma.scene_input_fingerprint(**base)
    assert ma.scene_input_fingerprint(**base, motion_kit=True) != ma.scene_input_fingerprint(**base)


class _Stop(Exception):
    pass


@pytest.mark.parametrize("kit", [False, True])
def test_the_stage_puts_the_motion_kit_key_into_the_scene_inputs_only_when_it_is_on(tmp_path, monkeypatch, kit):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    pdir = store.create("Fp", "16:9", motion_kit=kit)
    (pdir / "scene_plan.json").write_text(json.dumps({"scenes": [{"id": 1, "start": 0, "end": 3, "meaning": "m"}], "style": {"palette": ["#000"]}}), encoding="utf-8")
    seen = {}

    def capture(**inputs):
        seen.update(inputs)
        raise _Stop

    monkeypatch.setattr(ma, "scene_input_fingerprint", capture)
    with pytest.raises(_Stop):
        ma.generate_custom_motion_code(pdir)
    assert ("motion_kit" in seen) is kit and (seen.get("motion_kit") is True or not kit)


def test_a_project_stores_the_kit_choice_at_creation_and_old_projects_have_it_off(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    on = store.create("Kit", "16:9", motion_kit=True)
    assert store.motion_kit(on) is True and json.loads((on / "project.json").read_text(encoding="utf-8"))["motion_kit"] is True
    off = store.create("Plain")
    assert store.motion_kit(off) is False
    info = json.loads((off / "project.json").read_text(encoding="utf-8"))
    info.pop("motion_kit")                                                           # a project made before the option existed
    (off / "project.json").write_text(json.dumps(info), encoding="utf-8")
    assert store.motion_kit(off) is False
    assert store.media(on) == {"ai_images": False}                                    # the kit is not part of `media`: the Visual Plan fingerprint is untouched


def test_the_api_takes_the_kit_at_upload_and_nothing_changes_it_afterwards(client):
    ok = client.post("/projects", data={"name": "K", "motion_kit": "true"}, files={"audio": ("a.wav", _m7.wav_bytes(), "audio/wav")})
    assert ok.status_code == 201 and ok.json()["motion_kit"] is True
    pid = ok.json()["id"]
    client.patch(f"/projects/{pid}", json={"motion_kit": False})
    assert client.get(f"/projects/{pid}").json()["motion_kit"] is True
    assert create(client).json()["motion_kit"] is False
