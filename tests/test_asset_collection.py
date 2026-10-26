"""Stage 5 Asset Collection (VIDEO_ENGINE/stages/asset_collection.py): requirements planning, rights classes, search cache, fetch + validation, fallbacks, reuse, checks and staging.
The network and the LLM are replaced (stock.search / stock.download / llm_gateway.gateway.execute), so nothing here needs internet, a key or a language model.
Run: python -m pytest tests/test_asset_collection.py -q"""
import io
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from VIDEO_ENGINE.ffmpeg import media_probe
from VIDEO_ENGINE.stages import asset_collection as ac, live_steps, llm_gateway, stock

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def jpeg(color=(200, 60, 40), size=(1600, 900), seed=0) -> bytes:
    im = Image.new("RGB", size, color)
    for x in range(0, size[0], 40 + seed):                        # a pattern, so two different seeds do not hash alike
        for y in range(0, size[1], 40 + seed):
            im.putpixel((x, y), (255 - color[0], x % 255, y % 255))
    for i in range(seed * 30):
        im.paste((i * 7 % 255, 20, 200), (i * 13 % size[0], i * 5 % size[1], i * 13 % size[0] + 60 + seed * 20, i * 5 % size[1] + 40))
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def cand(i=1, kind="image", rights=True, license_name="Pexels License", w=1920, h=1080, provider="pexels", dur=None):
    return stock.StockAsset(id=f"{provider}:{i}", provider=provider, provider_asset_id=str(i), source_page_url=f"https://example.org/{i}", download_url=f"https://images.pexels.com/{i}.jpg",
                            media_type=kind, title=f"river {i}", width=w, height=h, duration_s=dur, license_name=license_name, license_url="https://l", author="Ann",
                            attribution_text="Photo by Ann on Pexels", commercial_use_known=True if rights else None, search_query="river", retrieved_at="2026-10-21T00:00:00").model_dump()


_PDIR: dict = {}


def write_plan(pdir, reqs):
    """The Visual Plan that asks for `reqs` (rows: scene, kind, query, alt_queries, must_be_real, why): one scene for each scene of the scene plan, every real element a media requirement.
    Asset Collection reads these; the stage has no planner of its own any more."""
    sp = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    scenes, per = [], {}
    for s in sp["scenes"]:
        mine = []
        for r in reqs:
            if r.get("scene") == s["id"]:
                per[s["id"]] = n = per.get(s["id"], 0) + 1
                mine.append({"requirement_id": f"req_asset_{s['id']}_{n}", "element_id": f"asset_{s['id']}_{n}", "media_type": {"video": "video", "page": "reference"}.get(r["kind"], "image"), "query": r["query"], "section": r.get("section"),
                             "alt_queries": r.get("alt_queries", []), "why": r.get("why", ""), "must_be_real": r.get("must_be_real", False), "ai_prompt": None,
                             "fallback": "a flat graphic of the same idea", "required": True, "region": "full_frame", "semantic_content": r["query"]})
        scenes.append({"plan_scene_id": s["id"], "media_requirements": mine})
    (pdir / "visual_planning.json").write_text(json.dumps({"source_fingerprint": "fp-" + json.dumps(reqs, sort_keys=True), "scenes": scenes}), encoding="utf-8")


