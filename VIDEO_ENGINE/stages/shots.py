"""Shot plan: which pictures of a scene appear one after another, and where the changes fall (A2V_SHOTS=1 applies it to the composition).
  python -m backend.shots projects/demo
A scene is split into shots only when it is long (>= LONG_SCENE_SEC), has several usable pictures that belong to DIFFERENT narration phrases
(backend/cues.py arrangement "timed"), and every part stays >= MIN_SHOT_SEC. A boundary sits on a real pause/cut near the phrase, not on a timer.
Otherwise the scene stays one shot: several pictures shown together (combined layout), or one picture with a subtle move (never invented content).
`camera` of a shot is a SIMULATED move on one picture; only kind="shot_change" is a real change of picture."""
import json
import sys
from pathlib import Path

from . import config, cues as cues_mod
from .assets import work_dir
from .contracts import Reason, Shot, ValidationItem, locked_numbers
from .models import MatchReport, PromptsMap, ScenePlan
from .transcribe import load_transcript

IMAGE_ROLES = ("main", "supporting", "background")     # icons and cut-out objects are overlays, never a shot of their own
EPS = 0.02


def _pauses(pdir: Path) -> tuple[list[tuple[float, str]], list[float]]:
    """Real pause moments (cut points with a silence or a sentence end; the first word after a pause >= 0.25 s) and every word start."""
    pauses: list[tuple[float, str]] = []
    cf = pdir / "cuts.json"
    if cf.exists():
        pauses += [(c["t"], f"cut ({c['reason']})") for c in json.loads(cf.read_text(encoding="utf-8"))["cuts"]
                   if c.get("silence", 0) >= 0.2 or c["reason"] in ("sentence_end", "segment_end")]
    try:
        words = [w for s in load_transcript(pdir).segments for w in s.words]
    except FileNotFoundError:
        words = []
    pauses += [(round(b.start, 3), "word after a pause") for a, b in zip(words, words[1:]) if b.start - a.end >= 0.25]
    return sorted(pauses), [w.start for w in words]


def _snap(target: float, lo: float, hi: float, pauses, starts) -> tuple[float, str]:
    near = [(abs(t - target), t, why) for t, why in pauses if lo < t < hi and abs(t - target) <= config.SHOT_SNAP_SEC]
    if near:
        _, t, why = min(near)
        return round(t, 3), why
    near = [(abs(t - target), t) for t in starts if lo < t < hi and abs(t - target) <= config.SHOT_SNAP_SEC]
    if near:
        return round(min(near)[1], 3), "word start"
    return round(target, 3), "estimated (no pause or word nearby)"


def _transition(k: int, prev_len: float, cur_len: float) -> tuple[str, float]:
    return config.SHOT_TRANSITIONS[(k - 1) % len(config.SHOT_TRANSITIONS)], round(min(config.SHOT_TRANSITION_SEC, config.TRANSITION_MAX_SHARE * min(prev_len, cur_len)), 2)


