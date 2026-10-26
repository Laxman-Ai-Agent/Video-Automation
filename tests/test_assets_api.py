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


def test_upload_custom_asset_replaces_fallback_and_serves_file(client, monkeypatch):
    """Verify manual asset upload replaces a fallback requirement, stores file, and serves it."""
    pid = create(client).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    plan_with_requests(pdir, monkeypatch)
    aspect = client.get(f"/projects/{pid}").json().get("aspect") or "9:16"
    ac.plan_requirements(pdir, aspect)

    # Start with a fallback for req_1_1
    ac._save(ac.manifest_path(pdir), {
        "schema": ac.SCHEMA_MAN,
        "input_fingerprint": ac.input_fingerprint(pdir, aspect),
        "assets": [],
        "fallbacks": [{"requirement_id": "req_1_1", "scene_id": 1, "reason": "no stock found"}],
    })

    # Upload custom file for req_1_1
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
    res = client.post(
        f"/projects/{pid}/assets/upload",
        data={"requirement_id": "req_1_1", "scene_id": "1"},
        files={"file": ("custom_apple.png", fake_png, "image/png")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["asset"]["requirement_id"] == "req_1_1"
    assert data["asset"]["element_id"] == "image_main" and data["asset"]["scene_id"] == 1                 # what Motion Generation draws it as: without it Motion Generation fails with KeyError 'element_id'
    assert [x["element_id"] for x in ac.assets_for_scene(pdir, 1)] == ["image_main"]
    bad = client.post(f"/projects/{pid}/assets/upload", data={"requirement_id": "req_9_9", "scene_id": "1"}, files={"file": ("x.png", fake_png, "image/png")})
    assert bad.status_code == 404 and "req_9_9" in bad.text                                                 # an upload against a request that does not exist is refused

    # Verify assets endpoint now reports collected instead of fallback
    got = client.get(f"/projects/{pid}/assets").json()
    item = next(i for i in got["items"] if i["requirement_id"] == "req_1_1")
    assert item["status"] == "collected"
    assert "custom asset" in data["message"].lower()

    # Verify file can be fetched via file endpoint
    file_res = client.get(item["asset"]["url"])
    assert file_res.status_code == 200
    assert file_res.content == fake_png


def test_update_video_trim_and_icon(client, monkeypatch):
    """Verify updating video trim settings and icon settings via /assets/update."""
    pid = create(client).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    plan_with_requests(pdir, monkeypatch)
    aspect = client.get(f"/projects/{pid}").json().get("aspect") or "9:16"
    ac.plan_requirements(pdir, aspect)

    # Manifest with a video asset
    ac._save(ac.manifest_path(pdir), {
        "schema": ac.SCHEMA_MAN,
        "input_fingerprint": ac.input_fingerprint(pdir, aspect),
        "assets": [{
            "requirement_id": "req_2_1",
            "scene_id": 2,
            "kind": "video",
            "asset_id": "vid123",
            "file": "assets/collected/vid123.mp4",
            "duration_s": 10.0,
            "clip_start": 0.0,
            "clip_dur": 2.0,
            "clip_end": 2.0,
        }],
        "fallbacks": [],
    })

    # Update video trim
    res = client.post(
        f"/projects/{pid}/assets/update",
        json={
            "requirement_id": "req_2_1",
            "scene_id": 2,
            "kind": "video",
            "clip_start": 3.0,
            "clip_dur": 2.0,
            "clip_end": 5.0,
        }
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # Check manifest updated
    man = ac.load_manifest(pdir)
    vid_asset = next(a for a in man["assets"] if a["requirement_id"] == "req_2_1")
    assert vid_asset["clip_start"] == 3.0
    assert vid_asset["clip_dur"] == 2.0
    assert vid_asset["clip_end"] == 5.0

    # Check categories reported
    got = client.get(f"/projects/{pid}/assets").json()
    assert "categories" in got
    assert got["categories"]["videos"] >= 1


def test_chart_map_and_sfx_endpoints(client):
    pid = create(client).json()["id"]

    # 1. SFX Catalog
    sfx_res = client.get(f"/projects/{pid}/sfx/catalog")
    assert sfx_res.status_code == 200
    sfx_data = sfx_res.json()
    assert sfx_data["ok"] is True
    assert len(sfx_data["sfx"]) >= 5

    # 2. Generate Map
    map_res = client.post(
        f"/projects/{pid}/assets/generate-map",
        json={"place_name": "Hyderabad, India", "width": 800, "height": 600}
    )
    assert map_res.status_code == 200
    assert map_res.json()["ok"] is True
    assert map_res.json()["type"] == "map"




def test_a_picture_that_was_not_found_gets_a_prompt_to_make_it_elsewhere_and_a_hand_upload_is_valid_provenance(client, monkeypatch):
    pid = create(client).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    plan_with_requests(pdir, monkeypatch)
    aspect = client.get(f"/projects/{pid}").json().get("aspect") or "9:16"
    ac.plan_requirements(pdir, aspect)
    reqs = ac.load_requirements(pdir)
    reqs["requirements"][0]["ai_prompt"] = None                                                     # the planner wrote none (a project made without that choice)
    ac._save(ac.requirements_path(pdir), reqs)
    items = {i["requirement_id"]: i for i in client.get(f"/projects/{pid}/assets").json()["items"]}
    assert "office workers" in items["req_1_1"]["ai_prompt"] and "no text" in items["req_1_1"]["ai_prompt"] and items["req_2_1"]["ai_prompt"] is None      # a clip has none
    up = client.post(f"/projects/{pid}/assets/upload", data={"requirement_id": "req_1_1", "scene_id": "1"}, files={"file": ("mine.png", _png(), "image/png")})
    assert up.status_code == 200 and up.json()["asset"]["authenticity"] == "user_provided" and up.json()["asset"]["source_url"] == "user-upload://mine.png"
    man = ac.load_manifest(pdir)
    assert ac.check_assets(pdir, man) == []                                                         # a hand upload is not "source or licence is missing"
    old = {**man["assets"][0], "source_url": "", "authenticity": "real"}                              # one stored before uploads carried them
    assert ac.check_assets(pdir, {"assets": [old]}) == [] and ac.has_provenance(old)
    assert [f["code"] for f in ac.check_assets(pdir, {"assets": [{**old, "selected_by": None}]})] == ["asset_provenance"]      # a download without a source is still an error
    assert [f["code"] for f in ac.check_assets(pdir, {"assets": [{**old, "authenticity": "ai"}]})] == ["asset_authenticity"]


def _png():
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (64, 36), (10, 20, 30)).save(b, "PNG")
    return b.getvalue()
