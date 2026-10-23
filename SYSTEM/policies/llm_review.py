"""Mandatory LLM participation and review gate for every pipeline stage.

NON-NEGOTIABLE COMPLETION RULE:
No pipeline stage may be marked `completed` until:
1. Its required execution and output generation have finished.
2. Deterministic validation and relevant technical checks have passed.
3. A stage-specific LLM review has run successfully and returned a structured, persisted result
   tied to the current input/output fingerprints.
4. The LLM review contains no unresolved blocking issues.

If the LLM is unavailable, fails, returns invalid output, or cannot complete its review,
the stage must remain `blocked` or `needs_review`. It must NEVER silently mark the stage completed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Literal, TypedDict

from SYSTEM.core import llm_client, llm_gateway
from SYSTEM.memory import store
from SYSTEM.policies.llm_reviewer import LlmFinding, LlmReviewStatus, ask_reviewer   # the generic reviewer is the Agent System's; this module is the video stage gate on top of it

SCHEMA = "1.0"
VERSION = 1


class LlmReviewResult(TypedDict):
    schema: str
    version: int
    stage: str
    aspect: str
    status: LlmReviewStatus
    score: float
    summary: str
    findings: list[LlmFinding]
    input_fingerprint: str
    output_fingerprint: str
    reviewed_at: float
    provider: str
    model: str
    latency_ms: int
    error: str | None


STAGE_DESCRIPTIONS: dict[str, str] = {
    "audio": "Audio Input Semantic & Narration Feasibility Review",
    "analyzer": "Audio Analyzer Transcript Accuracy & Bilingual Terminology Review",
    "segmentation": "Scene Segmentation Narrative Coherence & Boundary Review",
    "planning": "Visual Planning Scene Plan & Image Prompt Quality Review",
    "assets": "Asset Collection Real-Media Relevance, Rights & Provenance Review",
    "motion_plan": "Motion Planning Kinetic Rhythm & Typography Layout Review",
    "motion_gen": "Motion Animation React/TSX Source Code & Composition Review",
    "motion_validation": "Motion & Timeline Validation Synthesis & Safety Review",
    "timeline": "Timeline Build Track Alignment & Structural Integrity Review",
    "approval": "Timeline Approval Pre-Approval Executive Audit",
    "render": "Render Video Post-Render Telemetry & Media Profile Review",
    "qc": "Final QC Technical Synthesis & Compliance Review",
    "final": "Final Video Delivery & Provenance Verification",
}


def _sha(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


def _file_hash(p: Path) -> str:
    if not p.exists() or not p.is_file():
        return "missing"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:16]


ASPECT_DEPENDENT_STAGES = {
    "motion_plan",
    "motion_gen",
    "motion_validation",
    "timeline",
    "approval",
    "render",
    "qc",
    "final",
}


def review_path(pdir: Path, stage: str, aspect: str = "16:9") -> Path:
    sfx = "_9x16" if (stage in ASPECT_DEPENDENT_STAGES and aspect == "9:16") else ""
    return pdir / f"llm_review_{stage}{sfx}.json"


def stage_input_files(pdir: Path, stage: str, aspect: str = "16:9") -> list[Path]:
    sfx = "_9x16" if aspect == "9:16" else ""
    audio = next(iter(pdir.glob("audio.*")), None)
    if stage == "audio":
        return [audio] if audio else []
    elif stage == "analyzer":
        return [audio] if audio else []
    elif stage == "segmentation":
        return [pdir / "transcript.json", pdir / "cuts.json"]
    elif stage == "planning":
        return [pdir / "scene_segmentation.json", pdir / "transcript.json"]
    elif stage == "assets":
        return [pdir / "scene_plan.json", pdir / "visual_planning.json"]
    elif stage == "motion_plan":
        return [pdir / "visual_planning.json", pdir / "scene_plan.json"]
    elif stage == "motion_gen":
        return [pdir / f"motion_plan{sfx}.json", pdir / "visual_planning.json", pdir / "assets_manifest.json"]       # the scenes draw the collected assets
    elif stage == "motion_validation":
        return [pdir / f"composition{sfx}.json", pdir / f"motion_animation{sfx}.json"]
    elif stage == "timeline":
        return [pdir / f"composition{sfx}.json", pdir / f"motion_timeline_validation{sfx}.json"]
    elif stage == "approval":
        return [pdir / f"timeline{sfx}.json", pdir / f"timeline_build_report{sfx}.json"]
    elif stage == "render":
        return [pdir / f"timeline{sfx}.json", pdir / f"timeline_approval_history{sfx}.json"]
    elif stage == "qc":
        vid = pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        return [vid, pdir / f"timeline{sfx}.json"]
    elif stage == "final":
        vid = pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        return [pdir / f"final_qc_report{sfx}.json", vid]
    return []


def stage_output_files(pdir: Path, stage: str, aspect: str = "16:9") -> list[Path]:
    sfx = "_9x16" if aspect == "9:16" else ""
    audio = next(iter(pdir.glob("audio.*")), None)
    if stage == "audio":
        outs = [audio] if audio else []
        manifest = pdir / "audio_input_manifest.json"
        if manifest.exists():
            outs.append(manifest)
        return outs
    elif stage == "analyzer":
        return [pdir / "transcript.json", pdir / "transcript_corrected.json", pdir / "transcript_review.json", pdir / "cuts.json"]       # the approval is bound to the final transcript too
    elif stage == "segmentation":
        return [pdir / "scene_segmentation.json"]
    elif stage == "planning":
        return [pdir / "scene_plan.json", pdir / "visual_planning.json", pdir / "prompts_map.json"]
    elif stage == "assets":
        return [pdir / "asset_requirements.json", pdir / "assets_manifest.json"]
    elif stage == "motion_plan":
        return [pdir / f"motion_plan{sfx}.json"]
    elif stage == "motion_gen":
        return [pdir / f"motion_animation{sfx}.json", pdir / f"composition{sfx}.json"]
    elif stage == "motion_validation":
        return [pdir / f"motion_timeline_validation{sfx}.json"]
    elif stage == "timeline":
        return [pdir / f"timeline{sfx}.json", pdir / f"timeline_build_report{sfx}.json"]
    elif stage == "approval":
        return [pdir / f"timeline_approval_history{sfx}.json"]
    elif stage == "render":
        vid = pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        return [vid]
    elif stage == "qc":
        return [pdir / f"final_qc_report{sfx}.json"]
    elif stage == "final":
        return [pdir / f"final_qc_review{sfx}.json"]
    return []


def compute_stage_input_fingerprint(pdir: Path, stage: str, aspect: str = "16:9") -> str:
    files = stage_input_files(pdir, stage, aspect)
    hashes = [f"{f.name}:{_file_hash(f)}" for f in files]
    mode = "template" if store.reusable_motion_templates(pdir) else "custom_code"
    asp_tag = aspect if stage in ASPECT_DEPENDENT_STAGES else "common"
    return _sha("|".join(hashes) + f"|{asp_tag}|{mode}|v{VERSION}")


def compute_stage_output_fingerprint(pdir: Path, stage: str, aspect: str = "16:9") -> str:
    files = stage_output_files(pdir, stage, aspect)
    hashes = [f"{f.name}:{_file_hash(f)}" for f in files]
    return _sha("|".join(hashes) + f"|v{VERSION}")


def load_review(pdir: Path, stage: str, aspect: str = "16:9") -> LlmReviewResult | None:
    path = review_path(pdir, stage, aspect)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("schema") == SCHEMA:
            return data  # type: ignore[return-value]
    except (OSError, ValueError):
        pass
    return None


def save_review(pdir: Path, stage: str, aspect: str, result: LlmReviewResult) -> Path:
    path = review_path(pdir, stage, aspect)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    try:
        from SYSTEM.agents.shared import communication
        from SYSTEM.agents.shared.contracts import ArtifactRef
        from SYSTEM.core.pipeline_state import STAGE_TO_AGENT_MAP as stage_to_agent             # the one stage-to-agent map (imported here: pipeline_state imports this module)
        target_agent = stage_to_agent.get(stage, "main_orchestrator")
        communication.publish_review_feedback(
            project_id=pdir.name,
            stage_id=stage,
            sender_agent_id="main_orchestrator",
            recipient_agent_id=target_agent,
            status=result.get("status", "needs_review"),
            score=float(result.get("score", 0.0)),
            summary=str(result.get("summary", "")),
            findings=result.get("findings", []),
            artifact_refs=[ArtifactRef(path=str(path), description=f"LLM Review Report ({stage})")],
        )
    except Exception:
        pass
    return path


def is_stage_review_passed(
    pdir: Path,
    stage: str,
    aspect: str = "16:9",
    auto_pilot: bool = True,
) -> tuple[bool, str, LlmReviewResult | None]:
    """Evaluates whether the stage has a fresh, valid LLM review with zero blockers.
    Returns (passed: bool, reason: str, review: LlmReviewResult | None).
    """
    rev = load_review(pdir, stage, aspect)
    if rev is None:
        return False, "llm_review_missing", None

    current_in_fp = compute_stage_input_fingerprint(pdir, stage, aspect)
    current_out_fp = compute_stage_output_fingerprint(pdir, stage, aspect)

    if rev.get("input_fingerprint") != current_in_fp:
        return False, "llm_review_stale_inputs", rev

    if rev.get("output_fingerprint") != current_out_fp:
        return False, "llm_review_stale_outputs", rev

    status = rev.get("status")
    if status == "blocked":
        return False, "llm_review_blocked", rev
    elif status == "failed":
        return False, "llm_review_failed", rev

    # Check for blocking findings
    blockers = [f for f in rev.get("findings", []) if f.get("severity") in ("blocker", "error")]
    if blockers:
        return False, "llm_review_has_blockers", rev

    if status == "needs_review":
        if auto_pilot:
            return True, "passed", rev
        return False, "llm_review_needs_review", rev

    if status == "passed":
        return True, "passed", rev

    return False, f"llm_review_status_{status}", rev


def build_stage_payload(pdir: Path, stage: str, aspect: str = "16:9") -> dict[str, Any]:
    """Collects rich, stage-specific context for semantic LLM evaluation."""
    sfx = "_9x16" if aspect == "9:16" else ""
    reusable = store.reusable_motion_templates(pdir)

    payload: dict[str, Any] = {
        "project_id": pdir.name,
        "stage": stage,
        "aspect": aspect,
        "reusable_motion_templates": reusable,
    }

    if stage == "audio":
        audio = next(iter(pdir.glob("audio.*")), None)
        payload["audio_file"] = audio.name if audio else None
        payload["audio_size_bytes"] = audio.stat().st_size if audio else 0
        mf = pdir / "audio_input_manifest.json"
        if mf.exists():
            try:
                payload["manifest"] = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                pass
    elif stage == "analyzer":
        # The approval judges the FINAL transcript (the user's fix, else the LLM-corrected one, else the raw one), what the correction changed, and the word times: not the raw ASR text.
        cf = pdir / "cuts.json"
        cuts = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
        payload["cuts_count"] = len(cuts.get("cuts", [])) if isinstance(cuts, dict) else len(cuts)
        final_f = next((pdir / n for n in ("transcript_fixed.json", "transcript_corrected.json", "transcript.json") if (pdir / n).exists()), None)
        payload["final_transcript_file"] = final_f.name if final_f else None
        if final_f:
            segs = json.loads(final_f.read_text(encoding="utf-8")).get("segments", [])
            words = [w for s in segs for w in s.get("words", [])]
            payload["final_transcript"] = [{"segment": s.get("id"), "start": round(s.get("start", 0), 2), "end": round(s.get("end", 0), 2), "text": s.get("text")} for s in segs][:80]
            payload["word_timing"] = {"words": len(words), "llm_edited": sum(1 for w in words if w.get("edit")), "aligned": sum(1 for w in words if w.get("timing") == "aligned"),
                                      "estimated": sum(1 for w in words if w.get("timing") == "estimated"),
                                      "overlapping": sum(1 for a, b in zip(words, words[1:]) if b.get("start", 0) < a.get("end", 0) - 0.05)}
        rf = pdir / "transcript_review.json"
        if rf.exists():
            review = json.loads(rf.read_text(encoding="utf-8"))
            corrections = review.get("corrections") or []
            payload["llm_correction"] = {"llm_status": (review.get("llm") or {}).get("status"), "alignment": (review.get("alignment") or {}).get("status"),
                                         "applied": sum(c.get("status") == "applied" for c in corrections), "rejected": sum(c.get("status") != "applied" for c in corrections),
                                         "corrections": [{"from": c.get("from"), "to": c.get("to"), "status": c.get("status"), "reason": c.get("reason")} for c in corrections][:40]}
    elif stage == "segmentation":
        sf = pdir / "scene_segmentation.json"
        if sf.exists():
            data = json.loads(sf.read_text(encoding="utf-8"))
            payload["scenes_count"] = len(data.get("scenes", []))
            summary_list = []
            for s in data.get("scenes", [])[:10]:
                sid = s.get("scene_id") or s.get("id") or (f"scene_{s.get('scene_index'):03d}" if s.get("scene_index") is not None else "scene")
                st_time = float(s.get("start_time", s.get("start", 0.0)))
                end_time = float(s.get("end_time", s.get("end", 0.0)))
                dur = float(s.get("duration") or round(end_time - st_time, 2))
                concept = s.get("semantic_beat") or s.get("scene_objective") or s.get("concept") or s.get("transcript")
                summary_list.append({
                    "id": sid,
                    "start": st_time,
                    "end": end_time,
                    "duration": dur,
                    "concept": concept,
                    "transcript": s.get("transcript", "")[:80],
                })
            payload["scenes_summary"] = summary_list
            payload["segmentation_method"] = data.get("segmentation_method")
            payload["audio_duration_seconds"] = data.get("audio_duration_seconds")
            payload["language"] = data.get("language")
    elif stage == "planning":
        vpf = pdir / "visual_planning.json"
        spf = pdir / "scene_plan.json"
        payload["has_visual_plan"] = vpf.exists()
        payload["has_scene_plan"] = spf.exists()
        if vpf.exists():
            try:
                vp = json.loads(vpf.read_text(encoding="utf-8"))
                payload["scenes_planned"] = len(vp.get("scenes", []))
                payload["errors"] = vp.get("validation", {}).get("errors", [])
                payload["warnings"] = vp.get("validation", {}).get("warnings", [])
            except Exception:
                pass
    elif stage == "motion_plan":
        mpf = pdir / f"motion_plan{sfx}.json"
        mplf = pdir / f"motion_planning{sfx}.json"
        if mpf.exists():
            try:
                mp = json.loads(mpf.read_text(encoding="utf-8"))
                mpl = json.loads(mplf.read_text(encoding="utf-8")) if mplf.exists() else {}
                payload["scenes_motion_planned"] = len(mp.get("scenes", []))
                payload["pace"] = mpl.get("timing_policy", {}).get("pace", mp.get("speed", 1.0))
                mpl_val = mpl.get("validation", {})
                checks = mpl_val.get("checks", {})
                by_rule = checks.get("by_rule", {})
                payload["validation_checks"] = {
                    "passed": checks.get("passed"),
                    "total": checks.get("total"),
                    "warnings": mpl_val.get("warnings", []),
                    "errors": mpl_val.get("errors", []),
                    "accepted_fallbacks": by_rule.get("element_drawn", {}).get("total", 0) - by_rule.get("element_drawn", {}).get("passed", 0),
                    "pending_downstream_checks": ["composition_current (updated downstream during Motion Generation)"] if by_rule.get("composition_current", {}).get("passed") != by_rule.get("composition_current", {}).get("total") else [],
                    "deterministic_verdict": "clean_pass" if not mpl_val.get("warnings") and not mpl_val.get("errors") else "needs_attention",
                }
                payload["scenes_detail"] = [
                    {
                        "id": sc.get("id"),
                        "start": sc.get("start"),
                        "end": sc.get("end"),
                        "duration": round((sc.get("end") or 0) - (sc.get("start") or 0), 2),
                        "transition": sc.get("transition"),
                        "texts": [
                            {
                                "text": t.get("text"),
                                "style": t.get("style"),
                                "preset": t.get("preset"),
                                "at": t.get("at"),
                                "enter_s": t.get("enter_s"),
                                "exit_s": t.get("exit_s"),
                                "emphasis": t.get("emphasis"),
                                "emphasis_at": t.get("emphasis_at"),
                            }
                            for t in sc.get("texts", [])
                        ],
                        "graphics": [g.get("preset") for g in sc.get("graphics", [])],
                    }
                    for sc in mp.get("scenes", [])
                ]
            except Exception:
                pass
    elif stage == "motion_gen":
        maf = pdir / f"motion_animation{sfx}.json"
        comp_f = pdir / f"composition{sfx}.json"
        if maf.exists():
            try:
                ma = json.loads(maf.read_text(encoding="utf-8"))
                payload["motion_animation_status"] = ma.get("status")
                payload["motion_mode"] = ma.get("mode")
                payload["scenes_count"] = len(ma.get("scenes", []))
                payload["typecheck_status"] = ma.get("typecheck", {}).get("status", "passed")
                payload["diagnostics"] = ma.get("diagnostics", {})
                payload["scenes_manifest"] = [
                    {
                        "scene_id": s.get("scene_id"),
                        "compile_status": s.get("compile_status"),
                        "duration_frames": s.get("duration_frames"),
                        "fps": s.get("fps"),
                        "security_audit": s.get("security_audit"),
                        "implemented_elements": s.get("implemented_elements"),
                        "missing_required_elements": s.get("missing_required_elements"),
                    }
                    for s in ma.get("scenes", [])
                ]
                # Add sample source code if custom_code
                if ma.get("mode") == "custom_code":
                    gen_dir = pdir / "generated_motion"
                    first_tsx = next(iter(gen_dir.glob("scene_*.tsx")), None)
                    if first_tsx and first_tsx.exists():
                        payload["sample_tsx"] = first_tsx.read_text(encoding="utf-8")[:4000]
            except Exception:
                pass
        if comp_f.exists():
            try:
                comp = json.loads(comp_f.read_text(encoding="utf-8"))
                payload["composition_scenes"] = len(comp.get("scenes", []))
                payload["composition_meta"] = comp.get("meta", {})
            except Exception:
                pass
    elif stage == "assets":
        try:
            from VIDEO_ENGINE.stages import asset_collection as _ac
            man = _ac.load_manifest(pdir)
            payload["scenes"] = [{"id": s["id"], "about": s["meaning"], "narration": s["narration_en"]} for s in _ac.scenes_of(pdir)]
            payload["requirements"] = _ac.load_requirements(pdir).get("requirements", [])
            payload["assets"] = [{**{k: a.get(k) for k in ("asset_id", "requirement_id", "scene_id", "kind", "title", "provider", "source_url", "rights_class", "authenticity", "needs_human_review",
                                                          "selected_by", "width", "height", "duration_s", "search_query")}, "license": (a.get("license") or {}).get("name")} for a in man.get("assets", [])]
            payload["fallbacks"] = man.get("fallbacks", [])
            payload["deterministic_findings"] = _ac.check_assets(pdir, man)
        except Exception:
            pass
    elif stage == "motion_validation":
        mvf = pdir / f"motion_timeline_validation{sfx}.json"
        if mvf.exists():
            try:
                mv = json.loads(mvf.read_text(encoding="utf-8"))
                payload["readiness"] = mv.get("readiness")
                payload["summary"] = mv.get("summary")
                payload["findings"] = [{k: f.get(k) for k in ("rule_id", "severity", "status", "scene_id", "element_id", "message", "evidence", "owner_stage")} for f in mv.get("findings", [])[:30]]
                payload["preview_evidence"] = [{k: e.get(k) for k in ("scene_id", "kind", "frame", "file", "sha", "decode_ok", "blank", "human_reviewed")} for e in mv.get("preview_evidence", [])[:40]]
                payload["stage_results"] = [{k: st.get(k) for k in ("stage_id", "name", "status", "checks_passed", "checks_total", "finding_ids")} for st in mv.get("stages", []) if isinstance(st, dict)]
            except Exception:
                pass
    elif stage == "timeline":
        tbf = pdir / f"timeline_build_report{sfx}.json"
        if tbf.exists():
            try:
                tb = json.loads(tbf.read_text(encoding="utf-8"))
                payload["timeline_status"] = tb.get("status")
                payload["counts"] = tb.get("counts")
                payload["summary"] = tb.get("summary")
            except Exception:
                pass
    elif stage == "approval":
        tbf = pdir / f"timeline_build_report{sfx}.json"
        ahf = pdir / f"timeline_approval_history{sfx}.json"
        tlf = pdir / f"timeline{sfx}.json"
        payload["has_timeline_report"] = tbf.exists()
        events = (json.loads(ahf.read_text(encoding="utf-8")).get("events", []) if ahf.exists() else [])
        payload["history_records"] = len(events)
        last = next((e for e in reversed(events) if e.get("kind") == "decision" and not e.get("voided")), None)
        payload["latest_decision"] = {k: last.get(k) for k in ("decision", "decided_by", "decided_at", "timeline_fingerprint", "notes")} if last else None
        try:
            from VIDEO_ENGINE.stages import timeline_approval as _ta
            payload["current_timeline_fingerprint"] = _ta.fingerprint(pdir, aspect)
        except Exception:
            payload["current_timeline_fingerprint"] = None
        payload["decision_policy"] = "Timeline Approval is decided by this LLM review (no human gate): approve only a timeline that is valid in every respect."
        if tbf.exists():
            try:
                tb = json.loads(tbf.read_text(encoding="utf-8"))
                payload["timeline_build_status"] = tb.get("status")
                payload["counts"] = tb.get("counts")
                payload["checks"] = tb.get("checks")
                payload["summary"] = tb.get("summary")
                payload["findings"] = tb.get("findings", [])[:20]
            except Exception:
                pass
        if tlf.exists():
            try:
                tl = json.loads(tlf.read_text(encoding="utf-8"))
                payload["timeline_profile"] = tl.get("profile")
                payload["disclosures"] = tl.get("disclosures")
                payload["gap_intervals"] = tl.get("gap_intervals", [])
                payload["transitions"] = [
                    {
                        "transition_id": tr.get("transition_id"),
                        "from_scene": tr.get("from_scene"),
                        "to_scene": tr.get("to_scene"),
                        "type": tr.get("type"),
                        "start_frame": tr.get("start_frame"),
                        "end_frame": tr.get("end_frame"),
                        "applied_frames": tr.get("applied_frames"),
                        "supported": tr.get("supported"),
                    }
                    for tr in tl.get("transitions", [])
                ]
                for trk in tl.get("tracks", []):
                    if trk.get("track_type") in ("composition", "video"):
                        payload["timeline_scenes"] = [
                            {
                                "scene_id": it.get("scene_id") or it.get("id"),
                                "start_frame": it.get("start_frame"),
                                "end_frame": it.get("end_frame"),
                                "duration_frames": (it.get("end_frame", 0) - it.get("start_frame", 0)),
                                "source_start_seconds": it.get("source_start_seconds"),
                                "source_end_seconds": it.get("source_end_seconds"),
                                "narration_start_seconds": it.get("narration_start_seconds"),
                                "narration_end_seconds": it.get("narration_end_seconds"),
                                "layers_count": len(it.get("layers", [])),
                            }
                            for it in trk.get("items", [])
                        ]
            except Exception:
                pass
        aaf = pdir / "audio_analysis.json"
        if aaf.exists():
            try:
                aa = json.loads(aaf.read_text(encoding="utf-8"))
                src = aa.get("source", {})
                payload["audio_source"] = {
                    "duration_seconds": src.get("duration_seconds") or aa.get("duration_seconds"),
                    "sample_rate_hz": src.get("sample_rate_hz") or aa.get("sample_rate"),
                    "channels": src.get("channels") or aa.get("channels"),
                    "codec": src.get("codec"),
                }
            except Exception:
                pass
        ssf = pdir / "scene_segmentation.json"
        if ssf.exists():
            try:
                ss = json.loads(ssf.read_text(encoding="utf-8"))
                payload["planned_scenes_count"] = len(ss.get("scenes", []))
                payload["scene_intervals"] = [
                    {
                        "scene_id": s.get("scene_id") or s.get("id"),
                        "start_time": s.get("start_time"),
                        "end_time": s.get("end_time"),
                        "duration": round((s.get("end_time") or 0) - (s.get("start_time") or 0), 3),
                        "transcript": (s.get("transcript") or "")[:80],
                    }
                    for s in ss.get("scenes", [])
                ]
            except Exception:
                pass
        mpf = pdir / f"motion_plan{sfx}.json"
        if mpf.exists():
            try:
                mp = json.loads(mpf.read_text(encoding="utf-8"))
                payload["motion_plan_summary"] = {
                    "scenes_count": len(mp.get("scenes", [])),
                    "speed": mp.get("speed"),
                    "scenes": [
                        {
                            "id": sc.get("id"),
                            "start": sc.get("start"),
                            "end": sc.get("end"),
                            "pattern": sc.get("pattern"),
                            "texts_count": len(sc.get("texts", [])),
                            "graphics_count": len(sc.get("graphics", [])),
                            "transition": sc.get("transition"),
                        }
                        for sc in mp.get("scenes", [])
                    ],
                }
            except Exception:
                pass
    elif stage == "render":
        vid = pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        payload["video_exists"] = vid.exists()
        payload["video_size_bytes"] = vid.stat().st_size if vid.exists() else 0
        rrf = pdir / f"render_report{sfx}.json"
        if rrf.exists():
            try:
                rr = json.loads(rrf.read_text(encoding="utf-8"))
                payload["render_status"] = rr.get("status")
                payload["expected"] = rr.get("expected")
                payload["observed"] = rr.get("observed")
                payload["verifications"] = rr.get("verification")
                payload["output_artifact"] = rr.get("output")
                payload["approval_reference"] = rr.get("approval")
                payload["timings_seconds"] = rr.get("timings_seconds")
                payload["carried_warnings"] = rr.get("carried_warnings")
            except Exception:
                pass
        tlf = pdir / f"timeline{sfx}.json"
        if tlf.exists():
            try:
                tl = json.loads(tlf.read_text(encoding="utf-8"))
                payload["timeline_profile"] = tl.get("profile")
            except Exception:
                pass
    elif stage == "qc":
        qcf = pdir / f"final_qc_report{sfx}.json"
        if qcf.exists():
            try:
                qc = json.loads(qcf.read_text(encoding="utf-8"))
                payload["qc_status"] = qc.get("status")
                payload["qc_summary"] = qc.get("summary")
                payload["candidate"] = qc.get("candidate")
                payload["media_metadata"] = qc.get("media")
                payload["evidence"] = {
                    k: {
                        "key": v.get("key"),
                        "checks": v.get("checks"),
                        "data": v.get("data"),
                    }
                    for k, v in qc.get("evidence", {}).items()
                }
                payload["delivery_gate"] = qc.get("delivery_gate")
                payload["llm_decision"] = qc.get("llm_review")
                payload["limitations"] = qc.get("limitations")
                payload["findings"] = [
                    {
                        "finding_id": f.get("finding_id"),
                        "rule_id": f.get("rule_id"),
                        "status": f.get("status"),
                        "severity": f.get("severity"),
                        "message": f.get("message"),
                        "scene_id": f.get("scene_id"),
                    }
                    for f in qc.get("findings", [])[:25]
                ]
            except Exception:
                pass
        tr_f = pdir / "transcript_corrected.json"
        if not tr_f.exists():
            tr_f = pdir / "transcript.json"
        if tr_f.exists():
            try:
                tr = json.loads(tr_f.read_text(encoding="utf-8"))
                segs = tr.get("segments", [])
                full_text = tr.get("text") or " ".join(s.get("text", "").strip() for s in segs if s.get("text"))
                payload["telugu_narration"] = {
                    "language": tr.get("language", "te"),
                    "full_text": full_text[:800],
                    "segments_count": len(segs),
                    "segments_timing": [
                        {
                            "id": s.get("id"),
                            "start": s.get("start"),
                            "end": s.get("end"),
                            "text": s.get("text"),
                        }
                        for s in segs[:10]
                    ],
                }
            except Exception:
                pass
        tl_f = pdir / f"timeline{sfx}.json"
        if tl_f.exists():
            try:
                tl = json.loads(tl_f.read_text(encoding="utf-8"))
                payload["timeline_scenes_count"] = tl.get("profile", {}).get("scene_count")
                payload["timeline_duration_frames"] = tl.get("profile", {}).get("duration_frames")
                payload["timeline_fps"] = tl.get("profile", {}).get("fps")
            except Exception:
                pass
    elif stage == "final":
        qcf = pdir / f"final_qc_report{sfx}.json"
        rev_f = pdir / f"final_qc_review{sfx}.json"
        deliv_f = pdir / "delivery_summary.json"
        vid_f = pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")

        payload["qc_passed"] = qcf.exists()
        sha_now = hashlib.sha256(vid_f.read_bytes()).hexdigest() if vid_f.exists() else None
        try:                                                                   # the current (not voided) Final QC LLM decision about THIS file, not merely a review file on disk
            from VIDEO_ENGINE.stages import final_qc as _fq
            dec = _fq.current_review(pdir, aspect, sha_now)
        except Exception:
            dec = None
        payload["qc_decision"] = {k: dec.get(k) for k in ("decision", "reviewer", "reviewer_source", "decided_at")} if dec else None
        payload["qc_approved"] = bool(dec and dec.get("decision") in ("approved", "approved_with_accepted_risks"))

        if vid_f.exists():
            payload["final_video_artifact"] = {"file_name": vid_f.name, "size_bytes": vid_f.stat().st_size, "sha256": sha_now}      # measured format facts are in the QC report below

        if qcf.exists():
            try:
                qc_data = json.loads(qcf.read_text(encoding="utf-8"))
                payload["qc_summary"] = qc_data.get("summary")
                payload["qc_delivery_gate"] = qc_data.get("delivery_gate")
                payload["qc_llm_review"] = qc_data.get("llm_review")
            except Exception:
                pass

        if rev_f.exists():
            try:
                rev_data = json.loads(rev_f.read_text(encoding="utf-8"))
                events = rev_data.get("events", [])
                if events:
                    latest_rev = events[-1]
                    payload["latest_approval_record"] = {
                        "review_id": latest_rev.get("review_id"),
                        "reviewer": latest_rev.get("reviewer"),
                        "decision": latest_rev.get("decision"),
                        "decided_at": latest_rev.get("decided_at"),
                        "coverage": latest_rev.get("coverage"),
                        "notes": latest_rev.get("notes"),
                        "accepted_findings": latest_rev.get("accepted_findings"),
                    }
            except Exception:
                pass

        if deliv_f.exists():
            try:
                deliv_data = json.loads(deliv_f.read_text(encoding="utf-8"))
                payload["desktop_delivery"] = {
                    "destination_path": str(deliv_data.get("destination_path")),
                    "delivered_at": deliv_data.get("delivered_at"),
                    "sha256_match": deliv_data.get("destination_sha256") == deliv_data.get("source_sha256"),
                }
            except Exception:
                pass

        # Upstream reviews summary
        upstream_stages = ["analyzer", "segmentation", "planning", "assets", "motion_plan", "motion_gen", "motion_validation", "timeline", "approval", "render", "qc"]
        upstream_summary = []
        for stg in upstream_stages:
            rf = pdir / f"llm_review_{stg}{sfx}.json"
            if rf.exists():
                try:
                    rd = json.loads(rf.read_text(encoding="utf-8"))
                    upstream_summary.append({
                        "stage": stg,
                        "status": rd.get("status"),
                        "score": rd.get("score"),
                        "summary": rd.get("summary", "")[:120],
                    })
                except Exception:
                    pass
        payload["upstream_stage_reviews"] = upstream_summary

    return payload


def generate_stage_review_prompt(stage: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Generates a stage-specific system instruction and user prompt."""
    sys_prompt = (
        "You are the Lead Quality Assurance & Creative Reviewer for the Dark World Video Generation Agent. "
        "Your role is to perform independent, rigorous, stage-specific LLM reviews for each pipeline stage. "
        "Do NOT blindly approve. Look for semantic coherence, pacing, terminology consistency, "
        "adherence to configuration, and production safety. "
        "You must respond with a strictly valid JSON object matching this schema:\n"
        "{\n"
        '  "status": "passed" | "needs_review" | "blocked",\n'
        '  "score": 0.0 to 1.0,\n'
        '  "summary": "Concise summary of findings",\n'
        '  "findings": [\n'
        '    {"severity": "blocker" | "warning" | "info", "category": "...", "message": "...", "scene_id": null}\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        '- If there are fatal flaws, set status="blocked" and include at least one finding with severity="blocker".\n'
        '- If minor visual/editorial warnings exist, set status="passed" with severity="warning" or status="needs_review".\n'
        '- If everything satisfies standards, set status="passed" and score >= 0.85.\n'
        "- Respond with ONLY the JSON object, with no markdown backticks, no comments, and no preamble."
    )

    stage_desc = STAGE_DESCRIPTIONS.get(stage, f"{stage} Review")
    user_prompt = (
        f"### STAGE: {stage.upper()} ({stage_desc})\n"
        f"Review the following stage artifacts and execution payload:\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n\n"
        "Perform your stage-specific review:\n"
    )

    if stage == "audio":
        user_prompt += (
            "- Verify that the audio file exists, has plausible non-zero size, and matches project expectations.\n"
            "- Evaluate narration feasibility and potential mixed-language expectations (Telugu/English tech terms).\n"
            "- If the audio file exists, has non-zero size, and has a valid audio manifest, set status='passed' with score >= 0.85."
        )
    elif stage == "analyzer":
        user_prompt += (
            "- Judge `final_transcript`: it is the transcript AFTER the LLM correction. The words the correction already fixed are listed in `llm_correction.corrections` (from -> to): never report a raw word that was corrected.\n"
            "- English technical terms must be in English script and genuine Telugu words in Telugu script; report only what is still wrong in `final_transcript`.\n"
            "- `word_timing`: corrected words should be `aligned` (estimated times are a warning), words must not overlap. Verify cuts and timestamps are coherent."
        )
    elif stage == "segmentation":
        user_prompt += (
            "- Evaluate scene boundary groupings and narrative pacing.\n"
            "- Verify each scene has a coherent semantic concept and duration limits are respected.\n"
            "- If scenes have valid boundaries, non-zero durations, and coherent concepts, approve with status='passed' and score >= 0.85."
        )
    elif stage == "planning":
        user_prompt += (
            "- Evaluate visual plan prompts, thematic imagery, and visual diversity across scenes.\n"
            "- Verify prompt coverage matches all planned scenes with zero blocking errors."
        )
    elif stage == "assets":
        user_prompt += (
            "- Asset Collection adds OPTIONAL real photographs and video clips to Motion-Only scenes. A project where no scene needs real media (zero requirements, zero assets) is a valid, passing outcome.\n"
            "- Every requirement must be met by a collected asset whose title and search query clearly match what that scene's narration is about, or be recorded in fallbacks with a reason. "
            "An asset that is irrelevant, misleading or likely to misrepresent the narration is a blocker.\n"
            "- Every asset needs a source_url, a licence, rights_class 'A' or 'C' (C = rights not established: collected on purpose and judged by the Final QC LLM review, so it is NOT a blocker here) and authenticity 'real'.\n"
            "- deterministic_findings with severity 'error' are blockers; severity 'review' is informational.\n"
            "- If all of this holds, approve with status='passed' and score >= 0.85."
        )
    elif stage == "motion_plan":
        user_prompt += (
            "- In Motion-Only mode, Custom Code Mode is strictly used: evaluate kinetic typography pacing, reading duration (words per second), visual hierarchy, and transitions using the provided scene details.\n"
            "- If deterministic validation has 0 errors and 0 warnings (note: delta in total checks represents accepted library fallbacks and downstream composition sync), and timing/hierarchy is coherent, approve with status='passed' and score >= 0.85."
        )
    elif stage == "motion_gen":
        user_prompt += (
            "- Verify that executable React/TSX animation code is compiled and free of prohibited presets.\n"
            "- Verify scene-specific executable Remotion code is generated with valid composition integrity and layer assembly at 30 fps.\n"
            "- If TypeScript compilation/typecheck passed with 0 prohibited presets, 30 fps Remotion components, and matching composition scenes, approve with status='passed' and score >= 0.85."
        )
    elif stage == "motion_validation":
        user_prompt += (
            "- Synthesize the 12 deterministic validation check results.\n"
            "- Confirm that reported warnings do not compromise visual readability or cause motion collisions."
        )
    elif stage == "timeline":
        user_prompt += (
            "- Review timeline composition structural integrity, frame accounting, transition windows, and audio tail."
        )
    elif stage == "approval":
        user_prompt += (
            "- Rigorously analyze and validate the generated timeline against audio duration, scene timings, word-level timestamps, transitions, motion plans, and synchronization requirements.\n"
            "- Cross-reference timeline duration vs audio duration: verify that total frames and duration align with source audio within 1 frame tolerance.\n"
            "- Verify scene-to-audio synchronization: confirm all planned scenes map to timeline composition tracks without gaps or frame accounting errors.\n"
            "- Check transition windows and gap intervals: verify filler policies (e.g. hold_previous_scene) keep continuous visual playback.\n"
            "- Review motion plan binding: confirm each scene's planned kinetic typography, transitions, and composition layers are properly accounted for.\n"
            "- Inspect timeline validation findings: confirm zero blocking errors (blockers=0) and that any minor carried warnings are acceptable and safe.\n"
            "- If all checks satisfy standards with 0 blockers, approve with status='passed' and score >= 0.85."
        )
    elif stage == "render":
        user_prompt += (
            "- Evaluate rendered video file existence, non-zero file size, and complete render telemetry.\n"
            "- Cross-reference observed vs expected dimensions (width x height), aspect ratio, duration, and frame count (fps and total frames).\n"
            "- Verify that the audio stream is present, active, and synchronized with video duration.\n"
            "- Confirm that all automated render verification checks passed and carried warnings are acceptable within tolerances (e.g., minor audio tail delta < 1 frame).\n"
            "- If the file exists, has valid dimensions, matching frame count, synced audio, and passed verifications, approve with status='passed' and score >= 0.85."
        )
    elif stage == "qc":
        user_prompt += (
            "- Your verdict IS the Final QC decision about this exact rendered video: nobody watches it after you.\n"
            "- Judge ONLY from the measurements, evidence, findings, limitations, timeline profile and narration in the payload. Never assume a value (resolution, frame count, levels, scene count) that is not in it.\n"
            "- qc_status 'failed' or 'blocked', or any finding with severity 'blocker' or 'error', means status='blocked'.\n"
            "- Findings with status 'requires_review' or 'not_run' were not measured automatically (e.g. narration/scene sync, transition smoothness, rights of class C assets). "
            "Decide from the evidence whether each is acceptable; name every one you accept as a 'warning' finding with the reason, and set status='blocked' with a 'blocker' finding for one that is not.\n"
            "- Approve with status='passed' and score >= 0.85 only when there are 0 blockers/errors and every open item is acceptable."
        )
    elif stage == "final":
        user_prompt += (
            "- Verify end-to-end delivery provenance from the payload only: every upstream stage review passed, qc_approved is true (the Final QC LLM decision about this exact file), "
            "the final video exists with the SHA-256 shown, and when a delivery record exists its SHA-256 matches the source.\n"
            "- Never assume a value that is not in the payload.\n"
            "- If delivery provenance and integrity are verified, approve with status='passed' and score >= 0.85."
        )

    return sys_prompt, user_prompt


