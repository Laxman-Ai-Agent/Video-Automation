"""The gate between stages: a stage with an unresolved error or warning does not let the next stage start.

What counts, read from files the stages already write (nothing is estimated):
- a step of the stage's own report (motion_generation.json "stages", ...) whose status is failed / blocked / error  -> error, never acceptable;
- a step of that report whose status is warning                                                                  -> warning, blocks until it is fixed
  or a person accepts exactly these warnings (stage_warning_acceptances.json, bound to the hash of the warning list: a changed report needs a new decision).
Only a stage whose own rules classify its warnings (POLICY_VERDICTS) lets policy-permitted warnings through; for every other stage none is assumed. LLM step checks are an advisory second opinion and do not gate.
"""
from __future__ import annotations

import json
from pathlib import Path

STEP_REPORTS = {                                                                    # stage -> the report whose "stages" list the stage itself writes ({sfx} = the 9:16 suffix)
    "analyzer": "audio_analysis.json", "segmentation": "scene_segmentation.json", "planning": "visual_planning.json",
    "motion_plan": "motion_planning{sfx}.json", "motion_gen": "motion_generation{sfx}.json",
    "motion_validation": "motion_timeline_validation{sfx}.json", "timeline": "timeline_build_report{sfx}.json", "qc": "final_qc_report.json",
}
_ERROR_STATES = ("failed", "blocked", "error")


def report_file(pdir: Path, stage_id: str, aspect: str) -> Path | None:
    name = STEP_REPORTS.get(stage_id)
    return pdir / name.format(sfx="_9x16" if aspect == "9:16" else "") if name else None


def report_steps(pdir: Path, stage_id: str, aspect: str) -> tuple[list[dict], dict | None, Path | None]:
    """The steps the stage recorded in its report, the whole report and its file (empty when the stage keeps no step report)."""
    f = report_file(pdir, stage_id, aspect)
    if f is None or not f.exists():
        return [], None, None
    try:
        rep = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return [], None, f
    out = [{"n": s.get("n"), "name": s.get("name") or s.get("label"), "status": s.get("status"), "detail": s.get("detail"),
            "checks_passed": s.get("checks_passed"), "checks_total": s.get("checks_total")}
           for s in (rep.get("stages") or []) if isinstance(s, dict) and "status" in s]
    return out, rep, f


def step_issues(pdir: Path, stage_id: str, aspect: str) -> list[dict]:
    """The warning / error steps of the stage's report: {n, name, severity, message}."""
    out = []
    for s in report_steps(pdir, stage_id, aspect)[0]:
        state = (s.get("status") or "").lower()
        if state in _ERROR_STATES:
            out.append({"n": s["n"], "name": s["name"], "severity": "error", "message": s.get("detail") or f"step {state}"})
        elif state == "warning":
            out.append({"n": s["n"], "name": s["name"], "severity": "warning", "message": s.get("detail") or "step warning"})
    return out


# A stage whose own rules classify its warnings: the report field and the values that mean "only policy-permitted warnings remain" (still disclosed; errors always block).
# Timeline Build: every warning is blocks_build=false (timeline_build.OK). Motion Validation: `ready_with_warnings`; `needs_review` is NOT in the list.
POLICY_VERDICTS = {"timeline": ("status", ("completed_with_warnings",)), "motion_validation": ("readiness", ("ready_with_warnings",)),
                   "qc": ("status", ("passed", "passed_with_warnings"))}           # Final QC: only after its LLM decision approved the file and named every accepted warning


def llm_issue(pdir: Path, stage_id: str, aspect: str) -> dict | None:
    """The stage LLM review as an issue: None when the stage needs none or its review passed. Fail-closed: a missing, stale, blocked or `needs_review` review is an error."""
    from SYSTEM.policies import llm_review
    if not llm_review.review_required(stage_id):
        return None
    passed, reason, rev = llm_review.is_stage_review_passed(pdir, stage_id, aspect)
    if passed:
        return None
    why = (rev or {}).get("summary") or ""
    return {"n": None, "name": "LLM review", "severity": "error", "message": f"the stage LLM review did not pass ({reason})" + (f": {why[:200]}" if why else "")}


def unresolved(pdir: Path, stage_id: str, aspect: str, ran: bool = True) -> list[dict]:
    """The issues of a stage that still block the next one: every error, the warnings unless the stage's own rules permit them, and a stage LLM review that did not pass (`ran=False`: the stage never ran, so there is no review to wait for)."""
    issues = step_issues(pdir, stage_id, aspect)
    warnings = [i for i in issues if i["severity"] == "warning"]
    if warnings and len(warnings) == len(issues) and stage_id in POLICY_VERDICTS:
        field, ok = POLICY_VERDICTS[stage_id]
        if (report_steps(pdir, stage_id, aspect)[1] or {}).get(field) in ok:
            issues = []
    return issues + ([i] if ran and (i := llm_issue(pdir, stage_id, aspect)) else [])


def describe(issues: list[dict]) -> str:
    """One line for a blocker message: how many and the first one."""
    if not issues:
        return ""
    errors = sum(1 for i in issues if i["severity"] == "error")
    return f"{len(issues)} unresolved ({errors} error(s), {len(issues) - errors} warning(s)); first: {issues[0]['name']}: {issues[0]['message'][:140]}"
