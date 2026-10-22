"""Dry run: the plan as it would be rendered (scenes, shots, highlights, matches, confidence, reasons, issues) WITHOUT rendering.
  python -m backend.plan_preview projects/demo [--write]      (--write saves plan_preview.json in the project folder)
Reads only files the pipeline already wrote; output is deterministic (no times, no absolute paths), so tests can compare it with a golden file."""
import json
import sys
from pathlib import Path

from . import config
from .contracts import EmphasisEvent, Reason, Shot, ValidationItem, locked_numbers
from .match_detail import detail_for
from .models import MatchReport, PromptsMap, ScenePlan
from .transcribe import load_transcript

VERSION = 1


def _words(pdir: Path) -> list:
    return [w for s in load_transcript(pdir).segments for w in s.words]


def _highlights(sc, words: list) -> list[EmphasisEvent]:
    """The plan's keywords as emphasis events. Timing is "word" only when the keyword time is within the tolerance of a spoken word start."""
    out = []
    for i, k in enumerate(sc.keywords):
        w = min(words, key=lambda x: abs(x.start - k.at)) if words else None
        off = (k.at - w.start) if w else None
        precise = off is not None and abs(off) <= config.HIGHLIGHT_TOLERANCE_SEC
        out.append(EmphasisEvent(
            id=f"scene_{sc.id:02d}_hl_{i + 1:02d}", scene=sc.id, start=round(k.at, 3), end=round(min(sc.end, k.at + config.HIGHLIGHT_DURATION_SEC[1]), 3),
            text=k.text, kind="keyword", timing="word" if precise else "estimated",
            reason=Reason(rule="plan_keyword", detail="no transcript words" if w is None else f"nearest spoken word starts {off:+.2f}s from the keyword time")))
    return out


def build(pdir: Path) -> dict:
    plan = ScenePlan.model_validate_json((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    prompts = PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8")).prompts
    rf = pdir / "match_report.json"
    report = MatchReport.model_validate_json(rf.read_text(encoding="utf-8")) if rf.exists() else None
    by_n = {m.n: m for m in report.matches} if report else {}
    cf = pdir / "composition.json"
    cams = {s["id"]: (s.get("camera") or {}).get("move") for s in json.loads(cf.read_text(encoding="utf-8"))["scenes"]} if cf.exists() else {}
    locked = locked_numbers(pdir, report.matches if report else None)
    words = _words(pdir)
    cue_info = None
    if config.improve("match_detail"):          # A2V_MATCH_DETAIL=1: link every prompt to the narration phrase it illustrates (backend/cues.py)
        from .cues import build as build_cues
        cue_info = build_cues(pdir)
    links = cue_info["links"] if cue_info else {}
    shot_plan = None
    if config.improve("shots"):                 # A2V_SHOTS=1: the real shot plan (backend/shots.py) instead of one shot per scene
        from .shots import plan as plan_shots
        sp_out = plan_shots(pdir)
        shot_plan = {"by_scene": {r["id"]: r["shots"] for r in sp_out["scenes"]}, "issues": sp_out["issues"]}
    scenes, issues = [], []
    for sc in plan.scenes:
        mine = [p for p in prompts if p.scene == sc.id]
        matches = [detail_for(p, by_n.get(p.n), locked, links.get(str(p.n))) for p in mine]
        shot = Shot(id=f"scene_{sc.id:02d}_shot_01", scene=sc.id, start=sc.start, end=sc.end, kind="whole_scene", slots=[p.slot for p in mine],
                    camera=cams.get(sc.id), locked=any(m.locked for m in matches),
                    reason=Reason(rule="one_shot_per_scene", detail=f"scene lasts {sc.end - sc.start:.1f}s (long-scene threshold {config.LONG_SCENE_SEC}s)"))
        hls = _highlights(sc, words)
        for m, p in zip(matches, mine):
            if m.status == "missing" and p.required:
                issues.append(ValidationItem(severity="warning", rule="missing_image", scene=sc.id, shot=shot.id, issue=f"prompt {p.n} has no image",
                                             action="upload an image for this prompt"))
            elif m.band == "low":
                issues.append(ValidationItem(severity="warning", rule="low_confidence", scene=sc.id, shot=shot.id,
                                             issue=f"prompt {p.n}: weak match ({m.reason.detail or 'low score or margin'})", action="check the image or choose another"))
        for h in hls:
            if h.timing == "estimated":
                issues.append(ValidationItem(severity="info", rule="highlight_timing", scene=sc.id, shot=shot.id,
                                             issue=f"'{h.text}' at {h.start}s is not on a spoken word start ({h.reason.detail})", action="snap the keyword to a word"))
        row = {"id": sc.id, "start": sc.start, "end": sc.end, "pattern": sc.pattern, "mode": sc.mode,
               "shots": [shot.model_dump()], "highlights": [h.model_dump() for h in hls], "matches": [m.model_dump() for m in matches]}
        if shot_plan:
            row["shots"] = shot_plan["by_scene"][sc.id]
        if cue_info:
            row["arrangement"] = cue_info["scenes"][str(sc.id)]["arrangement"]
            row["cues"] = [c for c in cue_info["cues"] if c["scene"] == sc.id]
        scenes.append(row)
    out = {"version": VERSION, "scenes": scenes, "issues": [i.model_dump() for i in issues],
           "summary": {"scenes": len(scenes), "shots": len(scenes), "highlights": sum(len(s["highlights"]) for s in scenes),
                       "matches": {b: sum(1 for s in scenes for m in s["matches"] if m["band"] == b) for b in ("high", "medium", "low", "none")}}}
    if shot_plan:
        out["issues"] += shot_plan["issues"]
        out["summary"]["shots"] = sum(len(v) for v in shot_plan["by_scene"].values())
    if config.improve("highlights"):        # A2V_HIGHLIGHTS=1: also show the emphasis events (backend/highlights.py) that fill would use
        from .highlights import build as build_emphasis
        out["emphasis"] = build_emphasis(pdir)
    return out


def dump(preview: dict) -> str:
    return json.dumps(preview, indent=1, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    out = build(pdir)
    if "--write" in sys.argv:
        (pdir / "plan_preview.json").write_text(dump(out), encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False), f"issues={len(out['issues'])}")