@pytest.fixture
def pdir(tmp_path, monkeypatch):
    p = tmp_path / "projects" / "p1"
    p.mkdir(parents=True)
    scenes = [{"id": 1, "start": 0.0, "end": 6.0, "meaning": "The Nile floods every year", "concept": "a river", "keywords": ["nile"]},
              {"id": 2, "start": 6.0, "end": 12.0, "meaning": "Why compound interest grows", "concept": "a chart", "keywords": []}]
    (p / "scene_plan.json").write_text(json.dumps({"scenes": scenes}), encoding="utf-8")
    monkeypatch.setattr(ac, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(ac.visual_planning, "blockers", lambda pd: None)                 # the Visual Plan is current: its own tests are in test_visual_planning.py
    _PDIR["p"] = p
    write_plan(p, [])
    return p


class LLM:
    """Replaces the gateway for the ranking call (the stage has no planner call any more): counts the calls. `requirements` = what the Visual Plan asks for (written by use())."""

    def __init__(self, requirements=None, choice=0, fail=False):
        self.requirements, self.choice, self.fail, self.calls = requirements if requirements is not None else [], choice, fail, []

    def __call__(self, req):
        self.calls.append(req.system_prompt[:12])
        if self.fail:
            return SimpleNamespace(error="down", structured_data=None, provider="stub", model="stub")
        body = json.loads(req.user_prompt.split("\n", 1)[1])
        return SimpleNamespace(error=None, structured_data={"choices": [{"requirement_id": b["requirement_id"], "index": self.choice} for b in body]}, provider="stub", model="stub")


def use(monkeypatch, llm, results=None, files=None):
    monkeypatch.setattr(llm_gateway.gateway, "execute", llm)
    if isinstance(llm, LLM) and _PDIR:
        write_plan(_PDIR["p"], llm.requirements)
    searches, downloads = [], []

    def fake_search(q, aspect="16:9", kind="image"):
        searches.append((q, kind))
        res = (results or {}).get(q, (results or {}).get("*", []))
        return [stock.StockAsset(**c) for c in res], {"pexels": {"ok": True, "count": len(res)}}

    def fake_download(c):
        downloads.append(c["id"])
        return (files or {}).get(c["id"]) or jpeg()
    monkeypatch.setattr(stock, "search", fake_search)
    monkeypatch.setattr(stock, "download", fake_download)
    return searches, downloads


REQ = {"scene": 1, "kind": "photo", "query": "Nile river flood", "alt_queries": ["river flood", "flooded river"], "must_be_real": False, "why": "a real place"}


def test_rights_classes_never_claim_unclear_rights_as_free():
    assert ac.rights_class(cand()) == "A"
    assert ac.rights_class(cand(rights=False, license_name="NASA media guidelines")) == "C"
    assert ac.rights_class(cand(license_name="")) == "D"


def test_a_provider_that_cannot_serve_more_than_1024_px_gets_its_own_width_floor():
    assert ac._usable(cand(1, w=1024, h=683, provider="openverse"), "photo") and not ac._usable(cand(2, w=1024, h=683, provider="pexels"), "photo")
    assert not ac._usable(cand(3, w=800, h=600, provider="openverse"), "photo") and ac._usable(cand(4, w=640, h=480, kind="video", dur=60.0, provider="archive"), "video")


def test_requirements_come_from_the_visual_plan_without_any_llm_call_and_are_reused_while_it_is_unchanged(pdir, monkeypatch):
    llm = LLM([REQ, {**REQ, "query": "Nile; river flood", "alt_queries": ["a", "b", "c"]}, {**REQ, "kind": "video", "query": "second", "must_be_real": True}])
    use(monkeypatch, llm)
    data = ac.plan_requirements(pdir, "16:9")
    reqs = data["requirements"]
    assert [r["query"] for r in reqs] == ["Nile river flood", "Nile  river flood", "second"]              # punctuation stripped
    assert [r["requirement_id"] for r in reqs] == ["req_1_1", "req_1_2", "req_1_3"] and [r["kind"] for r in reqs] == ["photo", "photo", "video"]
    assert reqs[1]["alt_queries"] == ["a", "b"] and reqs[2]["must_be_real"] is True and reqs[0]["fallback"] and reqs[0]["element_id"] == "asset_1_1" and data["source"] == "visual_planning.json"
    assert llm.calls == []                                                                              # the stage has no planner
    assert ac.plan_requirements(pdir, "16:9")["generated_at"] == data["generated_at"] and ac.load_requirements(pdir) == data     # same Visual Plan: the file is reused
    write_plan(pdir, [{**REQ, "query": "something else"}])
    assert [r["query"] for r in ac.plan_requirements(pdir, "16:9")["requirements"]] == ["something else"]    # the plan changed: written again


def test_a_missing_or_stale_visual_plan_stops_the_stage_with_the_cause(pdir, monkeypatch):
    use(monkeypatch, LLM())
    monkeypatch.setattr(ac.visual_planning, "blockers", lambda pd: "there is no Visual Plan yet: run Visual Planning")
    with pytest.raises(ac.AssetError, match="Visual Planning must be current.*no Visual Plan yet"):
        ac.run(pdir)


def test_no_requirements_completes_with_an_empty_manifest(pdir, monkeypatch):
    llm = LLM([])
    searches, downloads = use(monkeypatch, llm)
    man = ac.run(pdir)
    assert man["assets"] == [] and man["fallbacks"] == [] and man["requirement_count"] == 0 and not searches and not downloads
    assert ac.check_assets(pdir) == [] and ac.assets_for_scene(pdir, 1) == []


def test_a_photo_is_collected_with_provenance_credit_and_a_manifest(pdir, monkeypatch):
    llm = LLM([REQ], choice=1)
    searches, downloads = use(monkeypatch, llm, results={"*": [cand(1), cand(2), cand(3, license_name="")]}, files={"pexels:2": jpeg(seed=3)})
    man = ac.run(pdir)
    (a,) = man["assets"]
    assert downloads == ["pexels:2"] and a["selected_by"] == "llm"                   # the LLM's choice; the licence-less candidate was filtered before the LLM saw it
    assert a["authenticity"] == "real" and a["rights_class"] == "A" and a["needs_human_review"] is False and a["scene_id"] == 1 and a["element_id"] == "asset_1_1"
    assert a["source_url"] == "https://example.org/2" and a["license"]["name"] == "Pexels License" and a["attribution_text"] == "Photo by Ann on Pexels"
    assert (pdir / a["file"]).is_file() and a["public_file"] == f"projects/p1/assets/{Path(a['file']).name}" and a["width"] == 1600
    assert json.loads((pdir / "credits.json").read_text(encoding="utf-8"))[0]["slot"] == "req_1_1"
    assert ac.check_assets(pdir) == []
    assert ac.assets_for_scene(pdir, 1)[0]["credit"] == "Photo by Ann on Pexels" and ac.assets_for_scene(pdir, 2) == []


def test_a_current_manifest_is_reused_without_search_download_or_llm(pdir, monkeypatch):
    llm = LLM([REQ])
    searches, downloads = use(monkeypatch, llm, results={"*": [cand(1)]})
    ac.run(pdir)
    n_llm, n_search, n_down = len(llm.calls), len(searches), len(downloads)
    ac.run(pdir)
    assert (len(llm.calls), len(searches), len(downloads)) == (n_llm, n_search, n_down)
    f = next((pdir / "assets" / "collected").iterdir())
    f.unlink()                                                                       # a collected file disappears: only that asset is fetched again (the query is served from the cache)
    ac.run(pdir)
    assert len(downloads) == n_down + 1 and f.exists() and len(searches) == n_search


def _report(pdir):
    return json.loads((pdir / ac.REPORT).read_text(encoding="utf-8"))


def test_the_stage_writes_its_steps_live_and_finishes_them_all(pdir, monkeypatch):
    seen = []
    real = live_steps.LiveSteps.write
    monkeypatch.setattr(live_steps.LiveSteps, "write", lambda self: (real(self), seen.append((self.status, [r["status"] for r in self.rows], live_steps.progress(self.path))))[0])
    use(monkeypatch, LLM([REQ], choice=1), results={"*": [cand(1), cand(2)]}, files={"pexels:2": jpeg(seed=3)})
    ac.run(pdir)
    assert any(st == "running" and "running" in rows and lp and 0 <= lp["percent"] < 100 for st, rows, lp in seen)       # a step was seen running, with a real percent, before the end
    percents = [lp["percent"] for st, rows, lp in seen if lp]
    assert percents == sorted(percents)                                                                                  # the percent never goes back
    rep = _report(pdir)
    assert rep["status"] == "completed" and [r["status"] for r in rep["stages"]] == ["completed"] * len(ac.STEPS) and live_steps.progress(pdir / ac.REPORT) is None
    assert rep["stages"][3]["detail"].startswith("1 real asset(s) ready")


def test_every_step_carries_the_facts_it_stands_on_also_when_the_last_result_is_reused(pdir, monkeypatch):
    from backend import step_llm_check
    use(monkeypatch, LLM([REQ], choice=1), results={"*": [cand(1), cand(2)]}, files={"pexels:2": jpeg(seed=3)})
    ac.run(pdir)
    rows = _report(pdir)["stages"]
    assert all(r.get("evidence") for r in rows)                                                       # a step without facts cannot be confirmed by the LLM check
    assert rows[0]["evidence"]["requirements"][0]["query"] == "Nile river flood" and rows[3]["evidence"]["assets"][0]["file_sha256"]
    assert rows[4]["evidence"]["check_findings"] == [] and rows[4]["evidence"]["assets"] == 1
    ac.run(pdir)                                                                                      # nothing changed: reused, still with counts and facts
    again = _report(pdir)["stages"]
    assert all(r["status"] == "completed" and r["checks_total"] == 1 and r["evidence"]["reuse_proof"]["input_fingerprint"] and r["evidence"]["reuse_proof"]["file_problems"] == [] for r in again) and "reused" in again[0]["detail"]
    ev = step_llm_check.build_step_evidence("assets", {"n": 4, "name": again[3]["name"]}, _report(pdir))
    assert ev["step_evidence"]["assets"][0]["rights_class"] == "A" and ev["recorded_detail"] == again[3]["detail"] and ev["subtask_checks_total"] == 1


def test_a_failing_stage_marks_the_step_that_ran_as_failed(pdir, monkeypatch):
    use(monkeypatch, LLM([{**REQ, "must_be_real": True}]), results={"*": []})
    with pytest.raises(ac.AssetError):
        ac.run(pdir)
    rep = _report(pdir)
    assert rep["status"] == "failed" and [r["status"] for r in rep["stages"]] == ["completed"] * 4 + ["failed"] and "no acceptable real media" in rep["stages"][4]["detail"]
    assert live_steps.progress(pdir / ac.REPORT) is None


def test_search_is_cached_and_a_total_outage_is_not(pdir, monkeypatch):
    req = {"requirement_id": "r", "scene_id": 1, "kind": "photo", "query": "river", "alt_queries": []}
    searches, _ = use(monkeypatch, LLM(), results={"*": [cand(1)]})
    ac.search(req, "16:9")
    ac.search(req, "16:9")
    assert len(searches) == 1
    calls = []
    monkeypatch.setattr(stock, "search", lambda q, a="16:9", kind="image": calls.append(q) or ([], {"pexels": {"ok": False, "error": "down"}}))
    ac.search({**req, "query": "other"}, "16:9")
    ac.search({**req, "query": "other"}, "16:9")
    assert calls == ["other", "other"]                                               # an outage is not cached: asked again


def test_alternative_queries_are_tried_while_there_are_too_few_candidates(pdir, monkeypatch):
    searches, _ = use(monkeypatch, LLM(), results={"Nile river flood": [], "river flood": [cand(1)], "flooded river": [cand(2)]})
    found, _ = ac.search({"requirement_id": "r", "scene_id": 1, "kind": "photo", "query": "Nile river flood", "alt_queries": ["river flood", "flooded river"]}, "16:9")
    assert [q for q, _ in searches] == ["Nile river flood", "river flood", "flooded river"] and [c["id"] for c in found] == ["pexels:1", "pexels:2"]


def test_class_d_and_small_candidates_are_never_downloaded(pdir, monkeypatch):
    searches, downloads = use(monkeypatch, LLM([REQ]), results={"*": [cand(1, license_name=""), cand(2, w=640, h=360)]})
    man = ac.run(pdir)
    assert downloads == [] and man["assets"] == [] and man["fallbacks"][0]["reason"] == "no usable candidate"


def test_rights_not_established_is_collected_but_flagged_for_a_person(pdir, monkeypatch):
    use(monkeypatch, LLM([REQ]), results={"*": [cand(1, rights=False, license_name="NASA media guidelines", provider="nasa")]})
    man = ac.run(pdir)
    assert man["assets"][0]["rights_class"] == "C" and man["assets"][0]["needs_human_review"] is True
    assert [f["code"] for f in ac.check_assets(pdir)] == ["asset_rights_review"] and ac.check_assets(pdir)[0]["severity"] == "review"


def test_duplicates_by_hash_and_by_look_are_skipped(pdir, monkeypatch):
    same = jpeg()
    use(monkeypatch, LLM([REQ, {**REQ, "query": "second one"}]), results={"*": [cand(1), cand(2)]}, files={"pexels:1": same, "pexels:2": same})
    man = ac.run(pdir)
    assert len(man["assets"]) == 1 and man["fallbacks"][0]["requirement_id"] == "req_1_2" and "already collected" in man["fallbacks"][0]["reason"]


def test_a_missing_optional_asset_falls_back_but_must_be_real_fails_the_stage(pdir, monkeypatch):
    use(monkeypatch, LLM([REQ]), results={"*": []})
    man = ac.run(pdir)
    assert man["assets"] == [] and man["fallbacks"][0]["action"].startswith("the scene keeps")
    use(monkeypatch, LLM([{**REQ, "must_be_real": True}]), results={"*": []})
    with pytest.raises(ac.AssetError, match=r"req_1_1 \(no usable candidate\)"):
        ac.run(pdir, force=True)
    assert json.loads(ac.manifest_path(pdir).read_text(encoding="utf-8"))["fallbacks"]       # the cause is recorded even though the stage failed


def test_when_the_llm_is_down_the_providers_ranking_decides(pdir, monkeypatch):
    llm = LLM([REQ])
    searches, downloads = use(monkeypatch, llm, results={"*": [cand(1), cand(2)]})
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        raise RuntimeError("down")
    monkeypatch.setattr(llm_gateway.gateway, "execute", flaky)
    man = ac.run(pdir)
    assert calls["n"] == 1 and man["assets"][0]["selected_by"] == "rule" and downloads == ["pexels:1"]


def test_tampered_or_provenance_less_assets_are_errors(pdir, monkeypatch):
    use(monkeypatch, LLM([REQ]), results={"*": [cand(1)]})
    man = ac.run(pdir)
    (pdir / man["assets"][0]["file"]).write_bytes(b"changed")
    assert [f["code"] for f in ac.check_assets(pdir)] == ["asset_file"]
    man["assets"][0]["source_url"] = ""
    man["assets"][0]["authenticity"] = "generated"
    codes = {f["code"] for f in ac.check_assets(pdir, man)}
    assert {"asset_provenance", "asset_authenticity"} <= codes


def test_assets_are_staged_for_remotion(pdir, monkeypatch, tmp_path):
    use(monkeypatch, LLM([REQ]), results={"*": [cand(1)]})
    man = ac.run(pdir)
    monkeypatch.setattr(ac.config, "REMOTION_DIR", tmp_path / "remotion", raising=False)
    assert ac.stage_assets(pdir) == 1
    assert (tmp_path / "remotion" / "public" / man["assets"][0]["public_file"]).is_file()


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg is not installed")
def test_a_video_is_trimmed_scaled_to_the_canvas_and_stripped_of_sound(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=14:size=1280x720:rate=24", "-f", "lavfi", "-i", "sine=duration=14", "-shortest", "-pix_fmt", "yuv420p", str(src)], check=True)
    dest = tmp_path / "out" / "clip.mp4"
    info = ac.prepare_clip(src.read_bytes(), dest, seconds=30, aspect="16:9")           # a 30 s scene: the clip is capped at MAX_CLIP_S
    p = media_probe.probe(dest)
    assert (p["video"]["width"], p["video"]["height"]) == (1920, 1080) and p["audio"] is None and abs(p["duration"] - 10) < 0.5
    assert info["clip_out"] - info["clip_in"] == pytest.approx(10, abs=0.01) and info["clip_in"] == pytest.approx(2.0, abs=0.01) and abs(info["fps"] - 30) < 0.01
    vert = ac.prepare_clip(src.read_bytes(), tmp_path / "v.mp4", seconds=4, aspect="9:16")
    assert (vert["width"], vert["height"]) == (1080, 1920)
    with pytest.raises(ac.AssetError, match="not readable media"):
        ac.prepare_clip(b"not a video" * 50, tmp_path / "bad.mp4", seconds=4, aspect="16:9")


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg is not installed")
def test_a_video_requirement_goes_through_the_whole_stage(pdir, monkeypatch, tmp_path):
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=8:size=1280x720:rate=30", "-pix_fmt", "yuv420p", str(src)], check=True)
    vid = cand(7, kind="video", dur=8.0, w=1280, h=720)
    use(monkeypatch, LLM([{**REQ, "kind": "video", "query": "river flowing"}]), results={"*": [vid]})
    monkeypatch.setattr(stock, "permitted_url", lambda c: str(src))                     # a provider clip with a known duration is read by ffmpeg itself: here from a local file
    man = ac.run(pdir)
    (a,) = man["assets"]
    assert a["kind"] == "video" and a["file"].endswith(".mp4") and a["duration_s"] == pytest.approx(6.0, abs=0.3) and (a["width"], a["height"]) == (1920, 1080)
    assert a["clip_in"] == pytest.approx(1.0, abs=0.01) and a["source_duration_s"] == pytest.approx(8.0, abs=0.1) and ac.check_assets(pdir) == []


def test_motion_generation_gets_the_collected_assets_as_elements_it_must_draw(tmp_path, llm_codegen_stub, monkeypatch):
    """Scenes draw what Asset Collection found: every asset becomes a required element (never read as a 3D request, even with "model" in its title) and the LLM prompt says how to draw real media."""
    import importlib
    from VIDEO_ENGINE.stages import motion_animation as ma
    sid = 1
    d, *_ = importlib.import_module("test_motion_planning").make(tmp_path / "proj_assets", real={sid: "image"})              # scene 1 has a real primary element, element id image_main
    media = d / "assets" / "collected" / "abc.jpg"
    media.parent.mkdir(parents=True)
    media.write_bytes(jpeg())
    ac._save(ac.manifest_path(d), {"schema": ac.SCHEMA_MAN, "assets": [{
        "asset_id": "abc", "requirement_id": f"req_{sid}_1", "scene_id": sid, "element_id": "image_main", "kind": "photo", "file": "assets/collected/abc.jpg", "public_file": "projects/x/assets/abc.jpg",
        "title": "Wooden model ship with camera crew", "attribution_text": "Photo by Ann on Pexels", "width": 1600, "height": 900}], "fallbacks": []})
    seen = []
    real = llm_gateway.gateway.execute

    def spy(req):
        seen.append(req)
        return real(req)
    monkeypatch.setattr(llm_gateway.gateway, "execute", spy)
    man = ma.generate_custom_motion_code(d, "16:9")
    code = (d / "generated_motion" / f"scene_{sid}.tsx").read_text(encoding="utf-8")
    assert 'data-element-id="image_main"' in code
    sc = next(s for s in man["scenes"] if s["scene_id"] == sid)
    assert "image_main" in sc["required_elements"] and "image_main" in sc["implemented_elements"] and "image_main" not in sc["missing_required_elements"]
    assert next(c for c in sc["element_classifications"] if c["element_id"] == "image_main")["is_3d"] is False
    gen = next(r for r in seen if f"Scene {sid}." in r.user_prompt and "real_media" in r.user_prompt)
    assert "staticFile(real_media.file)" in gen.system_prompt and "Photo by Ann on Pexels" in gen.user_prompt and "projects/x/assets/abc.jpg" in gen.user_prompt


def test_a_remote_clip_is_seeked_by_ffmpeg_over_http_and_not_downloaded(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=1, stderr="Server returned 404", stdout="")
    monkeypatch.setattr(ac.subprocess, "run", fake_run)
    monkeypatch.setattr(ac, "_ffmpeg", lambda: "ffmpeg")
    with pytest.raises(ac.AssetError, match="404"):
        ac.prepare_clip("https://upload.wikimedia.org/x.webm", tmp_path / "o.mp4", seconds=6, aspect="16:9", source_duration=100.0)
    cmd = seen["cmd"]
    assert cmd.index("-ss") < cmd.index("-i") and cmd[cmd.index("-ss") + 1] == "47.000" and "-rw_timeout" in cmd and cmd[cmd.index("-i") + 1] == "https://upload.wikimedia.org/x.webm"
    with pytest.raises(ac.AssetError, match="duration of the remote clip is unknown"):
        ac.prepare_clip("https://upload.wikimedia.org/x.webm", tmp_path / "o.mp4", seconds=6, aspect="16:9")


def test_the_same_source_item_is_not_collected_twice(pdir, monkeypatch):
    use(monkeypatch, LLM([REQ, {**REQ, "query": "second one"}]), results={"*": [cand(1)]}, files={"pexels:1": jpeg()})
    man = ac.run(pdir)
    assert len(man["assets"]) == 1 and "same source item" in man["fallbacks"][0]["reason"]


def test_the_stage_contract_accepts_a_good_run_and_rejects_a_damaged_one(pdir, monkeypatch):
    from SYSTEM.core import artifact_contracts as contracts
    use(monkeypatch, LLM([REQ]), results={"*": [cand(1)]})
    man = ac.run(pdir)
    assert {r.artifact_id for r in contracts.validate_stage_artifacts(pdir, "assets")} == {"asset_requirements", "assets_manifest"}
    (pdir / man["assets"][0]["file"]).write_bytes(b"changed")
    with pytest.raises(contracts.ContractValidationError, match="changed after collection"):
        contracts.validate_stage_artifacts(pdir, "assets")
    (pdir / "assets_manifest.json").unlink()
    with pytest.raises(contracts.ContractValidationError, match="Missing assets_manifest.json"):
        contracts.validate_stage_artifacts(pdir, "assets")


def test_an_empty_run_is_a_valid_stage_output(pdir, monkeypatch):
    from SYSTEM.core import artifact_contracts as contracts
    use(monkeypatch, LLM([]))
    ac.run(pdir)
    assert len(contracts.validate_stage_artifacts(pdir, "assets")) == 2


def test_the_contract_refuses_class_d_and_non_real_assets(pdir, monkeypatch):
    from SYSTEM.core import artifact_contracts as contracts
    use(monkeypatch, LLM([REQ]), results={"*": [cand(1)]})
    man = ac.run(pdir)
    for field, value, text in (("rights_class", "D", "rights class"), ("authenticity", "generated", "authenticity"), ("source_url", "", "source or licence")):
        bad = json.loads(json.dumps(man))
        bad["assets"][0][field] = value
        ac._save(ac.manifest_path(pdir), bad)
        with pytest.raises(contracts.ContractValidationError, match=text):
            contracts.validate_stage_artifacts(pdir, "assets")


def test_the_llm_review_of_the_stage_sees_requirements_assets_and_findings(pdir, monkeypatch):
    from SYSTEM.policies import llm_review
    use(monkeypatch, LLM([REQ]), results={"*": [cand(1, rights=False, license_name="NASA media guidelines", provider="nasa")]})
    ac.run(pdir)
    payload = llm_review.build_stage_payload(pdir, "assets")
    assert payload["requirements"][0]["query"] == "Nile river flood" and payload["assets"][0]["rights_class"] == "C" and payload["scenes"][0]["about"].startswith("The Nile")
    assert payload["deterministic_findings"][0]["severity"] == "review"
    _, user = llm_review.generate_stage_review_prompt("assets", payload)
    assert "zero requirements" in user and "rights_class 'A' or 'C'" in user
    assert [f.name for f in llm_review.stage_output_files(pdir, "assets")] == ["asset_requirements.json", "assets_manifest.json"]
    assert "assets_manifest.json" in [f.name for f in llm_review.stage_input_files(pdir, "motion_gen")]            # a changed asset makes Motion Generation stale


def test_final_qc_blocks_damaged_assets_and_lists_unsettled_rights_for_a_person(pdir, monkeypatch):
    from VIDEO_ENGINE.stages import final_qc
    use(monkeypatch, LLM([REQ, {**REQ, "query": "second one"}]), results={"second one": [cand(2, rights=False, license_name="NASA media guidelines", provider="nasa")], "*": [cand(1)]},
        files={"pexels:1": jpeg(seed=1), "nasa:2": jpeg(seed=4)})
    man = ac.run(pdir)
    q = final_qc.Q()
    final_qc._assets_provenance(q, pdir)
    by = {c["rule_id"]: c for c in q.checks}
    assert by["QC_ASSETS_PROVENANCE"]["status"] == "passed" and by["QC_ASSET_RIGHTS_REVIEW"]["status"] == "requires_review" and by["QC_ASSET_RIGHTS_REVIEW"]["severity"] == "review"
    (pdir / man["assets"][0]["file"]).write_bytes(b"changed")
    q = final_qc.Q()
    final_qc._assets_provenance(q, pdir)
    assert next(c for c in q.checks if c["rule_id"] == "QC_ASSETS_PROVENANCE")["status"] == "failed"
    empty = final_qc.Q()
    ac._save(ac.manifest_path(pdir), {"schema": ac.SCHEMA_MAN, "assets": [], "fallbacks": []})
    final_qc._assets_provenance(empty, pdir)
    assert empty.checks == []                                                                                  # a project without real media: QC is unchanged


def test_the_real_media_skill_is_registered_pinned_and_reaches_the_codegen_prompt():
    from SYSTEM.registries import skill_registry
    reg = skill_registry.registry
    reg.initialize()
    rec = reg._skills["motion.real_media"]
    assert rec.status == "approved" and rec.domain == "motion" and rec.content_sha256 == skill_registry.compute_file_sha256(skill_registry.SKILLS_DIR / rec.entrypoint)
    assert "motion.real_media" in {s.skill_id for s in reg.search_skills(domain="motion", status="approved")}
    text = (skill_registry.SKILLS_DIR / rec.entrypoint).read_text(encoding="utf-8")
    assert "real_media.credit" in text and "staticFile(real_media.file)" in text and "mandatory" in text.lower()


def test_the_assets_stage_sits_between_visual_planning_and_motion_planning_in_the_dag(tmp_path):
    from SYSTEM.core import pipeline_state
    from VIDEO_ENGINE.pipeline import orchestrator
    pdir = tmp_path / "orch"
    pdir.mkdir()
    (pdir / "info.json").write_text(json.dumps({"id": "orch", "aspect": "16:9"}), encoding="utf-8")
    pipeline_state.save_pipeline_state(pdir, pipeline_state.init_default_state(pdir))
    assert orchestrator.STAGE_DEPENDENCIES["assets"] == ("planning",) and orchestrator.STAGE_DEPENDENCIES["motion_plan"] == ("assets",)
    assert pipeline_state.ACTIVE_STAGES.index("planning") + 1 == pipeline_state.ACTIVE_STAGES.index("assets") == pipeline_state.ACTIVE_STAGES.index("motion_plan") - 1
    assert pipeline_state.STAGE_TO_AGENT_MAP["assets"] == "asset_collection"
    pstate = pipeline_state.load_pipeline_state(pdir)
    for sid in ("audio", "analyzer", "segmentation", "planning"):
        pstate.stages[sid].status = "completed"
    pipeline_state.save_pipeline_state(pdir, pstate)
    mp = orchestrator.evaluate_stage_eligibility(pdir, "motion_plan", "16:9")
    assert mp["eligible"] is False and any("assets" in b for b in mp["blockers"])                  # Motion Planning waits for Asset Collection


def test_the_registered_adapter_runs_the_stage_and_its_output_passes_the_contract(pdir, monkeypatch):
    from SYSTEM.agents.shared.contracts import AgentRequest
    from SYSTEM.core import artifact_contracts as contracts
    from SYSTEM.registries.agent_registry import registry
    use(monkeypatch, LLM([REQ]), results={"*": [cand(1)]})
    adapter = registry.get_adapter("asset_collection")
    req = AgentRequest(project_id=pdir.name, agent_id="asset_collection", stage_id="assets", parameters={"aspect": "16:9", "force": True})
    assert adapter.validate(pdir, req) == []
    res = adapter.execute(pdir, req)
    assert res.status == "succeeded" and res.metadata["assets"] == 1 and {Path(r.path).name for r in res.output_refs} == {"asset_requirements.json", "assets_manifest.json"}
    assert len(contracts.validate_stage_artifacts(pdir, "assets")) == 2


def _page_cand(i=1):
    return stock.StockAsset(id=f"wikipedia-page:{i}", provider="wikipedia", provider_asset_id=str(i), source_page_url=f"https://en.wikipedia.org/wiki/Mount_{i}", download_url=f"https://en.wikipedia.org/wiki/Mount_{i}",
                            media_type="page", title=f"Mount {i}", license_name="CC BY-SA 4.0 (page text); images on the page carry their own licences", license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                            attribution_text=f"Mount {i}, Wikipedia contributors, CC BY-SA 4.0", commercial_use_known=None, search_query="mount", retrieved_at="2026-10-21T00:00:00").model_dump()


def _fake_capture(url, dest, section="infobox", **kw):
    dest.parent.mkdir(parents=True, exist_ok=True)                                                  # the real capture() creates the folder too
    Image.new("RGB", (520, 300), (240, 240, 250)).save(dest, "PNG")
    return {"final_url": url, "title": "Mount", "captured_at": "2026-10-21T00:00:00", "selector": ".infobox", "region": {"x": 10.0, "y": 20.0, "width": 520.0, "height": 300.0}, "width": 520, "height": 300,
            "text_sha256": "a" * 64, "text_excerpt": "Elevation 8,849 m"}


def test_a_reference_page_capture_is_collected_with_its_capture_record_and_flagged_for_a_person(pdir, monkeypatch):
    from VIDEO_ENGINE.stages import web_capture
    from SYSTEM.core import artifact_contracts as contracts
    use(monkeypatch, LLM([{**REQ, "kind": "page", "query": "Mount Everest", "section": "table"}, {**REQ, "kind": "page", "query": "bad section", "section": "../etc"}]))      # the Visual Plan asks for pages with a reference element
    searched = []
    monkeypatch.setattr(web_capture, "search_pages", lambda q: searched.append(q) or [stock.StockAsset(**_page_cand(1))])
    got = {}
    monkeypatch.setattr(web_capture, "capture", lambda url, dest, section="infobox", **kw: got.update(url=url, section=section) or _fake_capture(url, dest, section))
    man = ac.run(pdir)
    assert [r["section"] for r in ac.load_requirements(pdir)["requirements"]] == ["table", "infobox"]  # an unknown section falls back to the infobox
    (a,) = man["assets"]                                                                              # the second requirement wanted the same page: the same source item is not collected twice
    assert a["kind"] == "page" and a["capture_method"] == "browser_screenshot" and a["file"].endswith(".png") and a["rights_class"] == "C" and a["needs_human_review"] is True
    assert a["capture"]["selector"] == ".infobox" and a["capture"]["region"]["width"] == 520.0 and a["capture"]["text_sha256"] == "a" * 64 and a["width"] == 520
    assert got["url"] == "https://en.wikipedia.org/wiki/Mount_1" and got["section"] == "table" and searched
    assert [f["code"] for f in ac.check_assets(pdir)] == ["asset_rights_review"]
    assert len(contracts.validate_stage_artifacts(pdir, "assets")) == 2
    assert ac.assets_for_scene(pdir, 1)[0]["kind"] == "page"


def test_a_capture_that_is_refused_falls_back_and_never_fails_the_stage_unless_the_asset_must_be_real(pdir, monkeypatch):
    from VIDEO_ENGINE.stages import web_capture
    use(monkeypatch, LLM([{**REQ, "kind": "page"}]))
    monkeypatch.setattr(web_capture, "search_pages", lambda q: [stock.StockAsset(**_page_cand(1))])

    def refused(*a, **k):
        raise web_capture.CaptureError("disallowed by robots.txt")
    monkeypatch.setattr(web_capture, "capture", refused)
    man = ac.run(pdir)
    assert man["assets"] == [] and man["fallbacks"][0]["reason"] == "disallowed by robots.txt"


def test_motion_generation_tells_the_llm_how_to_draw_a_captured_page():
    from VIDEO_ENGINE.stages import motion_animation as ma
    import inspect
    src = inspect.getsource(ma.generate_scene_tsx_via_llm)
    assert 'kind \\"page\\"' in src and "objectFit contain" in src


def test_digitised_book_plates_are_not_candidates(pdir, monkeypatch):
    plate = {**cand(1), "title": 'Image from page 154 of "Mount Everest, the reconnaissance, 1921" (1922)'}
    real = {**cand(2), "title": "Mount Everest from Gokyo Ri"}
    use(monkeypatch, LLM([REQ]), results={"*": [plate, real]}, files={"pexels:2": jpeg(seed=2)})
    man = ac.run(pdir)
    assert [a["title"] for a in man["assets"]] == ["Mount Everest from Gokyo Ri"]


def test_when_the_model_rejects_every_candidate_the_next_alternative_query_is_tried(pdir, monkeypatch):
    class Picky(LLM):
        """Rejects candidates that are not about the Nile, accepts the first Nile one."""
        def __call__(self, req):
            if "Asset Planner" in req.system_prompt:
                return super().__call__(req)
            self.calls.append("rank")
            body = json.loads(req.user_prompt.split("\n", 1)[1])
            out = []
            for b in body:
                idx = next((c["index"] for c in b["candidates"] if "nile" in c["title"].lower()), None)
                out.append({"requirement_id": b["requirement_id"], "index": idx})
            return SimpleNamespace(error=None, structured_data={"choices": out}, provider="stub", model="stub")
    llm = Picky([REQ])
    wrong = [{**cand(i), "title": f"Mauna Kea {i}"} for i in (1, 2, 3, 4, 5)]
    right = [{**cand(9), "title": "The Nile in flood"}, {**cand(10), "title": "Nile delta"}]
    searches, downloads = use(monkeypatch, llm, results={"Nile river flood": wrong, "river flood": wrong, "flooded river": right}, files={"pexels:9": jpeg(seed=5)})
    man = ac.run(pdir)
    assert [a["title"] for a in man["assets"]] == ["The Nile in flood"] and man["assets"][0]["selected_by"] == "llm"
    assert [q for q, _ in searches] == ["Nile river flood", "flooded river"] or "flooded river" in [q for q, _ in searches]
    assert llm.calls.count("rank") == 2                                                              # asked once, rejected, asked again with the new candidates


def test_a_rejected_requirement_with_no_alternatives_left_falls_back_without_a_wrong_asset(pdir, monkeypatch):
    class Never(LLM):
        def __call__(self, req):
            if "Asset Planner" in req.system_prompt:
                return super().__call__(req)
            body = json.loads(req.user_prompt.split("\n", 1)[1])
            return SimpleNamespace(error=None, structured_data={"choices": [{"requirement_id": b["requirement_id"], "index": None} for b in body]}, provider="stub", model="stub")
    searches, downloads = use(monkeypatch, Never([{**REQ, "alt_queries": []}]), results={"*": [cand(1), cand(2)]})
    man = ac.run(pdir)
    assert downloads == [] and man["assets"] == [] and "no candidate fits" in man["fallbacks"][0]["reason"]


def _state_without_assets(tmp_path, completed):
    from SYSTEM.core import pipeline_state
    pdir = tmp_path / "old"
    pdir.mkdir()
    (pdir / "info.json").write_text(json.dumps({"id": "old", "aspect": "16:9"}), encoding="utf-8")
    state = pipeline_state.init_default_state(pdir)
    for sid in completed:
        state.stages[sid].status = "completed"
    pipeline_state.save_pipeline_state(pdir, state)
    f = pipeline_state._state_file(pdir)
    raw = json.loads(f.read_text(encoding="utf-8"))
    raw["stages"].pop("assets")                                                     # what a project stored before the stage existed looks like
    f.write_text(json.dumps(raw), encoding="utf-8")
    return pdir


def test_a_project_that_ran_before_the_stage_existed_skips_it_and_is_not_blocked(tmp_path):
    from SYSTEM.core import pipeline_state
    from VIDEO_ENGINE.pipeline import orchestrator
    pdir = _state_without_assets(tmp_path, ["audio", "analyzer", "segmentation", "planning", "motion_plan", "motion_gen"])
    rec = pipeline_state.load_pipeline_state(pdir).stages["assets"]
    assert rec.status == "skipped" and "added after" in rec.metadata["skipped_reason"]
    assert orchestrator.evaluate_stage_eligibility(pdir, "motion_plan", "16:9")["eligible"] is True          # re-running Motion Planning is possible without Asset Collection


def test_a_project_still_before_the_stage_keeps_it_pending(tmp_path):
    from SYSTEM.core import pipeline_state
    from VIDEO_ENGINE.pipeline import orchestrator
    pdir = _state_without_assets(tmp_path, ["audio", "analyzer", "segmentation", "planning"])                 # nothing after the stage completed yet: it will really run
    assert pipeline_state.load_pipeline_state(pdir).stages["assets"].status == "pending"
    mp = orchestrator.evaluate_stage_eligibility(pdir, "motion_plan", "16:9")
    assert mp["eligible"] is False and any("assets" in b for b in mp["blockers"])


def test_the_search_cache_is_not_used_for_a_different_set_of_providers(pdir, monkeypatch):
    req = {"requirement_id": "r", "scene_id": 1, "kind": "photo", "query": "river", "alt_queries": []}
    searches, _ = use(monkeypatch, LLM(), results={"*": [cand(1)]})
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    ac.search(req, "16:9")
    ac.search(req, "16:9")
    assert len(searches) == 1                                                        # the same providers: served from the cache
    monkeypatch.setenv("PEXELS_API_KEY", "k")
    ac.search(req, "16:9")
    assert len(searches) == 2                                                        # a key was set: a provider that was not asked before is asked now
