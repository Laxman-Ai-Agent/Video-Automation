"""Motion & Timeline Validation (roadmap improvements/Motion_Timeline_Validation_Complete_Roadmap), Stage 10 of the pipeline: between Motion Generation and the Timeline Build.
It answers ONE question: "is this motion output valid, current and safe to use to build a timeline?" It is read-only: it reads the current artifacts (Scene Segmentation, Visual Plan, Motion Plan,
Motion Generation report, composition, transcript, registry), writes only its own report `motion_timeline_validation[_9x16].json` and never changes, repairs or moves anything upstream.
No Claude call, no code from a plan is executed. It does NOT validate a timeline that does not exist yet: it reports "timeline readiness".

The 12 internal stages (checks of one module, not 12 agents; the rules are in motion_validation_rules.py):
  1 Input Reader & Provenance   2 Fingerprint & Freshness   3 Scene Mapping & Coverage   4 Timing & Frame Integrity   5 Element Completeness & Drawn Support   6 Animation & Preset Validity
  7 Layout & Collision          8 Audio & Text Sync          9 Transition & Continuity    10 Buildability & Determinism  11 Preview Validation   12 Readiness Gate
Readiness: ready | ready_with_warnings | needs_review | blocked | stale | failed. A required element that is not drawn is a BLOCKER unless an authorized, reasoned, fingerprint-bound exception
(`motion_validation_exceptions[_9x16].json`) exists; "accepted" in motion_fixes.json (Solve warnings) is not such an exception. Stale or failed validation is never green."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from SYSTEM.policies import rule_switches
from . import config, motion_generation as mg, motion_planning as mp

SCHEMA = "1.0"
VERSION = 1                                    # the validator (structure of the report, how the stages run)
RULE_SET = "1.1"                               # bump when a rule's meaning changes (part of every fingerprint and of every stage cache key)
EPS = mp.EPS
READY = ("ready", "ready_with_warnings")
STAGES = (
    ("input_provenance", "Input Reader", "Input Reader & Provenance", "Reading the current artifacts and where they came from"),
    ("fingerprint_freshness", "Fingerprint Check", "Fingerprint & Freshness", "Proving every input is current"),
    ("scene_mapping", "Scene Mapping", "Scene Mapping & Coverage", "One planned scene for every canonical scene"),
    ("timing_frame", "Timing & Frames", "Timing & Frame Integrity", "Seconds, frames, gaps and exits"),
    ("element_completeness", "Element Coverage", "Element Completeness & Drawn Support", "Every required element really drawn"),
    ("animation_preset", "Preset & Animation", "Animation & Preset Validity", "Presets, properties and descriptors"),
    ("layout_collision", "Layout & Collisions", "Layout & Collision", "Safe area, overlaps and z-order"),
    ("audio_text_sync", "Audio & Text Sync", "Audio & Text Synchronization", "Audio, text timing and emphasis words"),
    ("transition_readiness", "Transition Readiness", "Transition & Continuity Readiness", "Transitions the timeline can build"),
    ("buildability", "Buildability", "Composition Buildability & Determinism", "Renderer contract, read-back, repeat build"),
    ("preview_validation", "Preview Validation", "Preview Validation & Visual Evidence", "Stills and what was reviewed by a person"),
    ("readiness_gate", "Readiness Gate", "Findings, Report & Timeline Readiness Gate", "One truthful decision"),
)
N = len(STAGES)
SEVERITIES = ("blocker", "error", "warning", "info")
# Warnings of these rules are visual / readability defects only a person can judge: unresolved they make the readiness `needs_review`. Every other warning is policy-permitted
# (it stays visible and traceable and gives `ready_with_warnings`).
REVIEW_RULES = frozenset({"layout.text_graphic_collision", "layout.graphic_graphic_collision", "layout.safe_margins", "layout.overflow_clip", "text.safe_area", "timing.readability_before_exit",
                          "audio.duration_compatible", "continuity.motif_notes_valid"})
EXCEPTIONABLE = frozenset({"element.required_has_drawable"} | REVIEW_RULES)       # an error or another blocker is never waived: it is fixed in the stage that owns it
MIN_REASON = 10
CONFIG = {
    "timing": {"frame_rounding_policy": "floor(seconds x fps + 0.5), the end frame is exclusive (the project's one rule, motion_planning.fr)", "emphasis_alignment_tolerance_ms": 60,
               "preserve_intentional_gaps": True},
    "layout": {"safe_area_source": "config.SAFE_AREA", "use_actual_drawn_boxes_when_available": True, "unknown_geometry_is_not_a_pass": True},
    "readiness": {"required_undrawn_blocks_by_default": True, "explicit_exceptions_required": True, "stale_inputs_block": True, "validation_is_read_only": True},
    "preview": {"sample_changed_or_flagged_scenes": True, "separate_still_and_motion_review": True, "human_review_required_for_human_review_status": True},
}
EMPHASIS_TOLERANCE_S = CONFIG["timing"]["emphasis_alignment_tolerance_ms"] / 1000      # the project's own policy (motion_gen_rules stage 8 uses the same 0.06 s), not a new default


class ValidationError(Exception):
    """The validation could not be done reliably, or a request is refused (a message for the user)."""


def names(aspect: str) -> dict[str, str]:
    sfx = "_9x16" if aspect == "9:16" else ""
    return {"report": f"motion_timeline_validation{sfx}.json", "exceptions": f"motion_validation_exceptions{sfx}.json", "preview": f"motion_validation_preview{sfx}"}


def sha(data: str | bytes) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()[:16]


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _file_sha(path: Path) -> str | None:
    try:
        return sha(path.read_bytes())
    except OSError:
        return None


# ---------- the inputs and their fingerprints ----------
def input_files(pdir: Path, aspect: str) -> dict[str, Path]:
    """The artifacts the validation reads, by role (the real names of this repository)."""
    from . import motion_animation
    comp, gen, mplan = mg.names(aspect)
    return {
        "project": pdir / "project.json",
        "segmentation": pdir / "scene_segmentation.json",
        "visual_plan": pdir / "visual_planning.json",
        "motion_plan": pdir / mplan,
        "motion_planning": pdir / mp._names(aspect)[1],
        "motion_generation": pdir / gen,
        "motion_animation": pdir / motion_animation.names(aspect),
        "composition": pdir / comp,
        "fixes": pdir / mp.FIXES,
    }


def input_digests(pdir: Path, aspect: str) -> dict[str, str | None]:
    """A digest per input. The audio is its name and size (it is large; a changed take changes the size), the transcript is the file the composition was built from."""
    from . import pipeline
    d = {k: _file_sha(p) for k, p in input_files(pdir, aspect).items()}
    audio = next(iter(sorted(pdir.glob("audio.*"))), None)
    try:                                                                       # project.json also holds the job state: only the settings that change what is valid
        info = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
        d["project"] = sha(canon({k: info.get(k) for k in ("aspect", "use_images", "motion_branch")}))
    except (OSError, ValueError):
        d["project"] = None
    d["scene_plan"] = _file_sha(pdir / "scene_plan.json")                       # a project without a stored Visual Plan derives it from the scene plan
    d["audio"] = f"{audio.name}:{audio.stat().st_size}" if audio else None
    d["words"] = next((_file_sha(pdir / n) for n in ("transcript_fixed.json", "transcript_corrected.json", "transcript.json") if (pdir / n).exists()), None)
    d["renderer"] = pipeline._remotion_src_digest()
    d["resources"] = _resources_fp(input_files(pdir, aspect)["composition"])    # ONLY the resources this composition uses (hash + status): an unrelated registry change changes nothing
    gen_dir = pdir / "generated_motion"
    if gen_dir.exists():
        d["generated_motion"] = sha("".join(f"{f.name}:{f.stat().st_size}:{_file_sha(f)}" for f in sorted(gen_dir.glob("*")) if f.is_file()))
    d["config"] = sha(canon([config.SAFE_AREA, aspect, CONFIG]))
    return d


def _resources_fp(comp_path: Path) -> str | None:
    from . import resource_library
    try:
        return sha(resource_library.fingerprint(json.loads(comp_path.read_text(encoding="utf-8"))))
    except (OSError, ValueError):
        return None


def fingerprint(pdir: Path, aspect: str, digests: dict | None = None) -> str:
    """What a report was made from: every input, the validator and the rule set. Exceptions and preview evidence are decisions / derived files, not inputs: they are not in it."""
    d = digests if digests is not None else input_digests(pdir, aspect)
    return sha(canon([d, SCHEMA, VERSION, RULE_SET]))


STAGE_INPUTS = {                                # the invalidation map: a stage is redone only when one of ITS inputs (or the rule set) changed
    "fingerprint_freshness": ("visual_plan", "scene_plan", "segmentation", "motion_planning", "motion_plan", "motion_generation", "motion_animation", "generated_motion", "composition", "renderer", "project", "config"),
    "scene_mapping": ("visual_plan", "scene_plan", "segmentation", "motion_planning", "motion_plan", "motion_generation", "composition"),
    "timing_frame": ("motion_planning", "motion_plan", "motion_generation", "composition", "config"),
    "element_completeness": ("visual_plan", "scene_plan", "motion_planning", "motion_plan", "motion_generation", "composition", "fixes"),
    "animation_preset": ("motion_plan", "motion_generation", "motion_animation", "generated_motion", "composition", "renderer", "resources"),
    "layout_collision": ("motion_plan", "composition", "project", "config", "renderer", "motion_animation", "generated_motion"),
    "audio_text_sync": ("motion_plan", "composition", "words", "audio", "segmentation", "motion_planning", "config", "visual_plan", "motion_animation", "generated_motion"),
    "transition_readiness": ("motion_planning", "motion_plan", "composition", "renderer"),
    "buildability": ("motion_generation", "motion_animation", "composition", "renderer", "motion_planning", "motion_plan"),
}


def stage_key(sid: str, digests: dict) -> str:
    return sha(canon([sid, RULE_SET, VERSION, [digests.get(k) for k in STAGE_INPUTS.get(sid, ())]]))


# ---------- the findings ----------
def finding_id(rule: str, scene: str | None, target: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9._:-]+", "-", f"{rule}:{scene or 'project'}:{target or '-'}")


class V:
    """What the stages record: checks passed / applicable / skipped per stage, and one finding per failed rule and target (the same finding is never added twice)."""

    def __init__(self) -> None:
        self.findings: dict[str, dict] = {}
        self.counts: dict[str, dict[str, int]] = {s[0]: {"passed": 0, "total": 0, "skipped": 0} for s in STAGES}
        self.flagged_scenes: set[str] = set()

    def _add(self, stage, rule, severity, message, scene, target, evidence, owner, action) -> None:
        fid = finding_id(rule, scene, target)
        if fid in self.findings:
            self.findings[fid]["occurrences"] += 1
            return
        self.findings[fid] = {"finding_id": fid, "rule_id": rule, "stage_id": stage, "severity": severity, "status": "unresolved", "scene_id": scene, "element_id": target, "message": message,
                              "evidence": evidence or {}, "owner_stage": owner, "suggested_action": action, "can_auto_fix": False, "exceptionable": rule in EXCEPTIONABLE and severity in ("blocker", "warning"),
                              "exception": None, "occurrences": 1}
        if scene and severity in ("blocker", "error", "warning"):
            self.flagged_scenes.add(scene)

    def check(self, stage: str, rule: str, ok: bool, severity: str, message: str, scene: str | None = None, target: str | None = None, evidence: dict | None = None,
              owner: str = "motion_generation", action: str = "") -> bool:
        c = self.counts[stage]
        c["total"] += 1
        if ok or rule_switches.is_off("motion_validation", rule):             # a rule the user switched off is never evaluated
            c["passed"] += 1
            return True
        self._add(stage, rule, severity, message, scene, target, evidence, owner, action or f"fix it in {owner.replace('_', ' ')}, then validate again")
        return ok

    def skip(self, stage: str, rule: str, message: str, scene: str | None = None, target: str | None = None, evidence: dict | None = None, owner: str = "motion_generation", severity: str = "info") -> None:
        """A check that could not be done (unknown geometry, no data): said, never counted as passed."""
        self.counts[stage]["skipped"] += 1
        self._add(stage, rule, severity, message, scene, target, evidence, owner, "")

    def of(self, stage: str) -> list[dict]:
        return [f for f in self.findings.values() if f["stage_id"] == stage]


# ---------- exceptions (explicit human decisions) ----------
def ledger(pdir: Path, aspect: str) -> list[dict]:
    data = mp._read(pdir / names(aspect)["exceptions"])
    return data if isinstance(data, list) else []


def _save_ledger(pdir: Path, aspect: str, records: list[dict]) -> None:
    f = pdir / names(aspect)["exceptions"]
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def _active(rec: dict, fp: str) -> bool:
    return not rec.get("revoked_at") and rec.get("applies_to_fingerprint") == fp and rec.get("expires_when_inputs_change") is True


def apply_exceptions(findings: list[dict], recs: list[dict], fp: str) -> None:
    """An exception counts only for the exact fingerprint it was given for and never for an error: the finding becomes `accepted_for_version`, the technical issue is NOT fixed."""
    by = {r["finding_id"]: r for r in recs if _active(r, fp)}
    for f in findings:
        f["exception"], f["status"] = None, "unresolved"
        r = by.get(f["finding_id"])
        if r and f.get("exceptionable"):
            f["exception"], f["status"] = {k: r[k] for k in ("exception_id", "decision", "decision_by", "decision_at", "reason", "applies_to_fingerprint", "expires_when_inputs_change")}, "accepted_for_version"


# ---------- aggregation (stage 12) ----------
def counts_of(findings: list[dict]) -> dict:
    live = [f for f in findings if f["status"] == "unresolved"]
    n = lambda sev: sum(1 for f in live if f["severity"] == sev)
    return {"blockers": n("blocker"), "errors": n("error"), "warnings": n("warning"), "info": n("info"), "accepted_exceptions": sum(1 for f in findings if f["status"] == "accepted_for_version"),
            "unresolved_review_items": sum(1 for f in live if f["severity"] == "warning" and f["rule_id"] in REVIEW_RULES)}


def readiness_of(findings: list[dict], stages: list[dict]) -> str:
    live = [f for f in findings if f["status"] == "unresolved"]
    if any(s["status"] == "failed" for s in stages):
        return "failed"
    if any(f["severity"] in ("blocker", "error") for f in live) or any(s["status"] == "skipped_due_to_dependency" for s in stages):      # a "blocked" stage always has such a finding: a decision on it can lift it
        return "blocked"
    if any(f["severity"] == "warning" and f["rule_id"] in REVIEW_RULES for f in live):
        return "needs_review"
    if any(f["severity"] == "warning" for f in live) or any(f["status"] == "accepted_for_version" for f in findings) or any(s["checks_skipped"] for s in stages):
        return "ready_with_warnings"
    return "ready"


def restatus(findings: list[dict], stages: list[dict]) -> None:
    """The stage statuses follow the decisions: a stage whose blockers were accepted is no longer shown as blocked (its findings still are, as accepted_for_version)."""
    by = {f["finding_id"]: f for f in findings}
    for s in stages:
        if s["status"] in ("skipped_due_to_dependency", "failed") or not s["finding_ids"] and s["status"] == "completed":
            continue
        fs = [by[i] for i in s["finding_ids"] if i in by]
        live = [f for f in fs if f["status"] == "unresolved"]
        s["status"] = "blocked" if any(f["severity"] in ("blocker", "error") for f in live) else "warning" if (any(f["severity"] == "warning" for f in fs) or s["checks_skipped"] or any(f["status"] == "accepted_for_version" for f in fs)) else "completed"


NEXT = {"ready": "build_timeline_when_you_choose", "ready_with_warnings": "build_timeline_when_you_choose", "needs_review": "review_warnings_or_record_explicit_exceptions",
        "blocked": "resolve_blockers_in_the_owner_stage_or_record_an_explicit_exception", "stale": "run_validation_again", "failed": "see_error_and_run_validation_again"}


def _stage_record(sid: str, v: V, key: str, ms: int, cache: dict) -> dict:
    n = next(i for i, s in enumerate(STAGES) if s[0] == sid)
    c, fs = v.counts[sid], v.of(sid)
    status = "blocked" if any(f["severity"] in ("blocker", "error") for f in fs) else "warning" if (c["skipped"] or any(f["severity"] == "warning" for f in fs)) else "completed"
    return {"n": n + 1, "stage_id": sid, "name": STAGES[n][2], "label": STAGES[n][1], "status": status, "progress_percent": 100, "checks_passed": c["passed"], "checks_total": c["total"], "checks_skipped": c["skipped"],
            "finding_ids": [f["finding_id"] for f in fs], "input_fingerprint": key, "duration_ms": ms, "cache": cache}


# ---------- run ----------
def _ensure_preview(pdir: Path, aspect: str) -> None:
    """The run makes its own visual evidence (no person clicks Generate Preview): stills of the current composition when the preview is missing or not current. Only when Motion
    Generation is current and clean (the preview refuses otherwise, and the rules report that). A still that cannot be made fails the run with its exact cause."""
    from . import motion_gen_report, motion_validation_preview as pv
    gen = motion_gen_report.load(pdir, aspect)
    if gen is None or gen["stale"] or gen["validation"]["errors"] or pv.is_current(pv.load(pdir, aspect), gen["output"].get("composition_sha")):
        return
    pv.generate(pdir, aspect)


def run(pdir: Path, aspect: str, progress=None, force: bool = False) -> dict:
    """Validate and write the report. `force` redoes every stage; otherwise a stage whose inputs, rule set and validator are unchanged keeps its previous result (recorded as a cache hit)."""
    from . import motion_validation_rules as R
    say = progress or (lambda p, eta=None: None)
    _ensure_preview(pdir, aspect)
    t0 = time.perf_counter()
    digests = input_digests(pdir, aspect)
    fp0 = fingerprint(pdir, aspect, digests)
    prev = _read_report(pdir, aspect)
    try:
        x = R.X(pdir, aspect)
        v, records = V(), []
        reuse = prev is not None and not force and prev.get("rule_set") == RULE_SET and prev.get("validator", {}).get("version") == VERSION and prev.get("phase_status") == "completed"
        old = {s["stage_id"]: s for s in prev["stages"]} if reuse else {}
        old_findings = {f["finding_id"]: f for f in prev["findings"]} if reuse else {}
        halted = None
        for i, (sid, _lab, _name, _desc) in enumerate(STAGES[:-1]):
            say(5 + 85 * i / (N - 1))
            t1 = time.perf_counter()
            key = stage_key(sid, digests)
            if halted and sid not in ("input_provenance", "preview_validation"):
                rec = _stage_record(sid, v, key, 0, {"hit": False, "reason": "not run"})
                rec.update(status="skipped_due_to_dependency", progress_percent=0, detail=halted)
                records.append(rec)
                continue
            cached = old.get(sid)
            if cached and sid in STAGE_INPUTS and cached.get("input_fingerprint") == key and cached["status"] in ("completed", "warning", "blocked"):
                for fid in cached["finding_ids"]:
                    f = old_findings.get(fid)
                    if f:
                        v.findings[fid] = {**f, "status": "unresolved", "exception": None}
                        if f.get("scene_id") and f["severity"] in ("blocker", "error", "warning"):
                            v.flagged_scenes.add(f["scene_id"])
                v.counts[sid] = {"passed": cached["checks_passed"], "total": cached["checks_total"], "skipped": cached["checks_skipped"]}
                if sid == "element_completeness":
                    x.element_summary, x.element_rows = cached.get("elements") or {}, cached.get("element_rows") or []
                records.append({**cached, "cache": {"hit": True, "reason": "inputs, rule set and validator unchanged since the previous run"}, "duration_ms": 0})
                continue
            getattr(R, "stage_" + sid)(x, v)
            rec = _stage_record(sid, v, key, round((time.perf_counter() - t1) * 1000), {"hit": False, "reason": "forced" if force else "first run" if not cached else "an input of this stage changed"})
            if sid == "element_completeness":
                rec["elements"], rec["element_rows"] = x.element_summary, x.element_rows
            if sid == "input_provenance" and any(f["severity"] in ("blocker", "error") for f in v.of(sid)):
                halted = "an input is missing or unreadable: fix it first (see the Input Reader findings)"
            if sid == "fingerprint_freshness" and any(f["severity"] in ("blocker", "error") for f in v.of(sid)):
                halted = "an input is out of date: run the owner stage again, then validate (see the Fingerprint Check findings)"
            records.append(rec)
        say(92)
        findings = sorted(v.findings.values(), key=lambda f: (SEVERITIES.index(f["severity"]), f["scene_id"] or "", f["finding_id"]))
        records.append(_stage_record("readiness_gate", v, "", 0, {"hit": False, "reason": "always recomputed"}))
        rep = assemble(pdir, aspect, x, digests, fp0, findings, records, ledger(pdir, aspect))
        rep["timings_seconds"] = {"validate": round(time.perf_counter() - t0, 3)}
        res = commit(pdir, aspect, rep, fp0)
        from . import llm_review
        llm_review.run_stage_llm_review(pdir, "motion_validation", aspect)
        return res
    except Exception as e:
        write_failed(pdir, aspect, fp0, e)
        raise


def assemble(pdir: Path, aspect: str, x, digests: dict, fp: str, findings: list[dict], records: list[dict], recs: list[dict]) -> dict:
    apply_exceptions(findings, recs, fp)
    gate = records[-1]
    el = x.element_summary
    readiness = readiness_of(findings, records)
    summary = {"scenes_expected": el.get("scenes_expected", 0), "scenes_checked": el.get("scenes_checked", 0), **counts_of(findings), "required_not_drawn": el.get("required_not_drawn", 0),
               "optional_not_drawn": el.get("optional_not_drawn", 0), "approximate": el.get("approximate", 0), "stages_blocked": sum(1 for s in records if s["status"] in ("blocked", "skipped_due_to_dependency"))}
    live = sum(1 for f in findings if f["status"] == "unresolved")
    checks = [("report.summary_matches_findings", summary["blockers"] + summary["errors"] + summary["warnings"] + summary["info"] == live),
              ("report.no_false_green", not (readiness in READY and (summary["blockers"] or summary["errors"] or summary["stages_blocked"]))),
              ("report.stage_counts_honest", all(s["checks_passed"] <= s["checks_total"] for s in records))]
    bad = [c for c, ok in checks if not ok]
    gate.update(checks_passed=len(checks) - len(bad), checks_total=len(checks), status="failed" if bad else "completed", finding_ids=[])
    if bad:
        readiness = "failed"
    summary.update(checks_passed=sum(s["checks_passed"] for s in records), checks_total=sum(s["checks_total"] for s in records), checks_skipped=sum(s["checks_skipped"] for s in records))
    tech_score = max(0.0, min(100.0, 100.0 - (summary.get("blockers", 0) * 40.0 + summary.get("errors", 0) * 20.0 + summary.get("warnings", 0) * 3.0)))
    vis_score = 85.0 if readiness in READY else 60.0
    sem_score = 90.0 if not summary.get("required_not_drawn") else 50.0
    run_score = 100.0 if readiness != "failed" else 30.0
    ovr_score = round(0.35 * tech_score + 0.25 * vis_score + 0.25 * sem_score + 0.15 * run_score, 1)
    quality_assessment = {
        "dimensions": {
            "technical": round(tech_score, 1),
            "visual": round(vis_score, 1),
            "semantic": round(sem_score, 1),
            "runtime": round(run_score, 1),
            "overall": ovr_score,
        },
        "readiness": readiness,
    }
    return {"schema_version": SCHEMA, "phase": "motion_timeline_validation", "phase_status": "completed", "readiness": readiness, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "project_id": pdir.name,
            "validator": {"version": VERSION, "rule_set_version": RULE_SET}, "rule_set": RULE_SET, "config": x.cfg(), "policy": CONFIG, "source_fingerprint": fp, "inputs": x.inputs_block(digests),
            "summary": summary, "stages": records, "findings": findings, "elements": x.element_rows, "preview_evidence": x.preview_block(), "preview": x.preview_levels, "exceptions": recs,
            "quality_assessment": quality_assessment,
            "cache": {"stages_reused": sum(1 for s in records if s["cache"]["hit"]), "stages_run": sum(1 for s in records if not s["cache"]["hit"])}, "next_action": NEXT[readiness], "error": None,
            "note": "read-only: nothing upstream was changed; a timeline that is not built yet is not validated here (the pre-render check after the build does that)"}


def commit(pdir: Path, aspect: str, rep: dict, fp0: str) -> dict:
    """Write atomically, read back and compare. The inputs are fingerprinted again first: if one changed while the validation ran, the result is `stale`, never green."""
    if fingerprint(pdir, aspect) != fp0:
        rep["readiness"], rep["next_action"] = "stale", NEXT["stale"]
        rep["findings"].append({"finding_id": "report.commit_freshness:project:-", "rule_id": "report.commit_freshness", "stage_id": "readiness_gate", "severity": "blocker", "status": "unresolved", "scene_id": None,
                                "element_id": None, "message": "an input changed while the validation was running", "evidence": {}, "owner_stage": "project", "suggested_action": "validate again",
                                "can_auto_fix": False, "exceptionable": False, "exception": None, "occurrences": 1})
    return _write(pdir, aspect, rep)


def _write(pdir: Path, aspect: str, rep: dict) -> dict:
    f = pdir / names(aspect)["report"]
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    if canon(json.loads(f.read_text(encoding="utf-8"))) != canon(rep):
        raise ValidationError("the validation report read back from disk is not what was written")
    return rep


def write_failed(pdir: Path, aspect: str, fp: str, exc: Exception) -> None:
    """A validator that could not finish never leaves a green report: the old one is replaced by a failed one that says why."""
    rep = {"schema_version": SCHEMA, "phase": "motion_timeline_validation", "phase_status": "failed", "readiness": "failed", "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "project_id": pdir.name,
           "validator": {"version": VERSION, "rule_set_version": RULE_SET}, "rule_set": RULE_SET, "source_fingerprint": fp, "summary": {}, "stages": [], "findings": [], "inputs": {}, "exceptions": [],
           "next_action": NEXT["failed"], "error": f"{type(exc).__name__}: {exc}"[:400]}
    try:
        _write(pdir, aspect, rep)
    except Exception:                                   # the storage itself failed: the caller sees the original error, and no green report exists
        pass


# ---------- reading ----------
def _read_report(pdir: Path, aspect: str) -> dict | None:
    r = mp._read(pdir / names(aspect)["report"])
    return r if isinstance(r, dict) and r.get("schema_version") == SCHEMA else None


def load(pdir: Path, aspect: str) -> dict | None:
    """The stored report with `stale` (the inputs differ from the ones it was made from) and the exceptions applied for the CURRENT fingerprint. None when it has not been made.
    A stale report keeps the readiness it had (`readiness_at_validation`) but its readiness is `stale`."""
    rep = _read_report(pdir, aspect)
    if rep is None:
        return None
    try:
        cur = fingerprint(pdir, aspect)
    except OSError:
        cur = None
    rep["current_fingerprint"], rep["stale"] = cur, cur is None or rep.get("source_fingerprint") != cur
    if rep["stale"] and rep["phase_status"] == "completed":
        rep["readiness_at_validation"], rep["readiness"], rep["next_action"] = rep["readiness"], "stale", NEXT["stale"]
    elif rep["phase_status"] == "completed":
        apply_exceptions(rep["findings"], ledger(pdir, aspect), rep["source_fingerprint"])
        restatus(rep["findings"], rep["stages"])
        rep["summary"].update(counts_of(rep["findings"]), stages_blocked=sum(1 for st in rep["stages"] if st["status"] in ("blocked", "skipped_due_to_dependency")))
        rep["readiness"] = readiness_of(rep["findings"], rep["stages"])
        rep["next_action"] = NEXT[rep["readiness"]]
        rep["exceptions"] = ledger(pdir, aspect)
    return rep


def record_exception(pdir: Path, aspect: str, finding_id_: str, decision_by: str, reason: str, fp: str) -> dict:
    """An authorized, reasoned, fingerprint-bound decision about ONE finding. Refused for anything that is not exceptionable, for a stale report and for another fingerprint. It never edits an artifact."""
    rep = load(pdir, aspect)
    if rep is None or rep["phase_status"] != "completed":
        raise ValidationError("there is no completed validation report")
    if rep["stale"]:
        raise ValidationError("the report is out of date: validate again before deciding")
    if fp != rep["source_fingerprint"]:
        raise ValidationError("the exception names another fingerprint than the current report")
    f = next((x for x in rep["findings"] if x["finding_id"] == finding_id_), None)
    if f is None:
        raise ValidationError(f"no finding {finding_id_}")
    if not f.get("exceptionable"):
        raise ValidationError(f"{f['rule_id']} cannot be accepted: a {f['severity']} of this kind is fixed in {f['owner_stage'].replace('_', ' ')}")
    if not (decision_by or "").strip() or len((reason or "").strip()) < MIN_REASON:
        raise ValidationError(f"an exception needs the name of the person who decides and a reason of at least {MIN_REASON} characters")
    recs = ledger(pdir, aspect)
    same = next((r for r in recs if _active(r, fp) and r["finding_id"] == finding_id_), None)
    if same:
        return same
    rec = {"exception_id": f"exc-{sha(f'{finding_id_}:{fp}:{time.time()}')}", "finding_id": finding_id_, "rule_id": f["rule_id"], "decision": "accepted_for_this_version", "decision_by": decision_by.strip()[:80],
           "decision_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "reason": reason.strip()[:500], "applies_to_fingerprint": fp, "expires_when_inputs_change": True, "revoked_at": None}
    _save_ledger(pdir, aspect, recs + [rec])
    _rewrite_readiness(pdir, aspect)
    return rec


def revoke_exception(pdir: Path, aspect: str, exception_id: str) -> None:
    recs = ledger(pdir, aspect)
    hit = next((r for r in recs if r["exception_id"] == exception_id and not r.get("revoked_at")), None)
    if hit is None:
        raise ValidationError(f"no active exception {exception_id}")
    hit["revoked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")                   # the record stays: the decision and its withdrawal are both history
    _save_ledger(pdir, aspect, recs)
    _rewrite_readiness(pdir, aspect)


def _rewrite_readiness(pdir: Path, aspect: str) -> None:
    """Stage 12 only: the stored report is saved again with the decisions applied (nothing else is recomputed)."""
    rep = _read_report(pdir, aspect)
    if rep is None or rep["phase_status"] != "completed":
        return
    apply_exceptions(rep["findings"], ledger(pdir, aspect), rep["source_fingerprint"])
    rep["exceptions"] = ledger(pdir, aspect)
    restatus(rep["findings"], rep["stages"])
    rep["summary"].update(counts_of(rep["findings"]), stages_blocked=sum(1 for st in rep["stages"] if st["status"] in ("blocked", "skipped_due_to_dependency")))
    rep["readiness"] = readiness_of(rep["findings"], rep["stages"])
    rep["next_action"] = NEXT[rep["readiness"]]
    _write(pdir, aspect, rep)


# ---------- the gate (Stage 10 -> Stage 11) ----------
def blockers(pdir: Path, aspect: str, validate_if_needed: bool = False) -> list[str]:
    """Why the timeline must not be built from the motion output yet (empty = it may). The fingerprints are compared NOW, so a report made before an input changed never lets a build through.
    With `validate_if_needed` a missing or out-of-date report is made first (the validation is read-only and quick); a blocked or review verdict still stops."""
    from . import motion_branch
    if not motion_branch.required(pdir):
        return []
    rep = load(pdir, aspect)
    if (rep is None or rep["stale"] or rep["phase_status"] != "completed") and validate_if_needed:
        try:
            run(pdir, aspect)
        except Exception as e:
            return [f"Motion & Timeline Validation could not finish: {e}"]
        rep = load(pdir, aspect)
    if rep is None:
        return ["Motion & Timeline Validation has not run yet: run it from its page"]
    if rep["phase_status"] != "completed":
        return [f"Motion & Timeline Validation failed: {rep.get('error') or 'run it again'}"]
    if rep["stale"]:
        return ["Motion & Timeline Validation is out of date (an input changed): run it again"]
    if rep["readiness"] in READY:
        return []
    s = rep["summary"]
    why = {"blocked": f"{s.get('blockers', 0)} blocker(s), {s.get('errors', 0)} error(s)", "needs_review": f"{s.get('unresolved_review_items', 0)} warning(s) need a decision", "failed": "the validation did not finish"}
    first = (next((f for f in rep["findings"] if f["status"] == "unresolved" and f["severity"] in ("blocker", "error")), None)
             or next((f for f in rep["findings"] if f["status"] == "unresolved" and f["severity"] == "warning"), None))
    return [f"Motion & Timeline Validation is {rep['readiness'].replace('_', ' ')} ({why.get(rep['readiness'], '')})" + (f": {first['message']}" if first else "")]
