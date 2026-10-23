"""The Asset Collection page API: GET /projects/{pid}/assets (requirements with what was collected or why not) and the collected files. Run: python -m pytest tests/test_assets_api.py -q"""
import importlib
import json

from VIDEO_ENGINE.stages import asset_collection as ac

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create


def plan_with_requests(pdir, monkeypatch):
    """A current Visual Plan that asks for one photo in scene 1 and one clip in scene 2."""
    (pdir / "scene_plan.json").write_text(json.dumps({"scenes": [{"id": 1, "start": 0, "end": 6, "meaning": "m", "concept": "c", "keywords": []}, {"id": 2, "start": 6, "end": 12, "meaning": "n", "concept": "c", "keywords": []}]}), encoding="utf-8")
    req = lambda mt, q: {"requirement_id": "x", "element_id": f"{mt}_main", "media_type": mt, "query": q, "alt_queries": ["office"], "why": "w", "must_be_real": False, "ai_prompt": "an office, soft light",
                         "fallback": "a flat desk graphic", "required": True, "region": "full_frame", "semantic_content": q}
    (pdir / "visual_planning.json").write_text(json.dumps({"source_fingerprint": "fp", "scenes": [{"plan_scene_id": 1, "media_requirements": [req("image", "office workers")]},
                                                                                             {"plan_scene_id": 2, "media_requirements": [req("video", "busy street")]}]}), encoding="utf-8")
    monkeypatch.setattr(ac.visual_planning, "blockers", lambda p: None)


def test_the_page_lists_every_request_with_its_file_or_the_reason_it_fell_back(client, monkeypatch):
    pid = create(client).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    assert client.get(f"/projects/{pid}/assets").json()["items"] == []                          # nothing planned yet: nothing is invented
    plan_with_requests(pdir, monkeypatch)
    aspect = client.get(f"/projects/{pid}").json().get("aspect") or "9:16"
    reqs = ac.plan_requirements(pdir, aspect)["requirements"]
    assert [r["requirement_id"] for r in reqs] == ["req_1_1", "req_2_1"]
    assert {i["status"] for i in client.get(f"/projects/{pid}/assets").json()["items"]} == {"pending"}
    f = ac.collected_dir(pdir) / "abc.jpg"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"\xff\xd8 fake jpeg")
    asset = {"asset_id": "abc", "requirement_id": "req_1_1", "scene_id": 1, "element_id": "image_main", "kind": "photo", "file": "assets/collected/abc.jpg", "public_file": "projects/x/assets/abc.jpg",
             "authenticity": "real", "source_url": "https://example.org/a", "license": {"name": "Pexels License"}, "rights_class": "A", "title": "Office", "provider": "pexels"}
    ac._save(ac.manifest_path(pdir), {"schema": ac.SCHEMA_MAN, "input_fingerprint": ac.input_fingerprint(pdir, aspect), "requirement_count": 2, "assets": [asset],
                                      "fallbacks": [{"requirement_id": "req_2_1", "scene_id": 2, "kind": "video", "must_be_real": False, "reason": "no usable candidate", "action": "the scene keeps its generated motion graphics"}], "providers": {}})
    got = client.get(f"/projects/{pid}/assets").json()
    by = {i["requirement_id"]: i for i in got["items"]}
    assert by["req_1_1"]["status"] == "collected" and by["req_1_1"]["asset"]["url"] == f"/projects/{pid}/assets/file/abc.jpg" and by["req_1_1"]["ai_prompt"] == "an office, soft light"
    assert by["req_2_1"]["status"] == "fallback" and by["req_2_1"]["reason"] == "no usable candidate" and by["req_2_1"]["fallback"] == "a flat desk graphic"
    assert got["summary"] == {"requirements": 2, "collected": 1, "fallbacks": 1} and got["manifest_current"] is True
    r = client.get(f"/projects/{pid}/assets/file/abc.jpg")
    assert r.status_code == 200 and r.content == f.read_bytes()


def test_only_listed_collected_files_are_served_and_never_a_path_outside(client):
    pid = create(client).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    (pdir / "secret.txt").write_text("secret", encoding="utf-8")
    ac.collected_dir(pdir).mkdir(parents=True)
    (ac.collected_dir(pdir) / "unlisted.jpg").write_bytes(b"x")
    ac._save(ac.manifest_path(pdir), {"schema": ac.SCHEMA_MAN, "assets": []})
    assert client.get(f"/projects/{pid}/assets/file/unlisted.jpg").status_code == 404                   # in the folder but not in the manifest
    assert client.get(f"/projects/{pid}/assets/file/..%2F..%2Fsecret.txt").status_code == 404
    assert client.get(f"/projects/{pid}/assets/file/secret.txt").status_code == 404
