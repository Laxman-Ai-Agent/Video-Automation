"""Final QC, Stage 14 (backend/final_qc.py, its step and routes). The candidate is a REAL encoded mp4 (ffmpeg) that passed through the real Stage 13 publish path of a project approved through the real Stage 12 service; the media
checks run the real ffprobe / ffmpeg on it. The single-check tests build tiny videos with exactly one defect (black, frozen, corrupt, wrong size, silent, clipped, a silence inside the narration) and run that stage on them.
Run: python -m pytest tests/test_final_qc.py -q"""
import importlib
import json
import random
import shutil
import time

import pytest

from backend import final_qc as fq, media_probe as mprobe, render, render_video as rv

_rv = importlib.import_module("test_render_video")
_mo = importlib.import_module("test_motion_only_mode")
_v = importlib.import_module("test_motion_validation")
built, pd, good, client = _rv.built, _rv.pd, _rv.good, _rv.client
encode, approved, fake = _rv.encode, _rv.approved, _rv.fake
A = "16:9"
PROF = fq.PROFILES["standard"]


def rendered(d, good, monkeypatch):
    """An approved project whose final video was rendered, verified and published by Stage 13 (the renderer writes a real mp4)."""
    approved(d)
    monkeypatch.setattr(render, "render", fake(good))
    return rv.run(d, A)


def by_rule(rep, rule):
    return [c for c in rep["checks"] if c["rule_id"] == rule]


def stage_checks(sid, video, exp=None, cfg=None, data=None):
    """Run ONE media stage on a video and return its checks and its data."""
    q = fq.Q()
    q.stage = sid
    exp = exp or {"width": 1920, "height": 1080, "fps": 30, "frames": 60, "duration_seconds": 2.0}
    cfg = cfg or {"codec": "h264", "audio_enabled": True}
    cand = {"path": video, "sha256": mprobe.sha256_file(video), "size_bytes": video.stat().st_size}
    out = fq._media_stage(sid, q, video.parent, A, video, cand, exp, cfg, [], [], 30, PROF, data or {}, {"output": {"sha256": cand["sha256"]}})
    return q.checks, out


# ---------- provenance: only a verified render of the approved version is a candidate ----------
def test_there_is_nothing_to_judge_before_a_verified_render_and_no_report_is_green(pd):
    approved(pd)
    rep = fq.run(pd, A)
    assert rep["status"] == "blocked" and rep["candidate"]["sha256"] is None and by_rule(rep, "QC_CANDIDATE_RESOLVED")[0]["severity"] == "blocker"
    assert all(s["status"] == "skipped" for s in rep["stages"] if s["stage_id"] in ("file_integrity", "video_decode", "frame_quality"))      # nothing was measured, and it says so
    st = fq.state(pd, A)
    assert st["status"] == "blocked" and not st["delivery_gate"]["open"] and fq.gate(pd, A)


def test_a_video_that_stage_13_did_not_verify_is_never_judged_as_current(pd, good):
    approved(pd)
    shutil.copyfile(good, pd / "out.mp4")
    rep = fq.run(pd, A)
    assert rep["status"] == "blocked" and "no verified render report" in by_rule(rep, "QC_CANDIDATE_RESOLVED")[0]["message"]
    assert not list((pd / "final_qc_frames").glob("*.jpg")) if (pd / "final_qc_frames").exists() else True