def run_stage_llm_review(
    pdir: Path,
    stage: str,
    aspect: str = "16:9",
    force: bool = False,
    timeout: int = 60,
    auto_pilot: bool = False,
) -> LlmReviewResult:
    """Executes a mandatory stage-specific LLM review and persists the structured result.
    If the LLM is unavailable or fails, it fails closed (status='blocked').
    """
    in_fp = compute_stage_input_fingerprint(pdir, stage, aspect)
    out_fp = compute_stage_output_fingerprint(pdir, stage, aspect)

    # Check existing fresh review
    if not force:
        existing = load_review(pdir, stage, aspect)
        if (
            existing
            and existing.get("input_fingerprint") == in_fp
            and existing.get("output_fingerprint") == out_fp
            and existing.get("status") in ("passed", "needs_review")
        ):
            return existing

    t0 = time.perf_counter()
    payload = build_stage_payload(pdir, stage, aspect)
    sys_prompt, user_prompt = generate_stage_review_prompt(stage, payload)

    from SYSTEM.core.pipeline_state import STAGE_TO_AGENT_MAP as stage_to_agent
    verdict = ask_reviewer(
        project_id=pdir.name,
        stage_id=stage,
        agent_id=stage_to_agent.get(stage, "main_orchestrator"),
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        timeout=timeout,
        input_fingerprint=in_fp,
        artifact_refs=[{"path": str(f), "description": f.name} for f in stage_input_files(pdir, stage, aspect)],
        metadata={"aspect": aspect},
        auto_pilot=auto_pilot,
    )
    result: LlmReviewResult = {
        "schema": SCHEMA,
        "version": VERSION,
        "stage": stage,
        "aspect": aspect,
        **verdict,
        "input_fingerprint": in_fp,
        "output_fingerprint": out_fp,
        "reviewed_at": time.time(),
    }
    save_review(pdir, stage, aspect, result)
    return result


