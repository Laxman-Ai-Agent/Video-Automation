"""Motion-Only runs (backend/pipeline.py CHAINS, pipeline_view.py, routes/pipeline.py, timeline_gate.py): no Image
Generation stage, no image blocker anywhere, a composition without picture layers built by the motion library at a faster pace, and the server
has no image endpoints. The scene plan is the known-good fixture; Whisper/CLIP/the renderer are the fakes of test_m7; the composition
is built by the real build_composition.ts. The last tests render a few real frames of both formats. Run: python -m pytest tests/test_motion_only_mode.py -q"""
import importlib
import json
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend import config, jobs, pipeline, render as render_mod, store, timeline_gate
from backend import motion_validation as mv, motion_validation_preview as pv

_m7 = importlib.import_module("test_m7")
client, png, wav_bytes, wait_job = _m7.client, _m7.png_bytes, _m7.wav_bytes, _m7.wait_job
FIXTURE = Path(__file__).parent / "fixtures" / "plan_sample"
REMOTION = Path(__file__).parent.parent / "VIDEO_ENGINE" / "remotion"


def make(c, use_images: bool | None, aspect: str = "16:9") -> str:
    data = {"name": "Motion Demo", "aspect": aspect, **({} if use_images is None else {"use_images": "true" if use_images else "false"})}
    r = c.post("/projects", data=data, files={"audio": ("talk.wav", wav_bytes(), "audio/wav")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def with_plan(pid: str) -> Path:
    pdir = config.PROJECTS_DIR / pid
    for f in ("scene_plan.json", "prompts_map.json", "composition.json", "translation.json", "transcript.json"):
        shutil.copyfile(FIXTURE / f, pdir / f)
    from backend import llm_review, pipeline_view, store
    from backend import visual_planning as vp
    from VIDEO_ENGINE.stages import asset_collection
    from backend import scene_segmentation as ss
    duration = json.loads((pdir / "transcript.json").read_text(encoding="utf-8"))["duration"]
    (pdir / "audio.wav").write_bytes(wav_bytes(duration))              # the narration the transcript was made from: as long as the video (the upload is a 1 s dummy)
    sp, pm = (json.loads((pdir / f).read_text(encoding="utf-8")) for f in ("scene_plan.json", "prompts_map.json"))
    words = [w for s in json.loads((pdir / "transcript.json").read_text(encoding="utf-8"))["segments"] for w in s["words"]]
    ranges = []                                                         # Stage 3 grouped the words exactly as the fixture's scene plan: its scenes, by word number
    for s in sp["scenes"]:
        inside = [i + 1 for i, w in enumerate(words) if s["start"] - 0.01 <= (w["start"] + w["end"]) / 2 <= s["end"] + 0.01]
        ranges.append((inside[0], inside[-1]))
    seg = importlib.import_module("test_scene_segmentation")
    out = ss.run(pdir, ask=seg.Ask(seg.by_words(*ranges)))
    starts = [c["start_time"] for c in out["scenes"]]                   # Stage 4 times its scenes from Stage 3: scene k from canonical scene k's start (the first at 0) to the next one's start
    for k, s in enumerate(sp["scenes"]):
        s["start"], s["end"] = (0.0 if k == 0 else starts[k]), (starts[k + 1] if k + 1 < len(starts) else out["audio_duration_seconds"])
    (pdir / "scene_plan.json").write_text(json.dumps(sp, ensure_ascii=False, indent=1), encoding="utf-8")
    def hint_main(raw):                                                 # a good planner answer says how its main drawn concept moves (Motion Planning draws a hinted graphic for it)
        for s in raw["scenes"]:
            if any(e["element_id"] == "gfx_main" for e in s["elements"]):
                s["motion_hints"].insert(0, {"element_id": "gfx_main", "intent": "show_connected_structure", "description": None})
    raw = importlib.import_module("test_visual_planning").raw_for(sp, mutate=hint_main)
    plan, problems = vp.assemble(pdir, sp, raw)
    assert problems == [], problems
    vp.save(pdir, plan)                                                 # a Visual Plan, as Stage 4 leaves it (without one, Motion Planning warns and the warnings block the next stage)
    aspect = pipeline_view.aspect_of(pdir)
    asset_collection.run(pdir, aspect)                                  # Stage 5 as a real run leaves it: no scene of the fixture needs real media,
    llm_review.review_stage(pdir, "assets", aspect)                     # and its stage review recorded (the client fixture's review stub passes it)
    return pdir


def stages(c, pid) -> dict:
    return {s["id"]: s for s in c.get(f"/projects/{pid}/pipeline").json()["stages"]}


def stills(d, aspect: str = "16:9"):
    """Review stills in the format Stage 10's preview writes: a manifest bound to the composition's identity and one decodable, non-blank PNG per sample."""
    comp = json.loads((d / "composition.json").read_text(encoding="utf-8"))
    gen = json.loads((d / "motion_generation.json").read_text(encoding="utf-8"))
    out = pv.folder(d, aspect)
    out.mkdir(exist_ok=True)
    samples = []
    for i, smp in enumerate(pv.sample_plan(comp)):
        name = f"{smp['scene_id']}_{smp['kind']}_{smp['frame']:05d}.png"
        Image.effect_noise((48, 27), 60 + i % 5).convert("RGB").save(out / name)
        samples.append({**smp, "file": name, "time_s": round(smp["frame"] / 30, 3), "sha": mv.sha((out / name).read_bytes()), "decode_ok": True, "width": 48, "height": 27, "std": 40.0, "blank": False})
    man = {"sampling_rule_version": pv.RULE_VERSION, "composition_sha": gen["output"]["composition_sha"], "renderer_digest": pipeline._remotion_src_digest(), "scale": pv.SCALE, "created_at": "2026-10-14T00:00:00",
           "level": "test stills", "samples": samples, "reviews": []}
    (out / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    return man


def real_video(pdir, aspect: str = "16:9", audio_seconds: float | None = None) -> Path:
    """A real encoded mp4 of the size, fps and length the project's composition asks for (ffmpeg test pattern + a tone as long as the video unless `audio_seconds` says otherwise). Stage 13 verifies the output of the renderer
    for real, so a test that replaces the renderer has to hand it a real video (cached in the temp folder)."""
    meta = json.loads((pdir / ("composition_9x16.json" if aspect == "9:16" else "composition.json")).read_text(encoding="utf-8"))["meta"]
    frames = int(meta["duration"] * meta["fps"] + 0.5)
    audio_seconds = meta["duration"] if audio_seconds is None else audio_seconds
    dst = Path(tempfile.gettempdir()) / f"a2v_mo_video_{meta['width']}x{meta['height']}_{meta['fps']}_{frames}_{audio_seconds}.mp4"
    if not dst.exists():
        part = dst.with_name(dst.stem + ".part.mp4")
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={meta['width']}x{meta['height']}:rate={meta['fps']}", "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={audio_seconds}",
               "-frames:v", str(frames), "-t", f"{frames / meta['fps']:.4f}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "38", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "48k", str(part)]
        assert subprocess.run(cmd, capture_output=True).returncode == 0
        part.replace(dst)
    return dst


def approve_stage_12(c, pid, pdir) -> None:
    """A Motion-Only timeline is approved on the Timeline Approval stage (Stage 12): it needs the review stills of this version, the person's name and every limitation acknowledged. The stills are written in
    the format Stage 10's preview makes (test_timeline_approval.stills); nothing is rendered."""
    stills(pdir)
    st = c.get(f"/projects/{pid}/timeline-approval").json()
    assert st["status"] == "ready_for_review", st["blockers"]
    r = c.post(f"/projects/{pid}/timeline-approval/decision", json={"decision": "approved", "review_id": st["review_id"], "expected_fingerprint": st["fingerprint"], "decision_by": "Asha",
                                                                    "idempotency_key": f"t-{pid}", "warning_acknowledgements": [{"key": q["key"], "acknowledged": True} for q in st["requirements"]]})
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text


def layers(comp) -> list[dict]:
    return [l for s in comp["scenes"] for l in s["layers"]]


@pytest.fixture
def motion(client):
    pid = make(client, False)
    return client, pid, with_plan(pid)


def fake_renderer(monkeypatch, pdir, aspect: str = "16:9") -> None:
    """The renderer is replaced; Stage 13 verifies the real mp4 it hands over (real_video)."""
    monkeypatch.setattr(render_mod, "render", lambda pdir_, preview, cb=None, aspect=aspect, out=None: (shutil.copyfile(real_video(pdir, aspect), out), cb and cb(100.0, 0), out)[2])


def build_timeline(c, pid):
    """The one click after Visual Planning: Motion Planning -> Generation -> Validation -> Timeline Build -> Timeline Approval (LLM) -> Render, no person before Final QC."""
    r = c.post(f"/projects/{pid}/pipeline/advance")
    assert r.status_code == 200 and r.json()["advanced"], r.text
    s = wait_job(c, pid, timeout=240)
    assert s["error"] is None, s
    return s


# ---------- Motion-Only is the only mode ----------
def test_every_project_uses_the_motion_chains(client):
    pdir = config.PROJECTS_DIR / make(client, None)
    for label in ("build", "build-preview", "build-9x16", "build-preview-9x16", "timeline", "timeline-9x16"):
        names = pipeline.chain_for(pdir, label)
        assert names == pipeline.CHAINS[label] and names[0].startswith("motion-plan")
        assert all(n in pipeline.STEPS for n in names)
    assert pipeline.chain_for(pdir, "transcribe") == pipeline.CHAINS["transcribe"]
    assert client.get(f"/projects/{pdir.name}").json()["use_images"] is False


def test_the_stage_list_is_the_13_stages_in_order(client):
    ids = list(stages(client, make(client, None)))
    assert ids == ["audio", "analyzer", "segmentation", "planning", "assets", "motion_plan", "motion_gen", "motion_validation", "timeline", "approval", "render", "qc", "final"]


def test_the_image_endpoints_are_removed(motion):
    c, pid, pdir = motion
    calls = [c.post(f"/projects/{pid}/images/match"), c.post(f"/projects/{pid}/images/collect"),
             c.post(f"/projects/{pid}/images/1/upload", files={"file": ("a.png", png(), "image/png")}), c.post(f"/projects/{pid}/images/1/use-asset", json={"id": "x"})]
    assert [r.status_code for r in calls] == [404] * 4
    gone = [c.post(f"/projects/{pid}/mode", json={"use_images": True}), c.get(f"/projects/{pid}/match"), c.post(f"/projects/{pid}/match/fix", json={"file": "a.png", "n": 1}),
            c.post(f"/projects/{pid}/submit"), c.post(f"/projects/{pid}/prompts/generate"), c.put(f"/projects/{pid}/prompts/1", json={"text": "x"}), c.delete(f"/projects/{pid}/timeline/approval")]
    assert all(r.status_code in (404, 405) for r in gone), [r.status_code for r in gone]      # the image workflow's routes are gone, not just refused
    assert c.get(f"/projects/{pid}/status").json()["waiting_for"] is None               # nothing ever waits for images


def test_continue_needs_no_images(motion, monkeypatch):
    c, pid, pdir = motion
    fake_renderer(monkeypatch, pdir)
    assert not (pdir / "assets").exists()                                                 # no image was ever uploaded
    r = c.post(f"/projects/{pid}/continue")
    assert r.status_code == 202 and r.json()["steps"] == ["motion-plan", "motion-build", "motion-validate", "timeline-build", "timeline-approve", "render-final"], r.text
    assert wait_job(c, pid, timeout=240)["error"] is None


# ---------- the build: no pictures, generated motion code, approval and render without a person ----------
def test_timeline_is_built_approved_and_rendered_without_pictures(motion, monkeypatch):
    c, pid, pdir = motion
    assert c.post(f"/projects/{pid}/render").status_code == 409                          # still guarded: nothing built yet
    p = c.get(f"/projects/{pid}/pipeline").json()
    assert not any("image" in b or "prompt" in b for b in p["render"]["blockers"])
    fake_renderer(monkeypatch, pdir)
    build_timeline(c, pid)
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    plan = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    assert comp["meta"]["motionOnly"] is True and comp["meta"]["fps"] == 30
    assert (comp["meta"]["width"], comp["meta"]["height"]) == (1920, 1080) and len(comp["scenes"]) == len(plan["scenes"])
    assert not [l for l in layers(comp) if l["type"] in ("image", "stock-video")]                                    # no picture layer at all
    assert (pdir / "out.mp4").exists() and (pdir / "render_report.json").exists()
    t = stages(c, pid)
    assert [t[k]["status"] for k in ("motion_plan", "motion_gen", "motion_validation", "timeline", "approval", "render")] == ["completed"] * 6, t
    assert t["qc"]["status"] == "completed"                                              # a rendered video is judged by the Final QC LLM review, nobody else


def test_both_aspect_ratios_are_built_without_pictures(client, monkeypatch):
    pid = make(client, None, "9:16")
    pdir = with_plan(pid)
    fake_renderer(monkeypatch, pdir, "9:16")
    build_timeline(client, pid)
    comp = json.loads((pdir / "composition_9x16.json").read_text(encoding="utf-8"))
    assert (comp["meta"]["width"], comp["meta"]["height"]) == (1080, 1920) and comp["meta"]["motionOnly"] and comp["meta"]["fps"] == 30
    assert not [l for l in layers(comp) if l["type"] == "image"]
    assert timeline_gate.state(pdir, "9:16")["ready"]


# ---------- real frames of both formats ----------
def _ready() -> str | None:
    if not (REMOTION / "node_modules" / "@remotion" / "renderer").exists():
        return "remotion dependencies are not installed"
    try:
        [socket.create_connection((h, 443), timeout=4).close() for h in ("fonts.googleapis.com", "fonts.gstatic.com")]
    except OSError:
        return "Google Fonts unreachable (the renderer fetches the fonts at render time)"
    return None


@pytest.mark.parametrize("aspect,size", [("16:9", (1920, 1080)), ("9:16", (1080, 1920))])
def test_real_frames_of_a_motion_only_video_are_not_blank_and_move(tmp_path, aspect, size):
    why = _ready()
    if why:
        pytest.skip(why)
    pdir = tmp_path / "p"
    pdir.mkdir()
    for f in ("scene_plan.json", "transcript.json"):
        shutil.copyfile(FIXTURE / f, pdir / f)
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{pdir}" --no-images --aspect {aspect}', cwd=REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, (r.stderr or r.stdout)[-500:]
    comp_file = pdir / ("composition_9x16.json" if aspect == "9:16" else "composition.json")
    comp = json.loads(comp_file.read_text(encoding="utf-8"))
    comp["meta"]["audio"] = "audio_test.wav"
    comp_file.write_text(json.dumps(comp), encoding="utf-8")
    first = comp["scenes"][0]
    frames = [round(first["start"] * 30) + k for k in (6, 12, 18, 30, 60)]            # early frames of scene 1: entrances and graphics are in motion
    cases = [{"name": f"f{f}", "frame": f, "props": comp} for f in frames]
    base = tmp_path / "probe"
    base.mkdir()
    (base / "cases.json").write_text(json.dumps({"scale": 0.5, "publicDir": str(REMOTION / "public"), "cases": cases}, ensure_ascii=False), encoding="utf-8")
    for _ in range(3):
        r = subprocess.run(f'npx tsx scripts/caption_probe.ts "{base / "cases.json"}" "{base / "out"}"', cwd=REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500)
        if r.returncode == 0:
            break
    if r.returncode != 0 and "fetchFontData" in (r.stderr + r.stdout):
        pytest.skip("the web fonts could not be downloaded at render time (network)")
    assert r.returncode == 0, (r.stderr or r.stdout)[-600:]
    ims = [np.array(Image.open(base / "out" / f"f{f}.png").convert("RGB")).astype(float) for f in frames]
    assert ims[0].shape[1] * 2 == size[0] and ims[0].shape[0] * 2 == size[1]
    assert all(im.std() > 8 for im in ims), [round(float(im.std()), 1) for im in ims]                   # not blank: a gradient, graphics and text
    steps = [float(np.abs(ims[i + 1] - ims[i]).mean()) for i in range(len(ims) - 1)]
    assert all(s > 0.3 for s in steps), steps                                                            # it moves between frames: not a static picture


# ---------- the motion branch ----------
def test_the_motion_plan_page_data_and_a_repeated_run(motion):
    c, pid, pdir = motion
    assert c.get(f"/projects/{pid}/motion").json()["plan"] is None
    assert c.post(f"/projects/{pid}/motion/run").status_code == 202
    assert wait_job(c, pid, timeout=240)["error"] is None
    d = c.get(f"/projects/{pid}/motion").json()
    assert d["planned"] and d["use_images"] is False and d["built"]["pictures"] == 0 and d["built"]["fps"] == 30 and d["mode"] == "custom_code"
    assert d["motion_animation"]["status"] == "generated" and len(d["motion_animation"]["scenes"]) == d["built"]["scenes"]
    assert d["plan"]["mode"] == "motion-only" and len(d["plan"]["scenes"]) == d["built"]["scenes"]
    s = stages(c, pid)
    assert [s[k]["status"] for k in ("motion_plan", "motion_gen", "motion_validation")] == ["completed"] * 3, s       # /motion/run = Planning -> Generation -> Validation
    from backend import motion_branch
    assert motion_branch.complete(pdir, "16:9")
    assert c.post(f"/projects/{pid}/motion/run").status_code == 202                                                  # nothing left to do: the finished steps are skipped
    assert wait_job(c, pid, timeout=240)["error"] is None
    assert motion_branch.complete(pdir, "16:9")


def test_a_changed_plan_makes_the_motion_branch_incomplete_again(motion):
    c, pid, pdir = motion
    c.post(f"/projects/{pid}/motion/run")
    wait_job(c, pid, timeout=240)
    assert stages(c, pid)["motion_gen"]["status"] == "completed"
    plan = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    plan["scenes"][0]["meaning"] += " and more"
    (pdir / "scene_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    s = stages(c, pid)
    assert s["motion_plan"]["status"] != "completed" and s["motion_gen"]["status"] != "completed"                      # no stale "completed"