# ---------- the real checks on a real candidate ----------
def test_a_rendered_candidate_gets_every_media_check_and_waits_for_the_llm_decision(pd, good, monkeypatch):
    rrep = rendered(pd, good, monkeypatch)
    rep = fq.run(pd, A)
    assert rep["status"] == "needs_review", [(c["rule_id"], c["message"][:120]) for c in rep["checks"] if c["status"] == "failed"]
    assert rep["candidate"]["sha256"] == rrep["output"]["sha256"] and rep["lineage"]["approved_timeline_fingerprint"] == rrep["input_fingerprints"]["approved_version"]
    assert [s["stage_id"] for s in rep["stages"]][:3] == ["run_initialization", "artifact_resolution", "provenance_gate"] and len(rep["stages"]) == 14
    for rule in ("QC_DIMENSIONS", "QC_FRAME_RATE", "QC_VIDEO_CODEC", "QC_AUDIO_STREAM", "QC_VIDEO_DECODES", "QC_DURATION", "QC_FRAME_COUNT_CONTAINER", "QC_FRAME_COUNT_DECODED", "QC_AUDIO_DECODES", "QC_AUDIO_LEVEL", "QC_SPEECH_NOT_CUT"):
        c = by_rule(rep, rule)
        assert c and all(x["status"] == "passed" for x in c), (rule, [x["message"] for x in c])
    assert by_rule(rep, "QC_VIDEO_DECODES")[0]["evidence"]["coverage"] == "full decode" and by_rule(rep, "QC_FRAME_COUNT_DECODED")[0]["evidence"]["observed"] == 2104
    samples = rep["evidence"]["frame_quality"]["data"]["samples"]
    assert len(samples) > 9 * 3 and all(s["decode_ok"] for s in samples) and {"first", "last", "entry", "mid", "pre_exit", "before_cut", "transition_mid"} <= {s["kind"] for s in samples}
    assert all((pd / "final_qc_frames" / s["file"]).is_file() for s in samples)
    # what could NOT be measured is said, never passed; nobody watches the video
    assert by_rule(rep, "QC_AV_CONTENT_SYNC")[0]["status"] == "requires_review" and by_rule(rep, "QC_EMPHASIS_ON_WORD")[0]["status"] == "not_run"
    assert by_rule(rep, "QC_TRANSITION_SMOOTHNESS")[0]["status"] == "requires_review" and by_rule(rep, "QC_LLM_REVIEW")[0]["status"] == "requires_review"
    assert rep["summary"]["llm_review_required"] and not rep["delivery_gate"]["open"] and any("nobody watched the video" in x for x in rep["limitations"])
    st = fq.state(pd, A)
    assert st["current"] and st["status"] == "needs_review" and not st["delivery_gate"]["open"]
    assert not (pd / "timeline_approval.json").exists()                                                          # QC approved nothing and rendered nothing


def test_the_same_file_is_not_decoded_again_and_a_new_rules_version_recomputes_everything(pd, good, monkeypatch):
    rendered(pd, good, monkeypatch)
    first = fq.run(pd, A)
    second = fq.run(pd, A)
    media = [s for s in second["stages"] if s["stage_id"] in fq.MEDIA_STAGES]
    assert all(s["cache"]["hit"] for s in media) and not any(s["cache"]["hit"] for s in first["stages"] if s["stage_id"] in fq.MEDIA_STAGES)
    assert [c["finding_id"] for c in second["findings"]] == [c["finding_id"] for c in first["findings"]] and len({c["finding_id"] + c["stage_id"] for c in second["checks"]}) == len(second["checks"])         # no duplicate findings
    monkeypatch.setattr(fq, "RULES_VERSION", fq.RULES_VERSION + ".next")
    third = fq.run(pd, A)
    assert not any(s["cache"]["hit"] for s in third["stages"] if s["stage_id"] in fq.MEDIA_STAGES)


# ---------- the decision: the Final QC LLM review's, bound to the exact file ----------
BLOCKER = {"severity": "blocker", "category": "quality", "message": "scene 8 text is cut off"}


def test_the_llm_decision_is_bound_to_the_files_hash_and_resolves_what_nothing_measured(pd, good, monkeypatch, llm_review_says):
    rendered(pd, good, monkeypatch)
    rep = fq.run(pd, A)
    out = fq.llm_decide(pd, A)
    ev = out["review"]
    assert out["outcome"] == "recorded" and out["status"] in fq.OK_STATUS and out["delivery_gate"]["open"]
    assert ev["reviewer_source"] == "llm" and ev["reviewer"] == "llm:stub/stub" and ev["candidate_sha256"] == rep["candidate"]["sha256"] and ev["coverage"]["playback_watched"] is False
    open_items = [c for c in out["report"]["checks"] if c["status"] in ("requires_review", "not_run") and c["rule_id"] != "QC_LLM_REVIEW"]
    assert all(c["resolution"] == ("accepted_with_reason" if c["finding_id"] in ev["accepted_findings"] else "reviewed_by_llm") for c in open_items)   # accepted warnings are named, the rest judged by the LLM
    assert fq.llm_decide(pd, A)["outcome"] == "already_recorded" and len(fq.state(pd, A)["reviews"]) == 1
    assert (pd / "llm_review_final.json").exists()                                                              # an approval renews Final Video's review