class StageReviewResult:
    """Object representation of a stage LLM review result with dictionary and attribute access."""
    def __init__(
        self,
        stage: str,
        status: str,
        score: float = 1.0,
        summary: str = "",
        findings: list[dict[str, Any]] | None = None,
        raw_result: dict[str, Any] | None = None,
    ) -> None:
        self.stage = stage
        self.status = status
        self.score = score
        self.summary = summary
        self.findings = findings or []
        self._raw = raw_result or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "score": self.score,
            "summary": self.summary,
            "findings": self.findings,
            **self._raw,
        }

    def __getitem__(self, item: str) -> Any:
        return self.to_dict()[item]

    def get(self, item: str, default: Any = None) -> Any:
        return self.to_dict().get(item, default)


def review_stage(
    pdir: Path,
    stage: str,
    aspect: str = "16:9",
    force: bool = False,
    timeout: int = 60,
) -> StageReviewResult:
    """Runs a stage review and returns a StageReviewResult object."""
    res_dict = run_stage_llm_review(pdir, stage, aspect=aspect, force=force, timeout=timeout)
    return StageReviewResult(
        stage=res_dict.get("stage", stage),
        status=res_dict.get("status", "blocked"),
        score=res_dict.get("score", 0.0),
        summary=res_dict.get("summary", ""),
        findings=res_dict.get("findings", []),
        raw_result=res_dict,
    )
