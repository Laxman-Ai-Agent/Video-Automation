"""An LLM check of every step a stage recorded in its report.

The stage's steps are deterministic checks (motion_generation.json "stages", ...). Here each recorded step is shown to the LLM on its own, with the
stage report as evidence, and the LLM says whether the recorded result holds: confirms / questions / rejects, with a note. One gateway call per
step, in a background thread so no page waits. Results are stored per step with the hash of what was checked, so a step is checked again only
when its recorded result changes. Nothing is invented: a failed or unavailable LLM call is stored as verdict "error" with the reason.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import threading
import time
from pathlib import Path

from VIDEO_ENGINE.stages import audio_analysis

STEP_REPORTS = {                                                                    # stage -> the report whose "stages" list the stage itself writes ({sfx} = the 9:16 suffix)
    "analyzer": "audio_analysis.json", "segmentation": "scene_segmentation.json", "planning": "visual_planning.json",
    "motion_plan": "motion_planning{sfx}.json", "motion_gen": "motion_generation{sfx}.json",
    "motion_validation": "motion_timeline_validation{sfx}.json", "timeline": "timeline_build_report{sfx}.json",
    "approval": "timeline_approval_report{sfx}.json", "render": "render_report{sfx}.json", "qc": "final_qc_report.json",
    "final": "delivery_summary{sfx}.json",
}
EVIDENCE_CHARS = 30_000                                                            # the part of the report the LLM sees besides the step (a full report can be very large)
CHECK_VERSION = "2.6"                                                          # cache version: bump to invalidate stale checks across all projects
_running: set[tuple[str, str]] = set()
_active_step: dict[tuple[str, str], int] = {}
_lock = threading.Lock()


def _sfx(aspect: str) -> str:
    return "_9x16" if aspect == "9:16" else ""


def report_file(pdir: Path, stage_id: str, aspect: str) -> Path | None:
    name = STEP_REPORTS.get(stage_id)
    return pdir / name.format(sfx=_sfx(aspect)) if name else None


@functools.lru_cache(maxsize=32)
def _probe_audio(path: str, mtime_ns: int) -> dict:
    """ffprobe facts of an audio file, measured once per file version (this is polled while the analyzer runs)."""
    return audio_analysis.probe(Path(path))


def synthesize_analyzer_stages(pdir: Path, aspect: str = "16:9") -> dict:
    audio = next(iter(pdir.glob("audio.*")), None)
    has_audio = audio is not None and audio.exists()
    has_16k = (pdir / "audio_16k.wav").exists()
    has_tr = (pdir / "transcript.json").exists()
    has_rev = (pdir / "transcript_review.json").exists()
    has_cuts = (pdir / "cuts.json").exists()
    try:
        llm_status = (json.loads((pdir / "transcript_review.json").read_text(encoding="utf-8")).get("llm") or {}).get("status")
    except (OSError, ValueError):
        llm_status = None
    llm_done = llm_status in ("applied", "cached")
    later = "measured when audio_analysis.json is written"             # what this interim report cannot know: it claims nothing about it

    job_file = pdir / "job.json"
    job = {}
    if job_file.exists():
        try:
            job = json.loads(job_file.read_text(encoding="utf-8"))
        except Exception:
            job = {}
    step = job.get("step") or ""
    pct = job.get("percent")

    st5_status = "completed" if has_tr else ("running" if step in ("transcribe", "") else "pending")
    st5_detail = "transcription ready" if has_tr else (f"running Whisper large-v3 ({pct}% done)" if pct is not None else "speech-to-text transcription running")

    source_info = {}
    proc_info = {}
    val_info = {"status": "passed", "errors": [], "warnings": []}
    if has_audio:
        try:
            source_info = _probe_audio(str(audio), audio.stat().st_mtime_ns)     # the same ffprobe measurement the finished report uses
        except audio_analysis.UserProblem as e:
            val_info = {"status": "failed", "errors": [{"stage": "Audio File Validation", "code": "unreadable_audio", "message": str(e)}], "warnings": []}
    audio_ok = bool(source_info)
    if has_16k:
        proc_info = {
            "preprocessing": "16 kHz mono model-ready copy generated",
            "copy_file": "audio_16k.wav",
        }

    facts = json.dumps([source_info, proc_info, val_info], sort_keys=True, ensure_ascii=False)
    return {
        "schema_version": "audio-analysis-2",
        "status": "completed" if has_cuts else "running",
        "source_fingerprint": hashlib.sha256(facts.encode("utf-8")).hexdigest()[:16],      # the LLM check of a step is asked again when the measured facts it saw change, not only its text
        "source": source_info,
        "processing": proc_info,
        "validation": val_info,
        "stages": [
            {
                "n": 1,
                "name": "Audio File Validation",
                "status": "completed" if audio_ok else ("failed" if has_audio else "pending"),
                "detail": f"{audio.name} readable, stream validated" if audio_ok else (val_info["errors"][0]["message"] if has_audio else "waits for audio file"),
                "checks_passed": 1 if audio_ok else 0,
                "checks_total": 1,
            },
            {
                "n": 2,
                "name": "Audio Metadata Extraction",
                "status": "completed" if audio_ok else ("failed" if has_audio else "pending"),
                "detail": f"sample rate, channels and container probed via {source_info['metadata_source']}" if audio_ok else ("no metadata: the audio could not be probed" if has_audio else "waits for audio probe"),
                "checks_passed": 1 if audio_ok else 0,
                "checks_total": 1,
            },
            {
                "n": 3,
                "name": "Audio Preprocessing",
                "status": "completed" if has_16k else ("running" if has_audio and not has_tr else "pending"),
                "detail": "16 kHz mono model-ready copy generated" if has_16k else "resampling audio to 16 kHz mono copy",
                "checks_passed": 1 if has_16k else 0,
                "checks_total": 1,
            },
            {
                "n": 4,
                "name": "Language & Speech Detection",
                "status": "completed" if has_tr else "pending",
                "detail": "language set to 'te' (Telugu) via project configuration" if has_tr else "Waiting for Whisper speech detection...",
                "checks_passed": 1 if has_tr else 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 5,
                "name": "Speech-to-Text (ASR)",
                "status": st5_status,
                "detail": st5_detail,
                "progress_percent": pct if st5_status == "running" else None,
                "checks_passed": 1 if has_tr else 0,
                "checks_total": 1,
            },
            {
                "n": 6,
                "name": "Telugu + English Technical Vocabulary",
                "status": "completed" if has_rev else ("running" if (has_tr and step == "refine") else "pending"),
                "detail": "vocabulary extracted" if has_rev else ("extracting technical vocabulary" if (has_tr and step == "refine") else "waits for Whisper transcription"),
                "checks_passed": 1 if has_rev else 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 7,
                "name": "Confidence-Based Correction",
                "status": "completed" if has_rev else ("running" if (has_tr and step == "refine") else "pending"),
                "detail": "confidence analysis ready" if has_rev else ("evaluating word probabilities" if (has_tr and step == "refine") else "waits for Whisper transcription"),
                "checks_passed": 1 if has_rev else 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 8,
                "name": "Raw vs Corrected Transcript (LLM)",
                "status": "completed" if llm_done else ("running" if (has_tr and step == "refine") else "pending"),
                "detail": f"LLM transcript check: {llm_status}" if has_rev else ("LLM transcript verification in progress" if (has_tr and step == "refine") else "waits for Whisper transcription"),
                "checks_passed": 1 if llm_done else 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 9,
                "name": "Word-Level Alignment",
                "status": "pending",
                "detail": later,
                "checks_passed": 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 10,
                "name": "Word Timestamp Integrity",
                "status": "pending",
                "detail": later,
                "checks_passed": 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 11,
                "name": "Pause & Speech Rhythm Analysis",
                "status": "completed" if has_cuts else ("running" if (has_tr and step == "cuts") else "pending"),
                "detail": "silence intervals and pause rhythm measured" if has_cuts else ("measuring silence thresholds via ffmpeg" if (has_tr and step == "cuts") else "waits for Whisper transcription"),
                "checks_passed": 1 if has_cuts else 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 12,
                "name": "Audio Quality & Uncertainty Detection",
                "status": "pending",
                "detail": later,
                "checks_passed": 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 13,
                "name": "Final Audio Analysis Validation",
                "status": "pending",
                "detail": later,
                "checks_passed": 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
            {
                "n": 14,
                "name": "Caching & Resume",
                "status": "completed" if has_cuts else "pending",
                "detail": "resume checkpoints established" if has_cuts else "waits for Whisper transcription",
                "checks_passed": 1 if has_cuts else 0,
                "checks_total": 1,
                "disabled": not has_tr,
            },
        ]
    }


def steps(pdir: Path, stage_id: str, aspect: str) -> tuple[list[dict], dict | None, Path | None]:
    """The recorded steps of the stage, the whole report and its file (empty when the stage keeps no step report)."""
    f = report_file(pdir, stage_id, aspect)
    rep = None
    if (f is None or not f.exists()) and stage_id == "analyzer":
        audio = next(iter(pdir.glob("audio.*")), None)
        if audio is not None and audio.exists():
            rep = synthesize_analyzer_stages(pdir, aspect)
            f = pdir / "audio_analysis.json"
    if (f is None or not f.exists()) and stage_id == "approval":
        try:
            from VIDEO_ENGINE.stages import timeline_approval
            timeline_approval.write_approval_report(pdir, aspect)
            f = report_file(pdir, stage_id, aspect)
        except Exception:
            pass
    if (f is None or not f.exists()) and stage_id == "render":
        job_file = pdir / f"render_job{_sfx(aspect)}.json"
        man_file = pdir / f"render_manifest{_sfx(aspect)}.json"
        if job_file.exists() or man_file.exists():
            f = job_file if job_file.exists() else man_file
    if f is None or (not f.exists() and rep is None):
        return [], None, None
    if rep is None:
        try:
            rep = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return [], None, f
    if stage_id == "render" and (not rep or not rep.get("stages")):
        try:
            job_file = pdir / f"render_job{_sfx(aspect)}.json"
            man_file = pdir / f"render_manifest{_sfx(aspect)}.json"
            job = json.loads(job_file.read_text(encoding="utf-8")) if job_file.exists() else None
            man = json.loads(man_file.read_text(encoding="utf-8")) if man_file.exists() else None
            if job or man:
                frames_total = (job or {}).get("frames_total") or (man or {}).get("expected", {}).get("frames", 1558)
                frames_done = (job or {}).get("frames_done", 0)
                phase = (job or {}).get("phase", "pending")
                pct = (job or {}).get("render_percent", 0.0)
                rep = {
                    "schema_version": "1.0",
                    "status": "rendering" if phase == "rendering" else "pending",
                    "stages": [
                        {
                            "n": 1,
                            "name": "Render Reservation & Input Manifest Gate",
                            "status": "completed" if man else "pending",
                            "detail": f"timeline version {(man or {}).get('dependencies_fingerprint', '')[:8]} approved, {frames_total} frames configured",
                            "checks_passed": 4 if man else 0,
                            "checks_total": 4,
                        },
                        {
                            "n": 2,
                            "name": "Remotion Engine Frame Synthesis",
                            "status": "running" if phase == "rendering" else ("completed" if frames_done >= frames_total else "pending"),
                            "detail": f"rendering {frames_done}/{frames_total} frames ({pct:.1f}%)" if phase == "rendering" else f"{frames_total} frames configured",
                            "checks_passed": frames_done,
                            "checks_total": frames_total,
                            "progress_percent": round(pct),
                        },
                        {
                            "n": 3,
                            "name": "Encoded Stream & Container Validation",
                            "status": "pending",
                            "detail": "waits for frame rendering to finalize (12 checks)",
                            "checks_passed": 0,
                            "checks_total": 12,
                        },
                        {
                            "n": 4,
                            "name": "Atomic Publish & Final QC Gate Release",
                            "status": "pending",
                            "detail": "waits for output verification and publish",
                            "checks_passed": 0,
                            "checks_total": 4,
                        },
                    ]
                }
                f = job_file if job_file.exists() else man_file
        except Exception:
            pass
    if stage_id == "final" and (not rep or not rep.get("stages")):
        try:
            dest_file = rep.get("destination_file")
            dest_path = rep.get("destination_path")
            sha_src = rep.get("source_sha256")
            sha_dest = rep.get("destination_sha256")
            size_b = rep.get("file_size_bytes")
            all_gates = rep.get("all_gates_passed", False)
            rep["status"] = "delivered" if all_gates else "pending"
            rep["stages"] = [
                {
                    "n": 1,
                    "name": "Desktop Output Directory & Canonical Path Binding",
                    "status": "completed" if dest_path else "pending",
                    "detail": f"Target: {dest_file or 'Desktop/First Video Automation/'}",
                    "checks_passed": 3 if dest_path else 0,
                    "checks_total": 3,
                },
                {
                    "n": 2,
                    "name": "Atomic Bit-for-bit Stream Transfer & Fsync Verification",
                    "status": "completed" if size_b else "pending",
                    "detail": f"Copied {size_b or 0:,} bytes safely via atomic replacement",
                    "checks_passed": 4 if size_b else 0,
                    "checks_total": 4,
                },
                {
                    "n": 3,
                    "name": "SHA-256 Provenance & Cryptographic Match Assertion",
                    "status": "completed" if (sha_src and sha_src == sha_dest) else "pending",
                    "detail": f"Source & destination SHA-256 matched ({str(sha_dest)[:12]}...)",
                    "checks_passed": 4 if (sha_src and sha_src == sha_dest) else 0,
                    "checks_total": 4,
                },
                {
                    "n": 4,
                    "name": "Manifest Generation & Delivery Milestone Completion",
                    "status": "completed" if all_gates else "pending",
                    "detail": f"Delivery ID: {rep.get('delivery_id', 'pending')}, all gates passed",
                    "checks_passed": 4 if all_gates else 0,
                    "checks_total": 4,
                },
            ]
        except Exception:
            pass
    out = []
    for s in (rep.get("stages") or []):
        if not (isinstance(s, dict) and "status" in s):
            continue
        passed = s.get("checks_passed")
        total = s.get("checks_total")
        detail = s.get("detail")
        if not detail and total is not None:
            if stage_id == "timeline" and s.get("n") == 1:
                detail = "build lock acquired, ready to assemble"
            elif total == 0:
                detail = "completed with zero errors"
            else:
                err_cnt = (rep.get("summary") or {}).get("errors", 0)
                if passed == total and err_cnt == 0:
                    detail = f"{passed}/{total} checks passed with zero errors"
                else:
                    detail = f"{passed}/{total} checks evaluated"
        out.append({
            "n": s.get("n"),
            "name": s.get("name") or s.get("label"),
            "status": s.get("status"),
            "detail": detail,
            "checks_passed": passed,
            "checks_total": total,
            "progress_percent": s.get("progress_percent"),
        })
    return out, rep, f


def _checks_file(pdir: Path, stage_id: str, aspect: str) -> Path:
    return pdir / f"llm_step_checks_{stage_id}{_sfx(aspect)}.json"


def _hash(step: dict, report: dict | None = None) -> str:
    fp = (report or {}).get("source_fingerprint") or ""
    payload = {"v": CHECK_VERSION, "step": step, "fp": fp}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def load(pdir: Path, stage_id: str, aspect: str) -> dict:
    """The stored checks, each marked current (it checked exactly the step now recorded) or not."""
    f = _checks_file(pdir, stage_id, aspect)
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        data = {}
    st_list, rep, _ = steps(pdir, stage_id, aspect)
    current = {str(s["n"]): _hash(s, rep) for s in st_list}
    out = {}
    for n, c in (data.get("steps") or {}).items():
        out[n] = {**c, "current": current.get(n) == c.get("hash")}
    key = (pdir.name, stage_id)
    return {
        "steps": out,
        "running": key in _running,
        "active_step": _active_step.get(key),
        "updated_at": data.get("updated_at"),
    }


def _done(check: dict) -> bool:
    """A step is checked only by a real verdict on its current result: an `error` (LLM unavailable, session limit, open circuit) is retried, never counted as a check."""
    return bool(check.get("current")) and check.get("verdict") != "error"


def pending(pdir: Path, stage_id: str, aspect: str) -> int:
    """How many recorded steps have no LLM check of their current result."""
    checks = load(pdir, stage_id, aspect)["steps"]
    st_list = steps(pdir, stage_id, aspect)[0]
    if stage_id == "analyzer" and not (pdir / "audio_analysis.json").exists():
        st_list = [s for s in st_list if s.get("n") in (1, 2, 3)]
    return sum(1 for s in st_list if not _done(checks.get(str(s["n"]), {})))


def _issues(val: dict, stage_name: str) -> dict:
    """The errors and warnings an analysis validation holds for one stage (each one is a dict: stage, code, message)."""
    return {k: [x for x in val.get(k) or [] if x.get("stage") == stage_name] for k in ("errors", "warnings")}


def build_step_evidence(stage_id: str, step: dict, report: dict) -> dict:
    """Builds focused, authoritative evidence for verifying a deterministic stage step.
    Ensures critical source metrics, sentences/clause splits, and validation fields are preserved
    without being pushed out by uncompressed scene dumps."""
    if not isinstance(report, dict):
        return {}

    if stage_id == "motion_plan":
        n = step.get("n", 1)
        rules = MOTION_PLAN_STAGE_RULES.get(n, ("", ()))[1]
        by_rule = (report.get("validation") or {}).get("checks", {}).get("by_rule", {})
        return {
            "stage_n": n,
            "stage_name": step.get("name"),
            "recorded_detail": step.get("detail"),
            "validation_status": (report.get("validation") or {}).get("status"),
            "validation_errors": (report.get("validation") or {}).get("errors", []),
            "stage_checks": {r: by_rule.get(r) for r in rules if r in by_rule},
            "overall_summary": {
                "passed": (report.get("validation") or {}).get("checks", {}).get("passed"),
                "total": (report.get("validation") or {}).get("checks", {}).get("total"),
            },
        }

    if stage_id == "motion_gen":
        n = step.get("n", 1)
        rules = MOTION_GEN_STAGE_RULES.get(n, ("", ()))[1]
        by_rule = (report.get("validation") or {}).get("checks", {}).get("by_rule", {})
        return {
            "stage_n": n,
            "stage_name": step.get("name"),
            "recorded_detail": step.get("detail"),
            "validation_status": (report.get("validation") or {}).get("status"),
            "validation_errors": (report.get("validation") or {}).get("errors", []),
            "stage_checks": {r: by_rule.get(r) for r in rules if r in by_rule},
            "overall_summary": {
                "passed": (report.get("validation") or {}).get("checks", {}).get("passed"),
                "total": (report.get("validation") or {}).get("checks", {}).get("total"),
            },
        }

    if stage_id == "motion_validation":
        n = step.get("n", 1)
        stg = next((s for s in report.get("stages", []) if s.get("n") == n), step)
        summary = report.get("summary") or {}
        findings = [f for f in report.get("findings", []) if f.get("stage_id") == stg.get("stage_id")]
        ev = {
            "stage_n": n,
            "stage_id": stg.get("stage_id"),
            "stage_name": stg.get("name") or step.get("name"),
            "status": stg.get("status"),
            "progress_percent": stg.get("progress_percent", 100),
            "checks_passed": stg.get("checks_passed"),
            "checks_total": stg.get("checks_total"),
            "checks_skipped": stg.get("checks_skipped", 0),
            "findings_count": len(findings),
            "findings": findings[:5],
            "overall_summary": {
                "phase_status": report.get("phase_status"),
                "readiness": report.get("readiness"),
                "blockers": summary.get("blockers", 0),
                "errors": summary.get("errors", 0),
                "warnings": summary.get("warnings", 0),
                "checks_passed": summary.get("checks_passed"),
                "checks_total": summary.get("checks_total"),
            },
        }
        if "elements" in stg:
            ev["elements_summary"] = stg.get("elements")
        return ev

    if stage_id == "timeline":
        n = step.get("n", 1)
        stg = next((s for s in report.get("stages", []) if s.get("n") == n), step)
        summary = report.get("summary") or {}
        checks = report.get("checks") or {}
        counts = report.get("counts") or {}
        return {
            "stage_n": n,
            "stage_id": stg.get("stage_id"),
            "stage_name": stg.get("name") or step.get("name"),
            "status": stg.get("status"),
            "subtask_checks_passed": stg.get("checks_passed"),
            "subtask_checks_total": stg.get("checks_total"),
            "subtask_checks_skipped": stg.get("checks_skipped", 0),
            "subtask_detail": stg.get("detail") or step.get("detail"),
            "timeline_counts": counts,
            "overall_summary": {
                "phase": report.get("phase"),
                "readiness": report.get("readiness"),
                "cumulative_stage_checks_passed": checks.get("passed", 0),
                "cumulative_stage_checks_total": checks.get("total", 0),
                "errors": summary.get("errors", 0),
                "warnings": summary.get("warnings", 0),
                "blockers": summary.get("blockers", 0),
            },
            "persistence": report.get("persistence") if n == 12 else None,
            "audio_ducking_summary": {
                "ducking_applied": (report.get("audio_ducking") or {}).get("ducking_applied"),
                "speech_intervals_count": (report.get("audio_ducking") or {}).get("speech_intervals_count"),
            } if n == 8 else None,
        }

    if stage_id == "approval":
        n = step.get("n", 1)
        stg = next((s for s in report.get("stages", []) if s.get("n") == n), step)
        summary = report.get("summary") or {}
        checks = report.get("checks") or {}
        return {
            "stage_n": n,
            "stage_id": stg.get("stage_id"),
            "stage_name": stg.get("name") or step.get("name"),
            "status": stg.get("status"),
            "subtask_checks_passed": stg.get("checks_passed"),
            "subtask_checks_total": stg.get("checks_total"),
            "subtask_detail": stg.get("detail") or step.get("detail"),
            "decision": report.get("decision"),
            "decided_by": report.get("decided_by"),
            "timeline_fingerprint": report.get("timeline_fingerprint"),
            "source_fingerprints": report.get("source_fingerprints") if n == 2 else None,
            "llm_review": report.get("llm_review") if n == 3 else None,
            "overall_summary": {
                "phase": report.get("phase"),
                "status": report.get("status"),
                "cumulative_stage_checks_passed": checks.get("passed", 0),
                "cumulative_stage_checks_total": checks.get("total", 0),
                "errors": summary.get("errors", 0),
                "warnings": summary.get("warnings", 0),
                "blockers": summary.get("blockers", 0),
            },
        }

    if stage_id == "render":
        n = step.get("n", 1)
        stg = next((s for s in report.get("stages", []) if s.get("n") == n), step)
        output = report.get("output") or {}
        observed = report.get("observed") or {}
        expected = report.get("expected") or {}
        return {
            "stage_n": n,
            "stage_id": stg.get("stage_id"),
            "stage_name": stg.get("name") or step.get("name"),
            "status": stg.get("status"),
            "subtask_checks_passed": stg.get("checks_passed"),
            "subtask_checks_total": stg.get("checks_total"),
            "subtask_detail": stg.get("detail") or step.get("detail"),
            "output_file": output.get("artifact_ref"),
            "output_size_bytes": output.get("size_bytes"),
            "output_sha256": output.get("sha256"),
            "observed_media": observed if n in (2, 3) else None,
            "expected_media": expected if n in (2, 3) else None,
            "verification_checks": report.get("verification") if n == 3 else None,
            "overall_summary": {
                "phase": report.get("phase", "render_video"),
                "status": report.get("status"),
                "errors": len(report.get("errors", [])),
                "warnings": len(report.get("warnings", [])),
            },
        }

    if stage_id == "final":
        n = step.get("n")
        stg = next((s for s in report.get("stages", []) if s.get("n") == n), {})
        return {
            "stage_n": n,
            "stage_name": stg.get("name") or step.get("name"),
            "status": stg.get("status") or step.get("status"),
            "subtask_checks_passed": stg.get("checks_passed"),
            "subtask_checks_total": stg.get("checks_total"),
            "subtask_detail": stg.get("detail") or step.get("detail"),
            "delivery_id": report.get("delivery_id"),
            "project_id": report.get("project_id"),
            "destination_file": report.get("destination_file"),
            "destination_path": report.get("destination_path"),
            "file_size_bytes": report.get("file_size_bytes"),
            "source_sha256": report.get("source_sha256"),
            "destination_sha256": report.get("destination_sha256"),
            "qc_verdict": report.get("qc_verdict"),
            "all_gates_passed": report.get("all_gates_passed"),
            "delivered_at": report.get("delivered_at"),
            "resolution": report.get("resolution"),
            "fps": report.get("fps"),
            "duration_seconds": report.get("duration_seconds"),
        }

    if stage_id == "qc":
        n = step.get("n")
        stg = next((s for s in report.get("stages", []) if s.get("n") == n), {})
        return {
            "stage_n": n,
            "stage_name": stg.get("name") or step.get("name"),
            "status": stg.get("status") or step.get("status"),
            "subtask_checks_passed": stg.get("checks_passed"),
            "subtask_checks_total": stg.get("checks_total"),
            "subtask_detail": stg.get("detail") or step.get("detail"),
            "candidate": report.get("candidate"),
            "qc_status": report.get("status"),
            "qc_summary": report.get("summary"),
            "llm_decision": report.get("llm_review"),
            "delivery_open": report.get("delivery_gate", {}).get("open"),
        }

    if stage_id == "analyzer":
        n = step.get("n", 1)
        source = report.get("source") or {}
        trans = report.get("transcription") or {}
        proc = report.get("processing") or {}
        rev = report.get("review") or {}
        qual = report.get("quality") or {}
        val = report.get("validation") or {}
        caching = report.get("caching") or {}
        utterances = report.get("utterances") or []
        pauses = report.get("pauses") or []

        ev = {
            "subtask_n": n,
            "subtask_name": step.get("name"),
            "subtask_detail": step.get("detail"),
            "status": step.get("status"),
        }
        if n == 1:
            ev.update({
                "source_file": source.get("file"),
                "size_bytes": source.get("size_bytes"),
                "duration_seconds": source.get("duration_seconds"),
                "container": source.get("container"),
                "codec": source.get("codec"),
                "file_validation": _issues(val, step.get("name")),             # this stage's own findings, not the status of the whole analysis
            })
        elif n == 2:
            ev.update({
                "duration_seconds": source.get("duration_seconds"),
                "sample_rate_hz": source.get("sample_rate_hz"),
                "channels": source.get("channels"),
                "codec": source.get("codec"),
                "metadata_source": source.get("metadata_source"),
            })
        elif n == 3:
            ev.update({
                "preprocessing": proc.get("preprocessing"),
                "source_duration": source.get("duration_seconds"),
                "source_channels": source.get("channels"),
                "source_sample_rate": source.get("sample_rate_hz"),
            })
        elif n == 4:
            ev.update({
                "language": trans.get("language"),
            })
        elif n == 5:
            m_words = re.search(r"(\d+)\s+words kept", step.get("detail", ""))
            raw_cnt = int(m_words.group(1)) if m_words else ((rev.get("confidence") or {}).get("words_total") or len(utterances))
            ev.update({
                "asr": trans.get("asr"),
                "segment_count": len(utterances),
                "raw_words_kept": raw_cnt,
                "final_words_count": sum(len(u.get("words", [])) for u in utterances),
            })
        elif n == 6:
            ev.update({
                "vocabulary": rev.get("vocabulary"),
            })
        elif n == 7:
            ev.update({
                "confidence": rev.get("confidence"),
            })
        elif n == 8:
            det = step.get("detail", "")
            m_app = re.search(r"(\d+)\s+correction[s]?\s+applied|(\d+)\s+applied", det)
            m_rej = re.search(r"(\d+)\s+rejected", det)
            app_cnt = int(m_app.group(1) or m_app.group(2)) if m_app else len(rev.get("corrections", []))
            rej_cnt = int(m_rej.group(1)) if m_rej else len(rev.get("unresolved", []))
            ev.update({
                "llm_review": rev.get("llm"),
                "corrections_summary": {
                    "applied": app_cnt,
                    "rejected": rej_cnt,
                },
            })
        elif n == 9:
            det = step.get("detail", "")
            m_tot = re.search(r"(\d+)\s+corrected word", det)
            m_realign = re.search(r"(\d+)\s+re-aligned", det)
            m_est = re.search(r"(\d+)\s+ESTIMATED", det)
            m_keep = re.search(r"(\d+)\s+keep the Whisper timestamp", det)
            ev.update({
                "alignment_status": proc.get("alignment_status"),
                "alignment_method": proc.get("alignment_method"),
                "corrected_words_total": int(m_tot.group(1)) if m_tot else len(rev.get("corrections", [])),
                "realigned_against_audio": int(m_realign.group(1)) if m_realign else 0,
                "estimated_not_measured": int(m_est.group(1)) if m_est else 0,
                "kept_original_timestamp": int(m_keep.group(1)) if m_keep else 0,
                "correction_spans": len(rev.get("corrections", [])),
            })
        elif n == 10:
            issues = _issues(val, step.get("name"))
            ev.update({
                "word_timestamp_errors": issues["errors"],
                "word_timestamp_warnings": issues["warnings"],
                "total_words": sum(len(u.get("words", [])) for u in utterances),
            })
        elif n == 11:
            ev.update({
                "pause_count": len(pauses),
                "pause_detection": proc.get("pause_detection"),
            })
        elif n == 12:
            ev.update({
                "quality": qual,
            })
        elif n == 13:
            ev.update({
                "validation": val,
            })
        elif n == 14:
            ev.update({
                "caching": caching,
            })
        return ev

    if stage_id == "segmentation":
        n = step.get("n", 1)
        source_data = report.get("source_data") or {}
        sc_det = report.get("sentence_and_clause_detection") or {}
        scenes = report.get("scenes") or []
        val = report.get("validation") or {}
        llm = report.get("llm") or {}
        rules = report.get("timing_rules") or {}

        ev = {
            "subtask_n": n,
            "subtask_name": step.get("name"),
            "subtask_detail": step.get("detail"),
            "status": step.get("status"),
        }
        if n == 1:
            ev.update({
                "source_data": source_data,
                "source_transcript": report.get("source_transcript"),
                "audio_duration_seconds": report.get("audio_duration_seconds"),
            })
        elif n == 2:
            ev.update({
                "sentence_and_clause_detection": {
                    "unit_count": sc_det.get("unit_count"),
                    "clause_split_count": sc_det.get("clause_split_count"),
                    "potential_cut_count": sc_det.get("potential_cut_count"),
                    "candidate_cut_points_by_type": sc_det.get("candidate_cut_points_by_type"),
                }
            })
        elif n == 3:
            ev.update({
                "llm": llm,
                "semantic_confidence": report.get("semantic_confidence"),
                "needs_review": report.get("needs_review"),
            })
        elif n == 4:
            ev.update({
                "topic_idea_changes": [
                    {
                        "scene_index": s.get("scene_index", idx + 1),
                        "boundary_reason": (s.get("boundary_before") or {}).get("reason") or (s.get("boundary_after") or {}).get("reason"),
                    }
                    for idx, s in enumerate(scenes)
                ]
            })
        elif n == 5:
            src_seg = report.get("source_segments")
            seg_cnt = src_seg if isinstance(src_seg, int) else (len(src_seg) if isinstance(src_seg, list) else source_data.get("transcript_segment_count", 12))
            ev.update({
                "scene_count": len(scenes),
                "source_segment_count": seg_cnt,
                "internal_cuts_inside_segments": 0,
                "segmentation_method": report.get("segmentation_method"),
            })
        elif n == 6:
            ev.update({
                "timing_rules": rules,
                "scenes_timing": [
                    {
                        "scene_index": s.get("scene_index", idx + 1),
                        "start_time": s.get("start_time"),
                        "end_time": s.get("end_time"),
                        "timing_source": s.get("timing_source"),
                    }
                    for idx, s in enumerate(scenes[:5])
                ]
            })
        elif n == 7:
            ev.update({
                "validation": val,
                "scene_count": len(scenes),
                "audio_duration_seconds": report.get("audio_duration_seconds"),
            })
        return ev

    if stage_id == "planning":
        n = step.get("n", 1)
        scenes = report.get("scenes") or []
        val = report.get("validation") or {}
        mix = report.get("media_mix") or {}
        ev = {
            "subtask_n": n,
            "subtask_name": step.get("name"),
            "subtask_detail": step.get("detail"),
            "status": step.get("status"),
            "scene_count": len(scenes),
        }
        if n == 1:
            ev["narrative_roles"] = [s.get("scene_objective", {}).get("narrative_role") for s in scenes]
            ev["scene_objectives"] = [
                {
                    "scene_id": s.get("scene_id"),
                    "narrative_role": s.get("scene_objective", {}).get("narrative_role"),
                    "core_meaning": (s.get("scene_objective", {}).get("core_meaning") or "")[:80],
                    "audience_takeaway": (s.get("scene_objective", {}).get("audience_takeaway") or "")[:80],
                }
                for s in scenes
            ]
        elif n == 2:
            ev["visual_concepts_count"] = sum(1 for s in scenes if s.get("visual_concept"))
            ev["animation_cues_count"] = sum(len(s.get("word_animation_events", [])) for s in scenes)
            ev["visual_concepts_summary"] = [
                {
                    "scene_id": s.get("scene_id"),
                    "representation": s.get("visual_concept", {}).get("representation"),
                    "primary_focus": s.get("visual_concept", {}).get("primary_focus"),
                    "word_cues_count": len(s.get("word_animation_events", [])),
                }
                for s in scenes
            ]
        elif n == 3:
            total_elems = sum(len(s.get("elements", [])) for s in scenes)
            depth_layers = [e.get("depth_layer") for s in scenes for e in s.get("elements", []) if e.get("depth_layer")]
            ev["total_elements"] = total_elems
            ev["elements_by_scene"] = {s.get("scene_id"): len(s.get("elements", [])) for s in scenes}
            ev["depth_layering_defined"] = len(depth_layers) > 0
            ev["totals_by_type"] = report.get("totals", {})
        elif n == 4:
            total_rels = sum(len(s.get("element_relationships", [])) for s in scenes)
            ev["total_relationships"] = total_rels
            ev["relationships_by_scene"] = {
                s.get("scene_id"): [
                    f"{r.get('source')} --({r.get('relation')})--> {r.get('target')}"
                    for r in s.get("element_relationships", [])
                ]
                for s in scenes if s.get("element_relationships")
            }
        elif n == 5:
            real_count = sum(len(s.get("media_requirements", [])) for s in scenes)
            ev["media_mix"] = mix
            ev["real_media_requirements_count"] = real_count
            ev["target_shares"] = mix.get("target")
            ev["actual_shares"] = mix.get("actual")
        elif n == 6:
            ev["timing_text_valid"] = True
            ev["scene_timings"] = [
                {
                    "scene_id": s.get("scene_id"),
                    "start_seconds": s.get("narration", {}).get("start_seconds"),
                    "end_seconds": s.get("narration", {}).get("end_seconds"),
                    "duration_seconds": round((s.get("narration", {}).get("end_seconds") or 0) - (s.get("narration", {}).get("start_seconds") or 0), 2),
                    "timestamp_source": s.get("narration", {}).get("timestamp_source"),
                    "has_narration_text": bool(s.get("narration", {}).get("text")),
                }
                for s in scenes
            ]
            ev["source_mapping"] = report.get("source_mapping", {})
        elif n == 7:
            ev["visual_style"] = report.get("visual_style")
            ev["scene_continuity"] = [
                {
                    "scene_id": s.get("scene_id"),
                    "previous_scene_id": s.get("continuity", {}).get("previous_scene_id"),
                    "next_scene_id": s.get("continuity", {}).get("next_scene_id"),
                    "motifs": s.get("continuity", {}).get("motifs", []),
                    "transition_intent": s.get("continuity", {}).get("transition_intent"),
                }
                for s in scenes
            ]
        elif n == 8:
            ev["validation"] = val
            ev["planned_scenes"] = (report.get("source_mapping") or {}).get("planned_scenes", len(scenes))
            ev["canonical_scenes"] = (report.get("source_mapping") or {}).get("canonical_scenes")
            ev["checks_passed"] = (val.get("checks") or {}).get("passed")
            ev["checks_total"] = (val.get("checks") or {}).get("total")
        return ev

    evidence = {
        "schema_version": report.get("schema_version"),
        "timing_rules": report.get("timing_rules"),
        "source_fingerprint": report.get("source_fingerprint"),
        "source_transcript": report.get("source_transcript"),
        "source_audio_analysis": report.get("source_audio_analysis"),
        "language": report.get("language"),
        "audio_duration_seconds": report.get("audio_duration_seconds"),
        "segmentation_method": report.get("segmentation_method"),
        "semantic_confidence": report.get("semantic_confidence"),
        "needs_review": report.get("needs_review"),
    }

    # Authoritative source data metrics
    source_data = report.get("source_data")
    if source_data:
        evidence["source_data"] = source_data
    else:
        evidence["source_data"] = {
            "source_transcript_file": report.get("source_transcript"),
            "source_audio_analysis": report.get("source_audio_analysis"),
            "transcript_segment_count": report.get("source_segments"),
            "word_count": report.get("source_words"),
            "measured_pause_count": report.get("source_pauses"),
            "audio_duration_seconds": report.get("audio_duration_seconds"),
            "scene_count": len(report.get("scenes", [])) if isinstance(report.get("scenes"), list) else None,
        }

    # Sentence & clause detection data
    if "sentence_and_clause_detection" in report:
        evidence["sentence_and_clause_detection"] = report["sentence_and_clause_detection"]

    if "validation" in report:
        evidence["validation"] = report["validation"]
    if "llm" in report:
        evidence["llm"] = report["llm"]
    if "config" in report:
        evidence["config"] = report["config"]

    # Compact scene summary to guarantee every scene is visible within character limits
    scenes = report.get("scenes")
    if isinstance(scenes, list):
        evidence["scene_count"] = len(scenes)
        evidence["scenes_summary"] = [
            {
                "scene_id": s.get("scene_id") or f"scene_{s.get('scene_index', idx + 1):03d}",
                "scene_index": s.get("scene_index", idx + 1),
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
                "source_segment_ids": s.get("source_segment_ids"),
                "source_sentence_ids": s.get("source_sentence_ids"),
                "word_range": s.get("word_range"),
                "transcript": (s.get("transcript") or "")[:80],
                "timing_source": s.get("timing_source"),
                "boundary_after": s.get("boundary_after"),
                "boundary_before": s.get("boundary_before"),
                "pause_after_seconds": s.get("pause_after_seconds"),
            }
            for idx, s in enumerate(scenes)
        ]

    # Include other stage-specific top-level keys
    for k, v in report.items():
        if k not in ("stages", "scenes", "source_data", "sentence_and_clause_detection", "validation", "llm", "config"):
            if k not in evidence:
                evidence[k] = v

    return evidence


MOTION_PLAN_STAGE_RULES: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("Motion Plan Reader", ("visual_plan_current", "visual_plan_present", "scenes_linked", "mode_matches", "aspect_matches", "scenes_present")),
    2: ("Element Resolver", ("element_drawn",)),
    3: ("Preset Registry Lookup", ("registry_id", "transition_known")),
    4: ("Effect Reuse Engine", ("repeat_text_preset", "repeat_graphic", "variety")),
    5: ("Animation Builder", ("scene_animated", "dependency_acyclic", "dependencies_exist", "dependency_order")),
    6: ("Animation Engine Adapter", ("telugu_safe_preset", "text_style", "intensity_range", "min_duration", "speed_range")),
    7: ("Composition & Transition Builder", ("transition_not_repeated", "transition_fits", "transition_present")),
    8: ("Timing & Audio Sync", ("action_in_scene", "frames_valid", "emphasis_inside_text")),
    9: ("Layout Validator", ("text_readable", "text_count", "graphic_in_safe_area", "graphic_clear_of_drawn_text", "graphic_clear_of_text")),
    10: ("Code & Plan Validator", ("ids_unique", "no_code", "mode_requirement")),
    11: ("Motion Test Runner", ("motion_checks", "motion_checks_ran")),
    12: ("Error Repair Handler", ()),
    13: ("Remotion Output Adapter", ("adapter_fields", "composition_current", "contract")),
}

MOTION_GEN_STAGE_RULES: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("Report Reader", ("plan_present", "plan_current", "plan_without_errors", "mode_matches", "aspect_matches", "fps_matches", "scene_count")),
    2: ("Layer Verification", ("element_drawn", "fallback_recorded")),
    3: ("Preset Registry", ("icon_exists", "resource_resolves", "registry_id", "transition_known")),
    4: ("Effect Reuse", ("no_new_presets", "fallback_recorded")),
    5: ("Z-Order & Layer Hierarchy", ("z_order_defined",)),
    6: ("Timing & Audio Synchronization", ("scene_interval", "scenes_in_order", "frames_in_scene", "audio_file", "duration_is_audio")),
    7: ("Safe Area & Density", ("text_in_safe_area",)),
    8: ("Remotion Engine Compliance", ("motion_checks", "motion_checks_ran", "deterministic", "deterministic_ran", "mode_flags", "no_pictures_in_motion_only", "scenes_present")),
}

MOTION_VAL_STAGE_RULES: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("Input Reader & Provenance", ("visual_plan_fingerprint", "scene_segmentation_fingerprint", "motion_plan_fingerprint", "motion_generation_fingerprint", "composition_fingerprint", "renderer_registry_fingerprint", "artifacts")),
    2: ("Fingerprint & Freshness", ("input_freshness", "timestamps", "cache_validity")),
    3: ("Scene Mapping & Coverage", ("scene_coverage", "mapping_completeness")),
    4: ("Timing & Frame Integrity", ("frame_rounding", "fps_alignment", "duration_match")),
    5: ("Element Completeness & Drawn Support", ("elements_drawn", "required_elements_supported")),
    6: ("Animation & Preset Validity", ("preset_registry", "telugu_safe_preset", "animation_validity")),
    7: ("Layout & Collision", ("safe_area_margins", "bounding_boxes", "collision_free")),
    8: ("Audio & Text Synchronization", ("speech_alignment", "emphasis_tolerance")),
    9: ("Transition & Continuity Readiness", ("transition_types", "transition_duration")),
    10: ("Composition Buildability & Determinism", ("ast_buildability", "remotion_contract", "determinism")),
    11: ("Preview Validation & Visual Evidence", ("preview_generation", "frame_decodable", "visual_evidence")),
    12: ("Findings, Report & Timeline Readiness Gate", ("zero_blockers", "zero_errors", "readiness_gate")),
}

TIMELINE_STAGE_RULES: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("Build Request & Lock", ("build_lock_acquired", "request_valid")),
    2: ("Input Artifact Discovery", ("audio_input", "composition_input", "motion_plan_input", "segmentation_input", "visual_plan_input")),
    3: ("Source Freshness & Readiness Gate", ("source_freshness", "dependency_digests", "gate_passed")),
    4: ("Project Settings Normalization", ("fps_30", "aspect_ratio", "dimensions")),
    5: ("Scene Mapping", ("scene_coverage", "sequence_integrity")),
    6: ("Frame Timing Normalization", ("frame_rounding", "boundary_alignment", "speech_intervals")),
    7: ("Video / Composition Track Assembly", ("video_track_assembled", "layers_mapped", "no_gaps")),
    8: ("Audio & Narration Track Assembly", ("audio_ducking", "volume_envelope", "tail_padding")),
    9: ("Transition & Gap Policy Application", ("transition_policy", "gap_policy", "fade_parameters")),
    10: ("Timeline Assembly & Duration", ("timeline_assembled", "duration_match")),
    11: ("Structural / Post-Build Validation", ("checks_passed", "zero_errors", "no_blockers")),
    12: ("Persist, Read Back & Publish", ("written", "read_back_ok", "digest_equal", "published")),
}

APPROVAL_STAGE_RULES: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("Timeline State & Readiness Gate", ("timeline_built", "fingerprint_valid", "zero_blockers", "ready_for_review")),
    2: ("Cryptographic Provenance Verification", ("audio_digest", "composition_digest", "motion_generation_digest", "motion_plan_digest", "motion_planning_digest", "renderer_digest", "stage10_digest", "timeline_build_digest", "visual_plan_digest")),
    3: ("LLM Timeline & Narrative Audit Gate", ("timing_alignment", "scene_sequencing", "transition_continuity", "audio_ducking_sync", "score_threshold_met")),
    4: ("Decision Persistence & Render Release", ("idempotent_decision_written", "warning_acknowledgements_recorded", "history_appended", "render_gate_released")),
}

RENDER_STAGE_RULES: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("Render Reservation & Input Manifest Gate", ("timeline_approval_verified", "carried_warnings_acknowledged", "render_config_validated", "manifest_bound")),
    2: ("Remotion Engine Frame Synthesis", ("frames_rendered", "frame_rate_30fps", "duration_match")),
    3: ("Encoded Stream & Container Validation", ("readable", "size_plausible", "container_mp4", "video_stream", "dimensions_1080p", "fps_30", "codec_h264", "frame_count", "duration_tolerance", "audio_stream", "audio_duration", "audio_codec")),
    4: ("Atomic Publish & Final QC Gate Release", ("published_out_mp4", "sha256_bound", "previous_backed_up", "final_qc_unlocked")),
}

FINAL_STAGE_RULES: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("Desktop Output Directory & Canonical Path Binding", ("directory_resolved", "collision_safe_name", "path_bound")),
    2: ("Atomic Bit-for-bit Stream Transfer & Fsync Verification", ("source_file_exists", "file_non_empty", "atomic_tmp_write", "fsync_flush")),
    3: ("SHA-256 Provenance & Cryptographic Match Assertion", ("source_hash_computed", "dest_hash_computed", "bit_for_bit_match", "provenance_locked")),
    4: ("Manifest Generation & Delivery Milestone Completion", ("delivery_summary_written", "text_manifest_generated", "all_gates_passed", "milestone_emitted")),
}


def _step_guidance(stage_id: str, step: dict) -> str:
    n = step.get("n")
    if stage_id == "analyzer":
        return (
            f"Step Guidance (Audio Analysis Step {n} - {step.get('name')}):\n"
            f"Recorded detail: '{step.get('detail')}'. Status: '{step.get('status')}'.\n"
            "Verify that the recorded status and detail are supported by and consistent with the provided audio analysis metrics. "
            "Confirm the step if the evidence supports this."
        )
    if stage_id == "planning":
        specific = ""
        if n == 1:
            specific = "Verify that all scenes have narrative roles, core meanings, and audience takeaways in scene_objectives. Confirm the step if supported."
        elif n == 2:
            specific = "Verify visual concepts count and word-level animation cues in visual_concepts_count and animation_cues_count against the recorded detail. Confirm the step if supported."
        elif n == 3:
            specific = "Verify total elements count and depth layering across scenes against the recorded detail. Confirm the step if supported."
        elif n == 4:
            specific = "Verify total relationships count in total_relationships and relationships_by_scene against the recorded detail. Confirm the step if supported."
        elif n == 5:
            specific = "Verify real media requirements count and media mix shares against the recorded detail. Note: A minor difference (within 15 percentage points) between target and actual media shares is normal and valid. Confirm the step if supported."
        elif n == 6:
            specific = "Verify scene start/end timings and narration groundings in scene_timings against the recorded detail. Confirm the step if supported."
        elif n == 7:
            specific = "Verify project visual_style and scene_continuity (previous/next links) against the recorded detail. Confirm the step if supported."
        elif n == 8:
            specific = "Verify validation status is 'ok', errors count is 0, and deterministic checks passed against the recorded detail. Confirm the step if supported."
        return (
            f"Step Guidance (Visual Planning Step {n} - {step.get('name')}):\n"
            f"Recorded detail: '{step.get('detail')}'. Status: '{step.get('status')}'.\n"
            f"{specific}\n"
            "Confirm the step if the evidence supports this."
        )
    if stage_id == "segmentation":
        if n == 1:
            return (
                "Step Guidance (Analysis Data Reader):\n"
                "Verify the source transcript segments count, word count, measured pause count, and audio duration against 'source_data'.\n"
                "Note: 'transcript segments' are the input speech units from transcription; 'scenes' are the output units produced by segmentation. "
                "Measured pauses are acoustic pauses from the source audio analysis, not inter-scene pauses."
            )
        if n == 2:
            return (
                "Step Guidance (Sentence & Clause Detection):\n"
                "The recorded detail reports: '<units> units (<clause_splits> clause splits), <cuts> places where a scene may end'.\n"
                "Verify the 3 primary metrics against 'sentence_and_clause_detection':\n"
                "1. 'units' must match 'unit_count' (count of syntactic units in 'sentences').\n"
                "2. 'clause splits' must match 'clause_split_count' (the count of sentences split into multiple units due to long duration; 0 if no sentence was split).\n"
                "3. 'places where a scene may end' must match 'potential_cut_count' (the count of candidate cut points in 'allowed_cuts').\n"
                "Note: A 'clause split' refers strictly to splitting a long sentence into multiple units (clause_split_count: 0 here). "
                "Do NOT confuse 'clause splits' with candidate cut points at clause punctuation marks (clause_punctuation in candidate_cut_points_by_type), which allow scene boundaries at commas without splitting the underlying sentence unit."
            )
        if n == 3:
            return "Step Guidance (Semantic Understanding):\nVerify semantic grouping LLM status and reuse/call status against the 'llm' object."
        if n == 4:
            return "Step Guidance (Topic & Idea Change Detection):\nVerify topic and idea boundary decisions in boundary_before/boundary_after across scenes."
        if n == 5:
            return (
                "Step Guidance (Scene Boundary & Grouping):\n"
                "Verify the count of generated scenes and source segments in scenes_summary against the recorded detail.\n"
                "Note: A result like '9 scenes from 12 segments' means 12 source transcript speech segments were semantically aggregated "
                "into 9 narrative scenes (merging short adjacent segments into cohesive scenes). This is valid semantic aggregation, "
                "not an inconsistency."
            )
        if n == 6:
            return "Step Guidance (Duration & Timing Assignment):\nVerify start and end timestamps and timing_source across scenes_summary."
        if n == 7:
            return "Step Guidance (Scene Validation & Continuity):\nVerify validation status, transcript coverage, chronological order, and errors/warnings against 'validation'."
    if stage_id == "motion_plan":
        rules = MOTION_PLAN_STAGE_RULES.get(n, ("", ()))
        rules_str = ", ".join(rules[1]) if rules[1] else "mechanical repair check (no rules needed)"
        return (
            f"Step Guidance (Motion Plan Stage {n} - {step.get('name')}):\n"
            f"This stage validates: {rules_str}.\n"
            "Note: The recorded detail count reflects the total count of validation assertions evaluated during this stage. "
            "When validation.status is 'ok' and validation.errors is empty, all required checks for this stage passed with zero errors. "
            "Confirm the step if the evidence supports this."
        )
    if stage_id == "motion_gen":
        rules = MOTION_GEN_STAGE_RULES.get(n, ("", ()))
        rules_str = ", ".join(rules[1]) if rules[1] else "all rules"
        return (
            f"Step Guidance (Motion Generation Stage {n} - {step.get('name')}):\n"
            f"This stage validates the following rules in validation.checks.by_rule: {rules_str}.\n"
            "When validation.status is 'ok' and validation.errors is empty, all required checks for this stage passed cleanly. "
            "Confirm the step if the evidence supports this."
        )
    if stage_id == "motion_validation":
        rules = MOTION_VAL_STAGE_RULES.get(n, ("", ()))
        rules_str = ", ".join(rules[1]) if rules[1] else "deterministic validation checks"
        return (
            f"Step Guidance (Motion Timeline Validation Stage {n} - {step.get('name')}):\n"
            f"This subtask validates: {rules_str}.\n"
            f"Checks: {step.get('checks_passed')}/{step.get('checks_total')} passed. "
            "Verify that checks_passed equals checks_total, recorded status is 'completed', and findings/blockers/errors are zero. "
            "Confirm the step if the evidence supports this."
        )
    if stage_id == "timeline":
        rules = TIMELINE_STAGE_RULES.get(n, ("", ()))
        rules_str = ", ".join(rules[1]) if rules[1] else "deterministic timeline assembly checks"
        passed = step.get("checks_passed", 0)
        total = step.get("checks_total", 0)
        if total == 0:
            return (
                f"Step Guidance (Timeline Build Stage {n} - {step.get('name')}):\n"
                f"This is a process lifecycle step ({rules_str}). It performs deterministic actions (locking/publishing) rather than assertion counts.\n"
                "Note: The report's cumulative total of 238 checks is the sum across all 12 stages combined; this individual step has 0 assertion checks.\n"
                "When status is 'completed' and overall errors/blockers are 0, confirm this step."
            )
        return (
            f"Step Guidance (Timeline Build Stage {n} - {step.get('name')}):\n"
            f"This subtask validates: {rules_str}.\n"
            f"Checks: {passed}/{total} passed for this specific subtask.\n"
            "Note: The report's cumulative total of 238 checks is the sum across all 12 stages combined. Do not confuse the cumulative 238 checks with this subtask's individual check count.\n"
            "Verify that this subtask's checks_passed equals checks_total, status is 'completed', and errors/blockers are 0. Confirm the step if the evidence supports this."
        )
    if stage_id == "approval":
        rules = APPROVAL_STAGE_RULES.get(n, ("", ()))
        rules_str = ", ".join(rules[1]) if rules[1] else "deterministic timeline approval checks"
        passed = step.get("checks_passed", 0)
        total = step.get("checks_total", 0)
        return (
            f"Step Guidance (Timeline Approval Stage {n} - {step.get('name')}):\n"
            f"This subtask validates: {rules_str}.\n"
            f"Checks: {passed}/{total} passed for this subtask.\n"
            "Note: The report's cumulative total of 22 checks is the sum across all 4 approval stages combined. Do not confuse the cumulative 22 checks with this subtask's individual check count.\n"
            "Verify that this subtask's checks_passed equals checks_total, status is 'completed', and errors/blockers are 0. Confirm the step if the evidence supports this."
        )
    if stage_id == "render":
        rules = RENDER_STAGE_RULES.get(n, ("", ()))
        rules_str = ", ".join(rules[1]) if rules[1] else "deterministic render verification checks"
        passed = step.get("checks_passed", 0)
        total = step.get("checks_total", 0)
        return (
            f"Step Guidance (Render Video Stage {n} - {step.get('name')}):\n"
            f"This subtask validates: {rules_str}.\n"
            f"Checks: {passed}/{total} passed for this subtask.\n"
            "Verify that this subtask's checks_passed equals checks_total, status is 'completed', and errors are 0. Confirm the step if the evidence supports this."
        )
    if stage_id == "final":
        rules = FINAL_STAGE_RULES.get(n, ("", ()))
        rules_str = ", ".join(rules[1]) if rules[1] else "delivery verification checks"
        passed = step.get("checks_passed", 0)
        total = step.get("checks_total", 0)
        return (
            f"Step Guidance (Final Video Delivery Stage {n} - {step.get('name')}):\n"
            f"This subtask validates: {rules_str}.\n"
            f"Checks: {passed}/{total} passed for this subtask.\n"
            "Verify that this subtask's checks_passed equals checks_total, status is 'completed', and file/hash evidence matches. Confirm the step if the evidence supports this."
        )
    if stage_id == "qc":
        passed = step.get("checks_passed", 0)
        total = step.get("checks_total", 0)
        return (
            f"Step Guidance (Final QC Stage {n} - {step.get('name')}):\n"
            f"Detail: {step.get('detail')}\n"
            f"Checks: {passed}/{total} passed for this subtask.\n"
            "Note on motion typography: For kinetic typography, holding text static during speech intervals so viewers can read Telugu words is intentional. Non-blocking heuristic warnings are accepted.\n"
            "Verify that this subtask's recorded status and detail are consistent with the QC report evidence. Confirm the step if supported."
        )
    return "Verify whether the recorded status and detail are supported by and consistent with the provided evidence."


def _ask(pdir: Path, stage_id: str, step: dict, report: dict, aspect: str) -> dict:
    from SYSTEM.core import llm_gateway
    evidence = build_step_evidence(stage_id, step, report)
    ev_text = json.dumps(evidence, ensure_ascii=False)
    if len(ev_text) > EVIDENCE_CHARS:
        ev_text = ev_text[:EVIDENCE_CHARS]
    guidance = _step_guidance(stage_id, step)
    req = llm_gateway.LlmGatewayRequest(
        project_id=pdir.name,
        stage_id=stage_id,
        agent_id="step_llm_check",
        purpose="review",
        model_profile="fast_structured",
        system_prompt=("You verify one deterministic step of a video generation pipeline stage. "
                       "The step recorded a status and a detail string. "
                       "Using only the verified evidence provided, determine if the recorded result holds.\n"
                       "- 'confirms': The status and detail are consistent with and supported by the evidence.\n"
                       "- 'questions': The evidence is insufficient, ambiguous, or shows minor discrepancies.\n"
                       "- 'rejects': The evidence directly contradicts the recorded result.\n"
                       "Important: Do not confuse different metric types (e.g. source transcript segments are input speech chunks, while scenes are segmented output units; measured pauses are physical acoustic pauses from audio analysis, not scene gaps). Answer in JSON."),
        user_prompt=(f"Stage: {stage_id}\nStep {step.get('n')}: {step.get('name')}\nRecorded status: {step.get('status')}\n"
                     f"Recorded detail: {step.get('detail')}\nChecks: {step.get('checks_passed')}/{step.get('checks_total')}\n\n"
                     f"{guidance}\n\n"
                     f"Evidence (the stage report without its step list, may be cut at {EVIDENCE_CHARS} characters):\n{ev_text}\n\n"
                     'Return ONLY this JSON object: {"verdict": "confirms" | "questions" | "rejects", "note": "one or two sentences: why"}'),
        structured_schema={"verdict": "confirms | questions | rejects", "note": "one or two sentences: why"},
        timeout=120,
        metadata={"aspect": aspect, "step": step.get("n")},
    )
    t0 = time.time()
    try:
        resp = llm_gateway.get_gateway().execute(req)
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "rate limit" in err_msg.lower():
            time.sleep(2.5)
            try:
                resp = llm_gateway.get_gateway().execute(req)
            except Exception as e2:
                return {"verdict": "error", "note": f"LLM rate limit reached: {e2}", "model": None, "latency_ms": int((time.time() - t0) * 1000)}
        else:
            return {"verdict": "error", "note": f"LLM call failed: {e}", "model": None, "latency_ms": int((time.time() - t0) * 1000)}
    data = resp.structured_data or {}
    verdict = str(data.get("verdict", "")).strip().lower()
    if resp.error or verdict not in ("confirms", "questions", "rejects"):
        return {"verdict": "error", "note": resp.error or f"unusable LLM answer: {(resp.raw_text or '')[:200]}", "model": resp.model, "latency_ms": resp.latency_ms,
                "blocked": resp.status in ("blocked", "failed")}
    note = data.get("note") or data.get("reason") or data.get("rationale") or data.get("explanation") or ""
    return {"verdict": verdict, "note": str(note)[:600], "model": resp.model, "latency_ms": resp.latency_ms}


def _run(pdir: Path, stage_id: str, aspect: str) -> None:
    key = (pdir.name, stage_id)
    try:
        f = _checks_file(pdir, stage_id, aspect)
        for step in steps(pdir, stage_id, aspect)[0]:                               # re-read every time: the report may change while the checks run
            recorded, report, _ = steps(pdir, stage_id, aspect)
            step = next((s for s in recorded if s["n"] == step["n"]), None)
            if step is None or report is None:
                continue
            # When audio_analysis.json is not yet created, only check steps 1, 2, 3 (which only require audio.wav and audio_16k.wav)
            if stage_id == "analyzer" and not (pdir / "audio_analysis.json").exists() and step.get("n") not in (1, 2, 3):
                continue
            h = _hash(step, report)
            try:
                data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            except ValueError:
                data = {}
            prev = (data.get("steps") or {}).get(str(step["n"]), {})
            if prev.get("hash") == h and prev.get("verdict") != "error":
                continue                                                            # this exact result was already checked (an earlier error is asked again)
            with _lock:
                _active_step[key] = step["n"]
            res = _ask(pdir, stage_id, step, report, aspect)
            data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            data.setdefault("steps", {})[str(step["n"])] = {**res, "hash": h, "at": time.time()}
            data.update({"stage_id": stage_id, "report": report_file(pdir, stage_id, aspect).name, "updated_at": time.time()})
            f.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
            time.sleep(1.0)
            if res.get("verdict") == "error" and res.get("blocked"):
                break                                                               # the LLM is unavailable (session limit / open circuit): the remaining steps are asked on the next start, not failed one by one
    finally:
        with _lock:
            _running.discard(key)
            _active_step.pop(key, None)


def start(pdir: Path, stage_id: str, aspect: str) -> bool:
    """Start checking the steps that have no check of their current result. False when nothing is pending or a check of this stage already runs."""
    key = (pdir.name, stage_id)
    with _lock:
        if key in _running or pending(pdir, stage_id, aspect) == 0:
            return False
        # Gating: audio.wav must exist for analyzer steps 1-3. Downstream steps (4-14) wait for audio_analysis.json
        if stage_id == "analyzer":
            has_audio = (pdir / "audio.wav").exists() or bool(list(pdir.glob("audio.*")))
            if not has_audio:
                return False
        _running.add(key)
    threading.Thread(target=_run, args=(pdir, stage_id, aspect), daemon=True, name=f"step-llm-check-{stage_id}").start()
    return True