def test_a_rejecting_or_unavailable_llm_never_opens_the_gate(pd, good, monkeypatch, llm_review_says):
    from backend import llm_gateway

    def offline(req):
        raise RuntimeError("offline")
    rendered(pd, good, monkeypatch)
    fq.run(pd, A)
    from SYSTEM.policies import llm_review as _lr
    _lr.review_path(pd, "qc", A).unlink(missing_ok=True)                    # a review stored for these exact files is reused (no second LLM call): this test is about asking while the LLM is down
    with monkeypatch.context() as m:
        m.setattr(llm_gateway.gateway, "execute", offline)
        out = fq.llm_decide(pd, A)
    assert out["review"]["decision"] == "cannot_determine" and out["status"] == "needs_review" and not out["delivery_gate"]["open"]
    llm_review_says("blocked", 0.3, [BLOCKER])
    out = fq.llm_decide(pd, A)
    assert out["review"]["decision"] == "changes_required" and out["status"] == "failed" and not out["delivery_gate"]["open"]
    assert any("scene 8" in n for n in out["report"]["llm_review"]["notes"])


def test_a_second_qc_run_of_the_same_file_is_decided_again(pd, good, monkeypatch, llm_review_says):
    rendered(pd, good, monkeypatch)
    fq.run(pd, A)
    assert fq.llm_decide(pd, A)["status"] in fq.OK_STATUS
    llm_review_says("blocked", 0.3, [BLOCKER])
    fq.run(pd, A)                                                                                                # a new run keeps the old approval of the same file until the LLM decides again
    out = fq.llm_decide(pd, A)
    assert out["outcome"] == "recorded" and out["review"]["decision"] == "changes_required"
    assert out["status"] == "failed" and not out["delivery_gate"]["open"] and len(fq.state(pd, A)["reviews"]) == 2


def test_an_approval_whose_audit_does_not_pass_is_voided(pd, good, monkeypatch):
    from SYSTEM.policies import llm_review as lr
    rendered(pd, good, monkeypatch)
    fq.run(pd, A)
    answers = iter([{"status": "passed", "score": 0.9, "summary": "ok", "findings": []},
                    {"status": "blocked", "score": 0.2, "summary": "the decision contradicts the report", "findings": [BLOCKER]}])
    monkeypatch.setattr(lr, "run_stage_llm_review", lambda *a, **k: {"provider": "stub", "model": "stub", **next(answers)})
    out = fq.llm_decide(pd, A)
    assert out["review"] is None and not out["delivery_gate"]["open"]
    assert fq.state(pd, A)["reviews"][-1]["voided"].startswith("the Final QC LLM audit did not pass")


def test_a_new_video_makes_the_old_report_and_the_old_decision_stale(pd, good, tmp_path, monkeypatch, llm_review_says):
    rendered(pd, good, monkeypatch)
    rep = fq.run(pd, A)
    fq.llm_decide(pd, A)
    assert fq.state(pd, A)["delivery_gate"]["open"]
    other = encode(tmp_path / "other.mp4", extra=("-metadata", "title=again"))
    monkeypatch.setattr(render, "render", fake(other))
    rv.run(pd, A)                                                                                                # a re-render: other bytes, other hash
    st = fq.state(pd, A)
    assert st["status"] == "stale" and st["stale"] and not st["delivery_gate"]["open"] and fq.gate(pd, A)
    with pytest.raises(fq.QcError) as e:
        fq.llm_decide(pd, A)                                                                                     # the report is of the OLD file: no decision is recorded on the new one
    assert e.value.code == "candidate_changed"
    fresh = fq.run(pd, A)
    assert fresh["status"] == "needs_review" and fresh["candidate"]["sha256"] != rep["candidate"]["sha256"]       # the old approval does not carry over


def test_a_changed_approval_after_the_render_blocks_the_qc(pd, good, monkeypatch):
    rendered(pd, good, monkeypatch)
    _rv._ta.touch(pd)                                                                                            # the approved version changes after the render
    rep = fq.run(pd, A)
    assert rep["status"] == "blocked" and by_rule(rep, "QC_APPROVAL_CURRENT")[0]["status"] == "failed" and not fq.state(pd, A)["delivery_gate"]["open"]