def plan(pdir: Path) -> dict:
    sp = ScenePlan.model_validate_json((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    prompts = PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8")).prompts
    rf, cf = pdir / "match_report.json", pdir / "composition.json"
    report = MatchReport.model_validate_json(rf.read_text(encoding="utf-8")) if rf.exists() else None
    by_n = {m.n: m for m in report.matches} if report else {}
    cams = {s["id"]: (s.get("camera") or {}).get("move") for s in json.loads(cf.read_text(encoding="utf-8"))["scenes"]} if cf.exists() else {}
    cue = cues_mod.build(pdir)
    cue_by_id = {c["id"]: c for c in cue["cues"]}
    pauses, starts = _pauses(pdir)
    locked = locked_numbers(pdir, report.matches if report else None)
    scenes, issues = [], []

    for sc in sp.scenes:
        sid, dur = sc.id, sc.end - sc.start
        mine = [p for p in prompts if p.scene == sid and p.role in IMAGE_ROLES]
        ready = [p for p in mine if report is None or (by_n.get(p.n) and by_n[p.n].file and by_n[p.n].status == "ok")]
        for p in mine:
            if p not in ready:
                issues.append(ValidationItem(severity="warning", rule="shot_asset_missing", scene=sid, issue=f"prompt {p.n} has no accepted image, so it gets no shot",
                                             action="upload or confirm the image for this prompt"))
        shots: list[Shot] = []
        why = None
        if dur < config.LONG_SCENE_SEC:
            why = ("short_scene", f"scene lasts {dur:.1f}s, below {config.LONG_SCENE_SEC}s: one shot")
        elif len(ready) < 2:
            why = ("one_asset_fallback" if ready else "no_asset", f"{len(ready)} usable picture(s) in a {dur:.1f}s scene: subtle camera move or hold, nothing invented")
        elif cue["scenes"][str(sid)]["arrangement"] != "timed":
            why = ("combined_layout", f"narration arrangement is '{cue['scenes'][str(sid)]['arrangement']}': the pictures stay together")
        elif any(not cue["links"].get(str(p.n)) for p in ready):
            why = ("unlinked_prompt", "a picture has no narration phrase, so no safe moment for its shot")
        if why is None:
            order = sorted(ready, key=lambda p: cue_by_id[cue["links"][str(p.n)]]["start"])
            bounds: list[tuple[float, str, object]] = []
            skipped = []
            last = sc.start
            for p in order[1:]:
                t, src = _snap(cue_by_id[cue["links"][str(p.n)]]["start"], last + config.MIN_SHOT_SEC - EPS, sc.end - config.MIN_SHOT_SEC + EPS, pauses, starts)
                if t - last < config.MIN_SHOT_SEC - EPS or sc.end - t < config.MIN_SHOT_SEC - EPS:
                    skipped.append(p.n)
                    continue
                bounds.append((t, src, p))
                last = t
            if skipped:
                issues.append(ValidationItem(severity="info", rule="shot_too_short", scene=sid, issue=f"prompt(s) {skipped} would need a shot under {config.MIN_SHOT_SEC}s",
                                             action="they stay out of the sequence; shorten the plan or merge phrases if they matter"))
            if bounds:
                firsts = [order[0]] + [b[2] for b in bounds]
                edges = [sc.start] + [b[0] for b in bounds] + [sc.end]
                for k, p in enumerate(firsts):
                    tr, td = _transition(k, edges[k] - edges[k - 1], edges[k + 1] - edges[k]) if k else (None, 0.0)
                    shots.append(Shot(id=f"scene_{sid:02d}_shot_{k + 1:02d}", scene=sid, start=round(edges[k], 3), end=round(edges[k + 1], 3), kind="shot_change",
                                      slots=[p.slot], camera=config.SHOT_CAMERAS[k % len(config.SHOT_CAMERAS)], locked=p.n in locked, transition=tr, transition_dur=td,
                                      reason=Reason(rule="narration_cue", source_cue=cue["links"][str(p.n)],
                                                    detail="scene start" if k == 0 else f"change at {edges[k]:.2f}s: {bounds[k - 1][1]}")))
            else:
                why = ("shots_too_short", f"no part of the scene can last {config.MIN_SHOT_SEC}s or more")
        if not shots:
            shots = [Shot(id=f"scene_{sid:02d}_shot_01", scene=sid, start=sc.start, end=sc.end, kind="whole_scene", slots=[p.slot for p in ready], camera=cams.get(sid),
                          locked=any(p.n in locked for p in ready), reason=Reason(rule=why[0], detail=why[1]))]
        issues += _crop_issues(pdir, report, by_n, shots, prompts)
        scenes.append({"id": sid, "start": sc.start, "end": sc.end, "shots": [s.model_dump() for s in shots]})
    return {"version": 1, "scenes": scenes, "issues": [i.model_dump() for i in issues]}


def _crop_issues(pdir: Path, report, by_n, shots: list[Shot], prompts) -> list[ValidationItem]:
    """A full-frame shot must not hide most of its picture (same geometry as the renderer: object-fit cover). Needs the accepted image on disk."""
    if report is None:
        return []
    from PIL import Image
    from .prerender_checks import CROP_WARN, box_px, visible_share
    out = []
    slot_n = {p.slot: p.n for p in prompts}
    for sh in shots:
        if sh.kind != "shot_change":
            continue
        for slot in sh.slots:
            m = by_n.get(slot_n.get(slot))
            f = work_dir(pdir) / (Path(m.file).stem + ".png") if m and m.file else None
            if not f or not f.exists():
                continue
            with Image.open(f) as im:
                size = im.size
            for aspect, frame, portrait in (("16:9", (1920, 1080), False), ("9:16", (1080, 1920), True)):
                share = visible_share(size, box_px("full", frame, portrait))
                if share < CROP_WARN:
                    out.append(ValidationItem(severity="warning", rule="shot_crop", scene=sh.scene, shot=sh.id,
                                              issue=f"{aspect}: only {share:.0%} of the picture for {slot} stays visible as a full-frame shot",
                                              action="use the crop editor to move the focus point, or choose a picture with a closer shape"))
    return out


def validate(scene_start: float, scene_end: float, shots: list[dict]) -> list[ValidationItem]:
    """Pure check of one scene's shots: they must cover the scene exactly (no blank gap, no overlap), last long enough, and fades must fit inside the shots."""
    out: list[ValidationItem] = []
    sid = shots[0]["scene"] if shots else None
    if not shots:
        return [ValidationItem(severity="error", rule="shots_missing", scene=sid, issue="the scene has no shot", action="rebuild the shot plan")]
    if abs(shots[0]["start"] - scene_start) > EPS:
        out.append(ValidationItem(severity="error", rule="shot_gap", scene=sid, shot=shots[0]["id"], issue=f"first shot starts at {shots[0]['start']}s, the scene at {scene_start}s", action="start the first shot with the scene"))
    if abs(shots[-1]["end"] - scene_end) > EPS:
        out.append(ValidationItem(severity="error", rule="shot_gap", scene=sid, shot=shots[-1]["id"], issue=f"last shot ends at {shots[-1]['end']}s, the scene at {scene_end}s", action="extend the last shot to the scene end"))
    for a, b in zip(shots, shots[1:]):
        if abs(a["end"] - b["start"]) > EPS:
            out.append(ValidationItem(severity="error", rule="shot_gap" if b["start"] > a["end"] else "shot_overlap", scene=sid, shot=b["id"],
                                      issue=f"{a['id']} ends at {a['end']}s but {b['id']} starts at {b['start']}s", action="make the shots follow each other exactly"))
    for i, s in enumerate(shots):
        if len(shots) > 1 and s["end"] - s["start"] < config.MIN_SHOT_SEC - EPS:
            out.append(ValidationItem(severity="warning", rule="shot_too_short", scene=sid, shot=s["id"], issue=f"shot lasts {s['end'] - s['start']:.2f}s (minimum {config.MIN_SHOT_SEC}s)", action="merge it with a neighbour"))
        if s.get("transition") and s["transition_dur"] > config.TRANSITION_MAX_SHARE * (s["end"] - s["start"]) + EPS:
            out.append(ValidationItem(severity="warning", rule="shot_transition", scene=sid, shot=s["id"], issue="the transition takes too large a share of the shot", action="shorten the transition"))
        if i and s.get("transition") and s["transition"] == shots[i - 1].get("transition"):
            out.append(ValidationItem(severity="info", rule="shot_transition_repeat", scene=sid, shot=s["id"], issue="same transition as the previous shot", action="vary the transition"))
    return out


def apply_shots(pdir: Path, comp: dict) -> int:
    """Rewrite the image layers of 'timed' scenes into full-frame pictures that follow each other. Returns the number of scenes changed.
    The scene camera becomes static: every shot carries its own simulated move (ken-burns or hold) so zooms never stack."""
    changed = 0
    for row in plan(pdir)["scenes"]:
        shots = row["shots"]
        if shots[0]["kind"] != "shot_change":
            continue
        sc = next((s for s in comp["scenes"] if s["id"] == row["id"]), None)
        if sc is None:
            continue
        by_slot = {l.get("slot"): l for l in sc["layers"] if l.get("type") == "image"}
        if any(slot not in by_slot or not by_slot[slot].get("file") for sh in shots for slot in sh["slots"]):
            continue                                            # a picture is not in the composition (yet): keep the original layout
        for k, sh in enumerate(shots):
            for slot in sh["slots"]:
                l = by_slot[slot]
                l["pos"], l["z"] = "full", 1 + k
                l.pop("parallax", None)
                l.pop("enter", None), l.pop("exit", None)
                l["anim"] = sh["camera"] if sh["camera"] == "ken-burns" else "hold"
                if sh["transition"]:
                    l["enter"] = {"at": sh["start"], "anim": sh["transition"], "dur": sh["transition_dur"]}
                if k + 1 < len(shots):                          # the next picture covers this one before it is switched off: no blank frame in between
                    nxt = shots[k + 1]
                    l["exit"] = {"at": round(nxt["start"] + nxt["transition_dur"], 3), "anim": "fade", "dur": 0.1}
        cam = sc.setdefault("camera", {})
        cam.update({"move": "static", "from": 1, "to": 1})
        sc["shots"] = shots
        changed += 1
    return changed


if __name__ == "__main__":
    out = plan(config.project_dir(sys.argv[1]))
    for s in out["scenes"]:
        print(f"scene {s['id']:>2} {s['start']:>6}-{s['end']:<6} " + " | ".join(f"{x['kind'][:5]} {x['start']}-{x['end']} {x['slots']} [{x['reason']['rule']}]" for x in s["shots"]))
    print(f"issues={len(out['issues'])}")