def test_an_approval_names_every_open_warning_and_the_warnings_stay_visible(pd, tmp_path, monkeypatch, llm_review_says):
    static = encode(tmp_path / "static.mp4", src="smptebars=size={w}x{h}:rate={fps}")                          # a real video whose picture never changes: frozen run (warning), no blank scene
    rendered(pd, static, monkeypatch)
    rep = fq.run(pd, A)
    warns = [c["finding_id"] for c in rep["findings"] if c["severity"] == "warning"]
    assert warns and by_rule(rep, "QC_FROZEN_RUN") and rep["status"] == "needs_review"
    out = fq.llm_decide(pd, A)
    assert out["review"]["decision"] == "approved_with_accepted_risks" and sorted(out["review"]["accepted_findings"]) == sorted(warns)
    assert out["status"] == "passed_with_warnings" and out["delivery_gate"]["open"]
    shown = [c for c in out["report"]["checks"] if c["finding_id"] in warns]
    assert shown and all(c["status"] != "passed" and c["resolution"] == "accepted_with_reason" for c in shown)    # accepted is a resolution status: the warning is still there


# ---------- single checks on tiny videos with exactly one defect ----------
def test_black_and_frozen_pictures_are_found_as_warnings_not_called_errors(tmp_path):
    black = encode(tmp_path / "b.mp4", w=320, h=180, frames=60, src="color=c=black:s={w}x{h}:r={fps}", audio=False)
    _, out = stage_checks("video_decode", black)
    assert out["black"] and out["black"][0][1] - out["black"][0][0] >= 1.9
    still = encode(tmp_path / "s.mp4", w=320, h=180, frames=240, src="smptebars=size={w}x{h}:rate={fps}", audio=False)
    checks, out = stage_checks("video_decode", still, exp={"width": 320, "height": 180, "fps": 30, "frames": 240, "duration_seconds": 8.0})
    assert out["freeze"] and out["freeze"][0][1] - out["freeze"][0][0] >= 3.0 and next(c for c in checks if c["rule_id"] == "QC_VIDEO_DECODES")["status"] == "passed"


def test_a_corrupted_file_fails_the_decode_check(tmp_path):
    v = encode(tmp_path / "v.mp4", w=640, h=360, frames=120, audio=False)
    data = bytearray(v.read_bytes())
    rnd = random.Random(7)
    for i in range(int(len(data) * 0.35), int(len(data) * 0.7)):
        data[i] = rnd.randrange(256)
    v.write_bytes(bytes(data))
    checks, _ = stage_checks("video_decode", v, exp={"width": 640, "height": 360, "fps": 30, "frames": 120, "duration_seconds": 4.0})
    d = next(c for c in checks if c["rule_id"] == "QC_VIDEO_DECODES")
    assert d["status"] == "failed" and d["severity"] == "blocker" and "decode problems" in d["message"]


def test_the_wrong_size_the_wrong_rate_and_a_missing_audio_stream_are_reported_against_the_manifest(tmp_path):
    v = encode(tmp_path / "v.mp4", w=640, h=360, frames=50, fps=25, audio=False)
    checks, data = stage_checks("stream_metadata", v)
    by = {c["rule_id"]: c for c in checks}
    assert by["QC_DIMENSIONS"]["status"] == "failed" and by["QC_FRAME_RATE"]["status"] == "failed" and by["QC_AUDIO_STREAM"]["status"] == "failed" and by["QC_AUDIO_STREAM"]["severity"] == "blocker"
    assert by["QC_DIMENSIONS"]["evidence"] == {"expected": [1920, 1080], "observed": [640, 360]} and data["observed"]["audio_present"] is False


@pytest.mark.parametrize("a_src, status", [("anullsrc=r=48000:cl=mono", "failed"), ("sine=frequency=440:sample_rate=48000,volume=8,alimiter=limit=1:level=disabled", "warning")])
def test_a_silent_or_clipped_audio_track_is_reported(tmp_path, a_src, status):
    exp = {"width": 320, "height": 180, "fps": 30, "frames": 90, "duration_seconds": 3.0}
    v = encode(tmp_path / "v.mp4", w=320, h=180, frames=90, a_src=a_src)
    meta = stage_checks("stream_metadata", v, exp=exp)[1]
    checks, _ = stage_checks("audio_integrity", v, exp=exp, data={"stream_metadata": meta})
    assert next(c for c in checks if c["rule_id"] == "QC_AUDIO_LEVEL")["status"] == status


def test_a_silence_inside_the_narration_is_a_warning_and_one_after_the_last_word_is_not(tmp_path, monkeypatch):
    v = encode(tmp_path / "v.mp4", w=320, h=180, frames=360, a_src="sine=frequency=440:sample_rate=48000,volume=enable='between(t,4,9)':volume=0")
    exp = {"width": 320, "height": 180, "fps": 30, "frames": 360, "duration_seconds": 12.0}
    meta = stage_checks("stream_metadata", v, exp=exp)[1]
    monkeypatch.setattr(fq, "_words", lambda *a: [{"end": 11.5}])                                               # speech continues after the silence: it is inside the narration
    checks, _ = stage_checks("audio_integrity", v, exp=exp, data={"stream_metadata": meta})
    s = next(c for c in checks if c["rule_id"] == "QC_AUDIO_SILENCE")
    assert s["status"] == "warning" and s["severity"] == "warning" and "inside the narration" in s["message"]
    monkeypatch.setattr(fq, "_words", lambda *a: [{"end": 3.9}])                                                # the last word ended before the silence: an ending, not a fault
    checks, _ = stage_checks("audio_integrity", v, exp=exp, data={"stream_metadata": meta})
    assert next(c for c in checks if c["rule_id"] == "QC_AUDIO_SILENCE")["status"] == "passed"


def test_speech_that_is_cut_off_by_the_end_of_the_video_is_an_error(tmp_path, monkeypatch):
    v = encode(tmp_path / "v.mp4", w=320, h=180, frames=90)
    exp = {"width": 320, "height": 180, "fps": 30, "frames": 90, "duration_seconds": 3.0}
    meta = stage_checks("stream_metadata", v, exp=exp)[1]
    monkeypatch.setattr(fq, "_words", lambda *a: [{"end": 3.4}])
    checks, _ = stage_checks("audio_integrity", v, exp=exp, data={"stream_metadata": meta})
    c = next(c for c in checks if c["rule_id"] == "QC_SPEECH_NOT_CUT")
    assert c["status"] == "failed" and c["severity"] == "error" and "cut off" in c["message"]


def test_the_sampling_rule_covers_first_last_scenes_cuts_and_transitions_and_short_scenes_are_not_sampled_twice():
    clips = [{"scene_id": "scene_001", "start_frame": 0, "end_frame": 100}, {"scene_id": "scene_002", "start_frame": 100, "end_frame": 104}]
    trans = [{"transition_id": "t", "to_scene": "scene_002", "start_frame": 100, "end_frame": 104}]
    frames = [s["frame"] for s in fq.sample_plan(clips, trans, 104, PROF)]
    assert frames == sorted(set(frames)) and 0 in frames and 103 in frames and 98 in frames and 100 in frames and all(0 <= f < 104 for f in frames)


# ---------- the status algorithm ----------
def chk(status, severity, rule="X"):
    return {"finding_id": f"{rule}:{status}:{severity}", "rule_id": rule, "status": status, "severity": severity, "resolution": "unresolved"}


def test_one_blocker_is_never_outweighed_by_passes_and_a_decision_is_needed_for_passed():
    passes = [chk("passed", "info", f"P{i}") for i in range(500)]
    rev = {"decision": "approved"}
    assert fq.aggregate(passes + [chk("failed", "blocker")], rev, False)[0] == "failed"
    assert fq.aggregate(passes, rev, True)[0] == "blocked"
    assert fq.aggregate(passes, None, False)[0] == "needs_review"
    assert fq.aggregate(passes, {"decision": "cannot_determine"}, False)[0] == "needs_review"
    assert fq.aggregate(passes, rev, False)[0] == "passed"
    assert fq.aggregate(passes + [chk("warning", "warning")], rev, False)[0] == "passed_with_warnings"
    assert fq.aggregate(passes + [chk("warning", "info")], rev, False)[0] == "passed"                           # an info observation (an optional element not drawn) is visible but is not a warning
    assert fq.aggregate(passes, {"decision": "changes_required"}, False)[0] == "failed"


# ---------- the step and the API, end to end ----------
def test_the_api_runs_final_qc_records_a_decision_and_moves_the_pipeline_stages(client, tmp_path, monkeypatch, llm_review_says):
    c = client
    pid, pdir = _v.api_project(c)
    assert c.get(f"/projects/{pid}/final-qc").json()["status"] == "blocked" and c.post(f"/projects/{pid}/final-qc/cancel").status_code == 409
    assert c.post(f"/projects/{pid}/motion-timeline-validation/run").status_code == 202 and _mo.wait_job(c, pid, timeout=240)["error"] is None
    monkeypatch.setattr(fq, "_words", lambda *a: [])                                                              # (the fixture's audio does not hold its transcript: the speech check has its own tests)
    assert c.post(f"/projects/{pid}/timeline-build/run").status_code == 202 and _mo.wait_job(c, pid, timeout=240)["error"] is None   # build -> LLM approval -> render -> Final QC checks
    st = c.get(f"/projects/{pid}/render-video").json()
    assert st["status"] == "completed" and st["output"]["current"]
    stages = _mo.stages(c, pid)
    assert stages["render"]["status"] == "completed" and stages["qc"]["status"] == "completed" and stages["final"]["status"] == "completed"   # the render ran Final QC and its LLM decision
    q = c.get(f"/projects/{pid}/final-qc").json()                                                                # the render ran Final QC and the LLM decision: the gate is open
    assert q["status"] in fq.OK_STATUS and q["current"] and q["candidate"]["sha256"] == st["output"]["sha256"] and q["delivery_gate"]["open"]
    assert q["reviews"][-1]["reviewer_source"] == "llm" and q["reviews"][-1]["decision"] in ("approved", "approved_with_accepted_risks")
    assert c.post(f"/projects/{pid}/final-qc/llm-decide").json()["outcome"] == "already_recorded"                  # the route reuses the decision of this run
    f = next(x for x in q["report"]["checks"] if x["status"] == "requires_review")
    assert c.get(f"/projects/{pid}/final-qc/findings/{f['finding_id']}").json()["rule_id"] == f["rule_id"] and c.get(f"/projects/{pid}/final-qc/findings/nope").status_code == 404
    name = q["report"]["evidence"]["frame_quality"]["data"]["samples"][0]["file"]
    assert c.get(f"/projects/{pid}/final-qc/frame/{name}").headers["content-type"] == "image/jpeg" and c.get(f"/projects/{pid}/final-qc/frame/..%2Fproject.json").status_code in (404, 422)



def test_a_voided_review_never_counts_as_a_decision(tmp_path):
    """A voided decision (e.g. one whose audit did not pass) stays in the history but is not the current decision."""
    import json as _json
    from backend import final_qc as fq
    ev = {"review_id": "qcr_x", "decision": "approved", "reviewer": "software", "candidate_sha256": "abc", "coverage": {"playback_watched": True}}
    (tmp_path / fq.names("16:9")["review"]).write_text(_json.dumps({"events": [dict(ev, voided="the audit did not pass")]}), encoding="utf-8")
    assert fq.current_review(tmp_path, "16:9", "abc") is None
    (tmp_path / fq.names("16:9")["review"]).write_text(_json.dumps({"events": [ev]}), encoding="utf-8")
    assert fq.current_review(tmp_path, "16:9", "abc")["review_id"] == "qcr_x"


def test_only_final_qc_records_a_decision_and_no_step_delivers_on_its_own():
    """A Final QC decision is recorded only by final_qc.llm_decide; no step or agent writes a decision record itself, or delivers the video on its own."""
    import re
    from pathlib import Path
    roots = [Path(__file__).resolve().parent.parent / d for d in ("VIDEO_ENGINE", "SYSTEM")]
    offenders = [str(f) for r in roots for f in r.rglob("*.py")
                 if re.search(r"_append_review\(|deliver_to_desktop\(", f.read_text(encoding="utf-8", errors="ignore")) and f.name not in ("final_qc.py", "agent.py")]
    assert offenders == [], offenders
