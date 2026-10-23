"""Motion Planning: HOW and WHEN the elements of the Visual Plan move (roadmap improvements/Motion_Planning_Complete_Roadmap). It extends the existing `motion-plan` step
(VIDEO_ENGINE/remotion/scripts/build_composition.ts --plan-only writes motion_plan.json: the presets the motion library chose for every scene) with motion_planning.json, the checked plan:
per scene the timing (seconds + frames), the motion intent, every Visual Plan element resolved to a real registry id or an explicit fallback, the action sequence with its
dependencies, the continuity with the neighbours, the transition, and the validation notes. Nothing here renders and nothing is invented: only ids of the installed registry
(npx tsx scripts/motion_list.ts) are used, times come from the plan, and no code is written. There is no Claude call: the choice is the deterministic selector of the motion
library, so the same inputs give the same plan.

The 13 logical stages (steps of one module, not 13 agents; the page shows them as boxes):
  1 Motion Plan Reader             inputs, scene ids, intervals, mode, fps, timing source
  2 Element Resolver               every Visual Plan element -> something the library draws, or a recorded fallback
  3 Preset Registry Lookup         every preset / exit / emphasis / transition id exists in the real registry
  4 Effect Reuse Engine            only existing presets, no repetition in neighbouring scenes, variety
  5 Animation Builder              the action sequence of every scene (establish -> reveal -> enter -> emphasis -> exit) with dependencies
  6 Animation Engine Adapter       the parameters the engine accepts (Telugu-safe presets, pace, intensity)
  7 Composition & Transition Builder  how a scene leaves and the next one enters (known type, no repeat, fits between the scenes)
  8 Timing & Audio Sync            seconds and frames on the audio timeline, inside the scene, keyword times
  9 Layout Validator               safe area, overlap with the planned text, reading time, text count
  10 Code & Plan Validator         the plan matches its contract, no code in it, unique ids, no dependency cycle, mode rules
  11 Motion Test Runner            the motion library's own checks (scripts/motion_checks.ts), cached by the library source
  12 Error Repair Handler          only mechanical repairs (clamp a time, replace an unknown id), each one recorded
  13 Remotion Output Adapter       the layers Motion Generation will build, and whether the composition already matches
Time rule: seconds everywhere; frame = floor(seconds x fps + 0.5), the end frame is exclusive and always after the start frame."""
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from SYSTEM.core import media_kinds as mk

from . import config, store, visual_planning

SCHEMA = "1.0"
VERSION = 2                                    # bump when the rules or the structure change (part of the fingerprint); 2: drawn elements (diagram), approximate status, drawn-text rules
FPS = 30
EPS = 0.04                                     # seconds: one frame of tolerance
FIXES = "motion_fixes.json"                    # written by solve(): what "Solve warnings" changed (read by build_composition.ts --fixes and by build())
MIN_DUR = 0.25                                # no entrance, exit or transition is shorter (the motion library's own floor)
TEXT_STYLES = ("headline", "caption", "label", "quote")
TELUGU = re.compile(r"[ఀ-౿]")
CODE_LIKE = re.compile(r"=>|\bfunction\s*\(|\bimport\s+[\w{*]|\brequire\s*\(|<script|\beval\s*\(|\bexec\s*\(|\bdef\s+\w+\s*\(|\bclass\s+\w+\s*[:{(]", re.I)
STAGES = (
    ("Motion Plan Reader", "Reading the Visual Plan and the scene timing"),
    ("Element Resolver", "Matching every element to something the library draws"),
    ("Preset Registry Lookup", "Checking every preset against the real registry"),
    ("Effect Reuse Engine", "Reusing existing presets without repeating them"),
    ("Animation Builder", "Building the action sequence of every scene"),
    ("Animation Engine Adapter", "Checking the parameters the engine accepts"),
    ("Composition & Transition Builder", "Planning how the scenes enter and leave"),
    ("Timing & Audio Sync", "Fixing seconds and frames on the audio timeline"),
    ("Layout Validator", "Checking safe areas, overlaps and reading time"),
    ("Code & Plan Validator", "Checking the plan against its contract"),
    ("Motion Test Runner", "Running the motion library's own checks"),
    ("Error Repair Handler", "Repairing only what is safe to repair"),
    ("Remotion Output Adapter", "Preparing the layers Remotion will build"),
)
N = len(STAGES)
PHASE_RANK = {"establish": 0, "reveal": 1, "enter": 2, "emphasis": 3, "exit": 4}


class MotionError(Exception):
    """The plan cannot be made (an input is missing or unreadable): the message says what to do."""


# ---------- the contract (stage 10 validates the finished plan against it) ----------
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Action(Strict):
    action_id: str
    target: str
    phase: Literal["establish", "reveal", "enter", "emphasis", "exit"]
    kind: Literal["text", "graphic", "icon"]
    preset: str | None = None
    registry: dict | None = None
    start: float
    end: float
    start_frame: int
    end_frame: int
    depends_on: list[str] = []
    timing_source: str
    reason: str
    params: dict = {}


class El(Strict):
    element_id: str
    source_element_id: str | None
    type: str
    semantic_role: str
    required: bool
    registry_id: str | None
    registry_kind: str | None
    status: Literal["resolved", "approximate", "fallback", "unresolved"]
    fallback: dict | None = None
    note: str | None = None


class SceneM(Strict):
    scene_id: str
    plan_scene_id: int
    timing: dict
    motion_intent: dict
    elements: list[El]
    sequence: list[Action]
    transition_out: dict | None
    continuity: dict
    validation_notes: list[dict]


class PlanM(Strict):
    schema_version: str
    version: int
    source: str
    project: dict
    timing_policy: dict
    visual_plan: dict
    style_guide: dict
    source_fingerprint: str
    scenes: list[SceneM]
    reuse: dict
    output: dict
    stages: list[dict]
    validation: dict
    repairs: list[dict]
    tests: dict
    needs_review: bool
    timings_seconds: dict
    warning_fix: dict | None = None


class Run:
    """The findings of one build: each rule counts what it checked, a failed rule records a finding (an error blocks the plan, a warning does not)."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.counts: dict[str, list[int]] = {}
        self.by_stage: dict[int, list[int]] = {}
        self.accepted: set[str] = set()                                       # scenes whose recorded fallback the user accepted with "Solve warnings"

    def rule(self, name: str, stage: int, scene: str | None, bad: bool, severity: str, code: str, message: str) -> None:
        c = self.counts.setdefault(name, [0, 0])
        c[1] += 1
        s = self.by_stage.setdefault(stage, [0, 0])
        s[1] += 1
        s[0] += not bad
        if bad:
            self.items.append({"stage": stage, "severity": severity, "code": code, "scene": scene, "message": message})
        else:
            c[0] += 1

    def note(self, stage: int, severity: str, code: str, scene: str | None, message: str) -> None:
        self.items.append({"stage": stage, "severity": severity, "code": code, "scene": scene, "message": message})

    def of(self, severity: str) -> list[dict]:
        return [i for i in self.items if i["severity"] == severity]


# ---------- registry (the real one, read from the motion library) ----------
_reg: dict = {}
_checks_mem: dict = {}


def registry() -> dict:
    """The installed presets by kind: {text, exit, emphasis, graphic, mask: {id: entry}}. Read from `npx tsx scripts/motion_list.ts`, cached until the library source changes."""
    from . import pipeline
    from . import resource_library
    key = pipeline._remotion_src_digest() + resource_library.registry_digest()          # the primitive list also holds the verified icons of the Resource Library
    if _reg.get("key") != key:
        r = subprocess.run("npx tsx scripts/motion_list.ts", cwd=pipeline._REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        line = next((x for x in r.stdout.splitlines() if x.startswith("{")), "")
        if r.returncode or not line:
            raise MotionError("the motion registry could not be read: " + (r.stderr or r.stdout)[-300:])
        raw = json.loads(line)
        _reg.update(key=key, data={"text": {x["id"]: x for x in raw["text"]}, "exit": {x["id"]: x for x in raw["exits"]}, "emphasis": {x["id"]: x for x in raw["emphasis"]},
                                   "graphic": {x["id"]: x for x in raw["graphics"]}, "mask": {x["id"]: x for x in raw["masks"]},
                                   "primitive": {x["id"]: x for x in raw.get("primitives", [])}})
    return _reg["data"]


def transitions() -> set[str]:
    """The scene transitions of the library (the same list transition_audit.py reads), straight from the Remotion source."""
    from . import pipeline
    text = (pipeline._REMOTION / "src" / "transitions" / "index.ts").read_text(encoding="utf-8")
    m = re.search(r"TRANSITIONS = \[(.*?)\] as const", text, re.S)
    if not m:
        raise MotionError("the transition list was not found in VIDEO_ENGINE/remotion/src/transitions/index.ts")
    return set(re.findall(r'"([a-z-]+)"', m.group(1)))


def _names(aspect: str) -> tuple[str, str]:
    sfx = "_9x16" if aspect == "9:16" else ""
    return f"motion_plan{sfx}.json", f"motion_planning{sfx}.json"


def reading_end(t: dict, scene_end: float) -> float:
    """The second the text starts to leave (its exit starts), not the end of the scene: what is read has to be on screen before that."""
    return t["until"] if t.get("until") is not None else scene_end - (t.get("exit_s") or 0)


def reading_need(t: dict) -> float:
    return (t.get("enter_s") or 0.5) + 0.8 + 0.3 * max(1, len(t["text"].split()))


def fr(seconds: float, fps: int = FPS) -> int:
    """The ONE seconds-to-frames rule: floor(seconds x fps + 0.5) (the same rounding as Math.round for times on the timeline)."""
    return int(seconds * fps + 0.5)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fingerprint(pdir: Path, aspect: str) -> str:
    """What this plan was made from: the motion plan the selector wrote, the Visual Plan it follows, the motion library source and these rules."""
    from . import pipeline
    mp = _names(aspect)[0]
    h = hashlib.sha256()
    for part in ((pdir / mp).read_bytes() if (pdir / mp).exists() else b"", ((_read(pdir / "visual_planning.json") or {}).get("source_fingerprint") or "").encode(),
                 pipeline._remotion_src_digest().encode(), f"{SCHEMA}:{VERSION}".encode()):
        h.update(part + b"\0")
    return h.hexdigest()[:16]


# ---------- the checks of the motion library itself (stage 11) ----------
def run_checks(pdir: Path) -> dict:
    """The motion library's own pure checks (scripts/motion_checks.ts). Cached by the library source: unchanged source = the recorded result, no second run."""
    from . import pipeline
    key = pipeline._remotion_src_digest()
    cache = pdir / ".motion_checks.json"
    old = _read(cache)
    if _checks_mem.get("key") == key:
        return {**_checks_mem["result"], "cached": True}
    if old and old.get("key") == key:
        _checks_mem.update(key=key, result=old["result"])
        return {**old["result"], "cached": True}
    try:
        r = subprocess.run("npx tsx scripts/motion_checks.ts", cwd=pipeline._REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                           env={**os.environ, "A2V_MOTION": "1"})
        line = next((x for x in reversed(r.stdout.splitlines()) if x.startswith("{")), "")
        res = json.loads(line) if line else {"ok": None, "error": (r.stderr or r.stdout)[-200:]}
    except (subprocess.TimeoutExpired, ValueError, OSError) as e:
        res = {"ok": None, "error": f"the checks could not run: {e}"}
    result = {"ok": res.get("ok"), "count": res.get("count"), "failed": res.get("failed", []), "error": res.get("error"), "cached": False}
    if result["ok"] is not None:
        _checks_mem.update(key=key, result=result)
        cache.write_text(json.dumps({"key": key, "result": result}), encoding="utf-8")
    return result


# ---------- the build ----------
def _scene_entries(mp: dict, vp: dict | None, sp: dict, aspect: str, fps: int, run: Run, assets: dict[int, dict[str, dict]]) -> list[dict]:
    """Stages 2 and 5 for every scene: the elements, the actions, the intent, the continuity with the previous scene. The selector's own data (`_m`, `_vps`) stays on the entry until the rules ran.
    `assets` = the real media Asset Collection kept, by scene id and element id."""
    from . import motion_scenes as sc
    vp_scenes = {s["plan_scene_id"]: s for s in (vp or {}).get("scenes", [])}
    sp_scenes = {s["id"]: s for s in sp.get("scenes", [])}
    out: list[dict] = []
    history: list[list[str]] = []
    for k, m in enumerate(mp["scenes"]):
        sid = visual_planning._scene_id(m["id"])
        vps = vp_scenes.get(m["id"])
        els, text_ids, gfx_ids, icon_ids = sc.resolve(vps, m, sid, run, assets.get(m["id"]))
        acts = sc.actions(m, sid, fps, text_ids, gfx_ids, icon_ids, [kw["at"] for kw in (sp_scenes.get(m["id"], {}).get("keywords") or [])])
        why, src, narr = m.get("why") or {}, (vps or {}).get("source_mapping") or {}, (vps or {}).get("narration") or {}
        obj, concept = (vps or {}).get("scene_objective") or {}, (vps or {}).get("visual_concept") or {}
        main = m["texts"][0]["preset"] if m["texts"] else None
        placed = [g["preset"] for g in m["graphics"] if not g.get("atmosphere")]
        prev = out[-1] if out else None
        repeats = ([main] if main and prev and main == prev["continuity"]["main_text_preset"] else []) + ([p for p in placed if prev and p in prev["continuity"]["placed_graphics"]])
        out.append({
            "scene_id": sid, "plan_scene_id": m["id"],
            "timing": {"start": m["start"], "end": m["end"], "start_frame": fr(m["start"], fps), "end_frame": fr(m["end"], fps), "source": narr.get("timestamp_source") or "scene_plan",
                       "canonical_start": src.get("plan_start", m["start"]), "canonical_end": src.get("plan_end", m["end"]), "gap_after_seconds": src.get("gap_after_seconds")},
            "motion_intent": {"purpose": obj.get("narrative_role"), "attention_goal": concept.get("primary_focus"), "takeaway": obj.get("audience_takeaway"),
                              "intensity": sc.intensity(float(why.get("importance", 0.5))), "hints": why.get("intents", []), "mood": why.get("mood", "")},
            "elements": els, "sequence": acts, "transition_out": m.get("transition"),
            "continuity": {"previous_scene_id": prev["scene_id"] if prev else None,
                           "next_scene_id": visual_planning._scene_id(mp["scenes"][k + 1]["id"]) if k + 1 < len(mp["scenes"]) else None,
                           "motifs": ((vps or {}).get("continuity") or {}).get("motifs", []), "main_text_preset": main, "placed_graphics": placed,
                           "recent_presets": sorted({p for h in history[-3:] for p in h}), "repeats": repeats},
            "validation_notes": [], "_m": m, "_vps": vps,
        })
        history.append([x for x in [main, *placed, *[t["preset"] for t in m["texts"][1:]]] if x])
    return out


def _rules(scenes: list[dict], reg: dict, aspect: str, images: bool, run: Run) -> None:
    """Stages 3, 4, 5, 6, 7, 8, 9 and 10 (mode): the checks of every scene against the registry, the scene interval, the neighbours and the safe area."""
    from . import motion_scenes as sc
    trans, prev_t = transitions(), None
    allp = {"text": reg["text"], "exit": reg["exit"], "emphasis": reg["emphasis"], "graphic": reg["graphic"], "primitive": reg.get("primitive", {})}
    for k, s in enumerate(scenes):
        sid, m, vps = s["scene_id"], s.pop("_m"), s.pop("_vps")
        t0, t1 = s["timing"]["start"], s["timing"]["end"]
        for a in s["sequence"]:
            kind = "primitive" if str(a["preset"] or "").startswith(("shape:", "icon:", "resource:")) else "graphic" if a["kind"] == "graphic" else "emphasis" if a["phase"] == "emphasis" else "exit" if a["phase"] == "exit" else "text"
            if a["preset"]:
                ok = a["preset"] in allp[kind]
                run_rule = run.rule
                run_rule("registry_id", 3, sid, not ok, "error", "unknown_registry_id", f"{sid}: '{a['preset']}' is not a {kind} preset of the installed registry")
                if ok:
                    e = allp[kind][a["preset"]]
                    a["registry"] = {"kind": kind, "id": a["preset"], "label": e.get("label"), "category": e.get("category")}
            run.rule("action_in_scene", 8, sid, a["start"] < t0 - EPS or a["end"] > t1 + EPS, "error", "invalid_timing", f"{sid}: {a['action_id']} runs {a['start']:g}-{a['end']:g} s, outside the scene {t0:g}-{t1:g} s")
            run.rule("frames_valid", 8, sid, a["end_frame"] <= a["start_frame"], "error", "invalid_timing", f"{sid}: {a['action_id']} has frames {a['start_frame']}-{a['end_frame']}")
        for t in m["texts"]:
            p = reg["text"].get(t["preset"])
            run.rule("telugu_safe_preset", 6, sid, bool(p) and bool(TELUGU.search(t["text"])) and not p.get("indic"), "error", "unsupported_parameter", f"{sid}: the preset '{t['preset']}' cannot draw Telugu text ('{t['text']}')")
            run.rule("text_style", 6, sid, t.get("style") not in TEXT_STYLES, "error", "unsupported_parameter", f"{sid}: the text style '{t.get('style')}' is not one of {', '.join(TEXT_STYLES)}")
            if t.get("k") is not None:
                run.rule("intensity_range", 6, sid, not 0.3 <= t["k"] <= 2.0, "warning", "unsupported_parameter", f"{sid}: the intensity {t['k']} of '{t['text']}' is outside 0.3-2.0")
            if t.get("enter_s") is not None:
                run.rule("min_duration", 6, sid, t["enter_s"] < MIN_DUR - 1e-6, "warning", "unsupported_parameter", f"{sid}: the entrance of '{t['text']}' lasts {t['enter_s']} s (shortest {MIN_DUR} s)")
            at, until = (t["at"] if t.get("at") is not None else t0), reading_end(t, t1)
            need = reading_need(t)
            run.rule("text_readable", 9, sid, until - at < need, "warning", "text_too_short", f"{sid}: '{t['text']}' is on screen {until - at:.1f} s before it starts to leave but needs about {need:.1f} s to be read")
            if t.get("emphasis_at"):
                run.rule("emphasis_inside_text", 8, sid, not at - EPS <= t["emphasis_at"][0] <= until + EPS, "error", "invalid_timing", f"{sid}: the emphasis of '{t['text']}' at {t['emphasis_at'][0]:g} s is outside its visible time")
        run.rule("text_count", 9, sid, len(m["texts"]) > 2, "warning", "layout_density", f"{sid}: {len(m['texts'])} animated texts (at most 2 keep a scene readable)")
        for g in m["graphics"]:
            if g["preset"] not in reg["graphic"]:
                continue
            run.rule("min_duration", 6, sid, g.get("exit_s") is not None and g["exit_s"] < MIN_DUR - 1e-6, "warning", "unsupported_parameter", f"{sid}: the exit of '{g['preset']}' lasts {g.get('exit_s')} s (shortest {MIN_DUR} s)")
            run.rule("speed_range", 6, sid, not 0.5 <= (g.get("speed") or 1) <= 2, "warning", "unsupported_parameter", f"{sid}: the pace {g.get('speed')} of '{g['preset']}' is outside 0.5-2")
            b = g.get("box")
            if b and not g.get("atmosphere"):
                mgn = config.SAFE_AREA["margin"]
                lim = 1 - config.SAFE_AREA["portrait_ui_bottom"] if aspect == "9:16" else 1 - mgn
                run.rule("graphic_in_safe_area", 9, sid, b[0] < mgn - 0.03 or b[1] < mgn - 0.03 or b[0] + b[2] > 1 - mgn + 0.03 or b[1] + b[3] > lim + 0.03, "warning", "layout_out_of_bounds",
                         f"{sid}: the box of '{g['preset']}' reaches outside the safe area")
                cat = reg["graphic"][g["preset"]].get("category")
                for t in m["texts"]:                                           # where the renderer really draws the text (the check above is against the Visual Plan's planned area); a frame encloses its text on purpose
                    db = t.get("drawn_box")
                    if db and b[2] * b[3] < 0.5 and cat != "frame":
                        ov = visual_planning._overlap((b[0], b[1], b[0] + b[2], b[1] + b[3]), tuple(db))
                        small = min(b[2] * b[3], (db[2] - db[0]) * (db[3] - db[1]))
                        run.rule("graphic_clear_of_drawn_text", 9, sid, small > 0 and ov / small > 0.25, "warning", "layout_overlap", f"{sid}: '{g['preset']}' lies on the text '{t['text']}' where the renderer draws it")
                if vps and b[2] * b[3] < 0.5:                                  # a frame or a bleed fills the screen on purpose; a placed graphic must not sit on the planned text
                    for e in vps["elements"]:
                        rb = visual_planning.region_box(e["placement"]["region"], aspect) if mk.is_text(e["type"]) else None
                        if rb:
                            ov = visual_planning._overlap((b[0], b[1], b[0] + b[2], b[1] + b[3]), rb)
                            small = min(b[2] * b[3], (rb[2] - rb[0]) * (rb[3] - rb[1]))
                            run.rule("graphic_clear_of_text", 9, sid, small > 0 and ov / small > 0.25, "warning", "layout_overlap", f"{sid}: '{g['preset']}' overlaps the area planned for the text '{e.get('content')}'")
        dg = m.get("diagram") or {}
        mgn2 = config.SAFE_AREA["margin"]
        lim2 = 1 - config.SAFE_AREA["portrait_ui_bottom"] if aspect == "9:16" else 1 - mgn2
        ids_vp = {e["element_id"] for e in (vps or {}).get("elements", [])}
        for d in dg.get("placed", []):
            b = d["box"]
            run.rule("diagram_element_exists", 2, sid, bool(vps) and d["element_id"] not in ids_vp, "error", "schema_invalid", f"{sid}: {d['element_id']} is drawn but is not an element of the Visual Plan")
            run.rule("diagram_in_safe_area", 9, sid, b[0] < mgn2 - 0.03 or b[1] < mgn2 - 0.03 or b[0] + b[2] > 1 - mgn2 + 0.03 or b[1] + b[3] > lim2 + 0.03, "warning", "layout_out_of_bounds",
                     f"{sid}: {d['element_id']} ({d['id']}) reaches outside the safe area")
            for t in m["texts"]:
                db = t.get("drawn_box")
                if db and d["layer"] != "motion_scene":
                    ov = visual_planning._overlap((b[0], b[1], b[0] + b[2], b[1] + b[3]), tuple(db))
                    small = min(b[2] * b[3], (db[2] - db[0]) * (db[3] - db[1]))
                    run.rule("diagram_clear_of_drawn_text", 9, sid, small > 0 and ov / small > 0.02, "warning", "layout_overlap", f"{sid}: {d['element_id']} ({d['id']}) lies on the text '{t['text']}' where the renderer draws it")
        tr, last = s["transition_out"], k == len(scenes) - 1
        if tr:
            nxt = scenes[k + 1] if not last else None
            run.rule("transition_known", 3, sid, tr["type"] not in trans, "error", "unknown_registry_id", f"{sid}: the transition '{tr['type']}' is not in the transition library")
            run.rule("transition_not_repeated", 7, sid, tr["type"] == prev_t, "error", "invalid_transition", f"{sid}: the transition '{tr['type']}' repeats the previous scene's")
            cap = 0.5 * min(t1 - t0, (nxt["timing"]["end"] - nxt["timing"]["start"]) if nxt else t1 - t0)
            run.rule("transition_fits", 7, sid, tr["dur"] < MIN_DUR - 1e-6 or tr["dur"] > cap + EPS, "error", "invalid_timing", f"{sid}: the transition lasts {tr['dur']} s but must be {MIN_DUR}-{cap:.2f} s to fit between the scenes")
            prev_t = tr["type"]
        else:
            run.rule("transition_present", 7, sid, not last, "warning", "hard_cut", f"{sid}: no transition into the next scene (hard cut)")
            prev_t = None
        c = s["continuity"]
        run.rule("repeat_text_preset", 4, sid, bool(c["main_text_preset"]) and c["main_text_preset"] in c["repeats"], "warning", "repeated_preset", f"{sid}: the main text uses '{c['main_text_preset']}' again, as the previous scene did")
        run.rule("repeat_graphic", 4, sid, any(p in c["repeats"] for p in c["placed_graphics"]), "warning", "repeated_preset", f"{sid}: the placed graphic repeats the previous scene's")
        ids = {a["action_id"] for a in s["sequence"]}
        run.rule("scene_animated", 5, sid, not s["sequence"] and not m.get("pictures"), "error", "mode_requirement", f"{sid}: the scene has nothing that moves (no text, no graphic and no picture)")      # a picture is moved by the camera
        run.rule("dependency_acyclic", 5, sid, not sc.acyclic(s["sequence"]), "error", "dependency_cycle", f"{sid}: the actions depend on each other in a circle")
        run.rule("dependencies_exist", 5, sid, any(d not in ids for a in s["sequence"] for d in a["depends_on"]), "error", "dependency_missing", f"{sid}: an action depends on an action that does not exist")
        by_id = {a["action_id"]: a for a in s["sequence"]}
        run.rule("dependency_order", 5, sid, any(a["start"] < by_id[d]["start"] - EPS for a in s["sequence"] for d in a["depends_on"] if d in by_id), "warning", "dependency_order", f"{sid}: an action starts before the action it depends on")
        run.rule("mode_requirement", 10, sid, not images and m.get("pictures", 0) > 0, "error", "mode_asset_conflict", f"{sid}: a Motion-Only plan has a picture")
    texts_all = [s["continuity"]["main_text_preset"] for s in scenes if s["continuity"]["main_text_preset"]]
    run.rule("variety", 4, None, len(scenes) >= 5 and len(set(texts_all)) < 3, "warning", "low_variety", f"only {len(set(texts_all))} different text presets in {len(scenes)} scenes")


def build(pdir: Path, aspect: str, progress=None, run_tests: bool = True) -> dict:
    """motion_planning.json from motion_plan.json (the selector's choices), the Visual Plan and the registry. Raises MotionError when an input is missing; the errors of the plan are in
    `validation` (the step refuses a plan that has any)."""
    from . import motion_scenes as sc, pipeline
    t0 = time.perf_counter()
    say = progress or (lambda p: None)
    mp_name = _names(aspect)[0]
    mp, sp, vp = _read(pdir / mp_name), _read(pdir / "scene_plan.json"), _read(pdir / "visual_planning.json")
    if mp is None or sp is None:
        raise MotionError(f"{mp_name if mp is None else 'scene_plan.json'} is missing or unreadable: run Motion Planning")
    reg, run, images = registry(), Run(), store.uses_images(pdir)
    fx = _read(pdir / FIXES) or {}
    run.accepted = set(fx.get("accepted", []))
    fps = int(mp.get("fps") or FPS)
    w, h = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    say(72)
    stale = visual_planning.blockers(pdir) if vp else None                          # stage 1
    run.rule("visual_plan_current", 1, None, bool(stale), "error", "visual_plan_not_current", f"the Visual Plan is not current: {stale}")
    run.rule("visual_plan_present", 1, None, vp is None, "warning", "visual_plan_missing", "this project has no Visual Plan: the elements of the scenes cannot be traced to it")
    bad = visual_planning.link_errors(mp["scenes"], visual_planning.handoff(pdir)) if vp else []
    run.rule("scenes_linked", 1, None, bool(bad), "error", "scene_mismatch", "; ".join(bad[:3]))
    run.rule("mode_matches", 1, None, mp.get("mode") != ("with-pictures" if images else "motion-only"), "error", "mode_mismatch", f"the motion plan was made for '{mp.get('mode')}' but Use Images is {'ON' if images else 'OFF'}")
    run.rule("aspect_matches", 1, None, mp.get("aspect") != aspect, "error", "aspect_mismatch", f"the motion plan is for {mp.get('aspect')}, not {aspect}")
    run.rule("scenes_present", 1, None, not mp["scenes"], "error", "schema_invalid", "the motion plan has no scenes")
    from . import asset_collection
    assets = {m["id"]: {a["element_id"]: a for a in asset_collection.assets_for_scene(pdir, m["id"])} for m in mp["scenes"]}
    scenes = _scene_entries(mp, vp, sp, aspect, fps, run, assets)                  # stages 2 and 5
    say(80)
    repairs: list[dict] = []
    sc.repair(scenes, repairs, reg, fps)                                            # stage 12, before the rules: they check the repaired plan
    _rules(scenes, reg, aspect, images, run)
    say(88)
    ids_all = [a["action_id"] for s in scenes for a in s["sequence"]]               # stage 10
    run.rule("ids_unique", 10, None, len(ids_all) != len(set(ids_all)), "error", "schema_invalid", "action ids are not unique")
    code = [str(v) for s in scenes for a in s["sequence"] for v in (a["preset"], a["target"], a["reason"]) if v and CODE_LIKE.search(str(v))]
    run.rule("no_code", 10, None, bool(code), "error", "schema_invalid", f"the plan contains code-like text: {code[:2]}")
    comp = _read(pdir / ("composition_9x16.json" if aspect == "9:16" else "composition.json"))        # stage 13
    out = {"motion_text": sum(1 for s in scenes for a in s["sequence"] if a["phase"] == "enter" and a["kind"] == "text" and a["preset"]),
           "motion_scene_items": sum(1 for s in scenes for a in s["sequence"] if a["kind"] == "graphic"), "icons": sum(1 for s in scenes for a in s["sequence"] if a["kind"] == "icon"),
           "classic_texts": sum(1 for s in scenes for a in s["sequence"] if a["kind"] == "text" and a["preset"] is None), "composition": "not built yet"}
    run.rule("adapter_fields", 13, None, any(a["start"] is None or (a["kind"] == "graphic" and not a["preset"]) for s in scenes for a in s["sequence"]), "error", "schema_invalid", "an action lacks the fields the Remotion layer needs")
    if comp:
        same = pipeline._planned(mp) == pipeline._built(comp)
        out["composition"] = "matches the plan" if same else "differs from the plan: Motion Generation has to build it again"
        run.rule("composition_current", 13, None, not same, "info", "composition_stale", "the composition on disk was built from an earlier plan: Motion Generation has to run again")
    tests = {"motion_checks": run_checks(pdir) if run_tests else {"ok": None, "error": "not run"}}                  # stage 11
    ok = tests["motion_checks"]["ok"]
    run.rule("motion_checks", 11, None, ok is False, "error", "motion_checks_failed", f"the motion library's own checks failed: {tests['motion_checks'].get('failed')}")
    run.rule("motion_checks_ran", 11, None, ok is None, "warning", "motion_checks_not_run", f"the motion library's checks could not run: {tests['motion_checks'].get('error')}")
    style = (vp or {}).get("visual_style") or {}
    plan = {"schema_version": SCHEMA, "version": VERSION, "source": "deterministic_selector",
            "project": {"mode": "image" if images else "motion_only", "aspect_ratio": aspect, "width": w, "height": h, "fps": fps},
            "timing_policy": {"unit": "seconds", "frame_rule": "frame = floor(seconds * fps + 0.5); the end frame is exclusive and after the start frame", "pace": mp.get("speed")},
            "visual_plan": {"file": "visual_planning.json" if vp else None, "fingerprint": (vp or {}).get("source_fingerprint"), "source": (vp or {}).get("source"), "text_and_hints_used": bool(mp.get("visual_plan_used"))},
            "style_guide": {"palette": style.get("palette") or sp.get("style", {}).get("palette"), "typography": style.get("typography"), "tone": style.get("tone"), "density": style.get("density"),
                            "safe_area_policy": style.get("safe_area_policy")},
            "source_fingerprint": fingerprint(pdir, aspect), "scenes": scenes,
            "reuse": {"text_presets_used": len({s["continuity"]["main_text_preset"] for s in scenes if s["continuity"]["main_text_preset"]}), "text_presets_available": len(reg["text"]),
                      "graphics_used": len({a["preset"] for s in scenes for a in s["sequence"] if a["kind"] == "graphic"}), "graphics_available": len(reg["graphic"]),
                      "ids_not_in_registry": sum(1 for i in run.items if i["code"] == "unknown_registry_id"), "new_presets_added": 0},
            "output": out, "stages": [], "validation": {}, "repairs": repairs, "tests": tests, "needs_review": False, "timings_seconds": {}}
    if fx:
        left = len(run.of("warning"))
        nd = sum(1 for s in scenes if s["scene_id"] in run.accepted for e in s["elements"] if e["status"] in ("fallback", "unresolved") and e["required"])      # accepted is not drawn: nothing in the library draws these
        acc = sorted(x["scene"] for x in run.items if x["code"] == "element_fallback" and x["severity"] == "info")                                       # the accepted scenes that still have an undrawn element
        plan["warning_fix"] = {"status": "solved" if left == 0 and nd == 0 else "partly", "not_drawn": nd, "approximate": sum(1 for s in scenes for e in s["elements"] if e["status"] == "approximate"),
                               "at": fx.get("at"), "before": fx.get("before"), "after": left, "changes": fx.get("changes", []), "accepted": acc, "left": [i["message"] for i in run.of("warning")]}
    try:
        PlanM.model_validate(plan)
        contract_ok = True
    except ValidationError as e:
        contract_ok = False
        for x in e.errors()[:5]:
            run.note(10, "error", "schema_invalid", None, f"motion_planning.{'.'.join(str(p) for p in x['loc'])}: {x['msg']}")
    run.counts["contract"] = [int(contract_ok), 1]
    for s in scenes:
        s["validation_notes"] = [{"code": i["code"], "severity": i["severity"], "message": i["message"]} for i in run.items if i["scene"] == s["scene_id"]]
    names = {1: "inputs", 2: "elements", 3: "ids", 4: "reuse", 5: "sequence", 6: "parameters", 7: "transitions", 8: "timing", 9: "layout", 10: "contract", 11: "tests", 12: "repairs", 13: "output"}
    for n in range(1, N + 1):
        its = [i for i in run.items if i["stage"] == n and i["severity"] in ("error", "warning")]
        er = [i for i in its if i["severity"] == "error"]
        if n == 12:
            status = "failed" if run.of("error") else "warning" if repairs else "completed"
            detail = f"{len(run.of('error'))} error(s) could not be repaired safely" if run.of("error") else (f"{len(repairs)} mechanical repair(s) made and recorded" if repairs else "nothing needed repair")
        elif n == 13 and not its:
            status = "completed"
            detail = f"{out['motion_text']} texts, {out['motion_scene_items']} graphics, {out['icons']} icons ready; composition {out['composition']}"
        else:
            status = "failed" if er else "warning" if its else "completed"
            done = run.by_stage.get(n, [0, 0])
            detail = (er or its)[0]["message"] if its else (f"{done[0]} of {done[1]} {names[n]} checks passed" if done[1] else f"{names[n]} checked")
        plan["stages"].append({"n": n, "name": STAGES[n - 1][0], "status": status, "detail": detail[:240]})
    errors = [i["message"] for i in run.of("error")]
    plan["validation"] = {"status": "error" if errors else "warning" if run.of("warning") else "ok", "errors": errors, "warnings": [i["message"] for i in run.of("warning")],
                          "checks": {"passed": sum(c[0] for c in run.counts.values()), "total": sum(c[1] for c in run.counts.values()),
                                     "by_rule": {k: {"passed": v[0], "total": v[1]} for k, v in run.counts.items()}},
                          "note": "no probability is claimed: the result is the list of checks that passed; the choice is the deterministic selector of the motion library"}
    plan["needs_review"] = bool(errors) or bool(run.of("warning"))
    plan["timings_seconds"] = {"build": round(time.perf_counter() - t0, 3)}
    return plan


# ---------- "Solve warnings" ----------
def solve(pdir: Path, aspect: str) -> dict:
    """Solve the warnings of the stored plan, mechanically and without Claude: a placed graphic that sits on the text area of the Visual Plan is moved to the nearest free spot of the safe area;
    a text that is shown too briefly to be read starts earlier (never before the scene starts); a required element the library cannot draw (a recorded fallback) is accepted, which is written
    into the plan. The decisions go to `motion_fixes.json`, which `build_composition.ts --fixes` applies to the plan AND the composition, so Motion Generation builds what was planned. The caller
    then runs Motion Planning again. Returns what was decided: {moved, earlier, accepted, before}."""
    plan = load(pdir, aspect)
    if plan is None:
        raise MotionError("there is no motion plan yet: run Motion Planning first")
    if plan["stale"]:
        raise MotionError("the motion plan is out of date: run Motion Planning first")
    mp, vp = _read(pdir / _names(aspect)[0]), _read(pdir / "visual_planning.json")
    if mp is None:
        raise MotionError(f"{_names(aspect)[0]} is missing: run Motion Planning first")
    old = _read(pdir / FIXES) or {}
    scenes, changes = old.get("scenes", {}), list(old.get("changes", []))
    vps = {s["plan_scene_id"]: s for s in (vp or {}).get("scenes", [])}
    key = "boxTall" if aspect == "9:16" else "box"
    mgn = config.SAFE_AREA["margin"]
    lim = 1 - config.SAFE_AREA["portrait_ui_bottom"] if aspect == "9:16" else 1 - mgn
    moved = earlier = 0
    kept: list[str] = []
    reg = registry()
    prev_dur = 0.0
    for m in mp["scenes"]:
        sid, t0, t1 = visual_planning._scene_id(m["id"]), m["start"], m["end"]
        fx = scenes.setdefault(str(m["id"]), {})
        rbs = [rb for e in (vps.get(m["id"]) or {}).get("elements", []) if mk.is_text(e["type"]) and (rb := visual_planning.region_box(e["placement"]["region"], aspect))]

        drawn = [tuple(x["drawn_box"]) for x in m["texts"] if x.get("drawn_box")]          # where the renderer really draws the texts (the Visual Plan's region is only the plan)
        cur = {i: g.get("box") for i, g in enumerate(m["graphics"])}                        # the boxes as they are while this scene is solved (a moved graphic is an obstacle for the next)

        def share(c: list[float], rb: tuple) -> float:                                      # the part of the smaller box that lies on the other (the check of the Layout Validator)
            small = min(c[2] * c[3], (rb[2] - rb[0]) * (rb[3] - rb[1]))
            return visual_planning._overlap((c[0], c[1], c[0] + c[2], c[1] + c[3]), rb) / small if small > 0 else 0.0

        def worst(c: list[float]) -> float:
            return max([share(c, rb) for rb in (*rbs, *drawn)] + [0.0])

        def crowded(c: list[float], me: int) -> bool:                                       # another placed graphic (a frame or backdrop fills the screen on purpose, so it is excluded)
            return any(
                share(c, (o[0], o[1], o[0] + o[2], o[1] + o[3])) > 1e-9
                for j, o in cur.items()
                if j != me and o
                and not m["graphics"][j].get("atmosphere")
                and reg["graphic"].get(m["graphics"][j].get("preset", ""), {}).get("category") != "frame"
                and o[2] * o[3] < 0.5
            )
        for gi, g in enumerate(m["graphics"]):
            b = g.get("box")
            if not b or g.get("atmosphere") or g.get("anchored") or b[2] * b[3] >= 0.5 or worst(b) <= 0.25 or reg["graphic"].get(g["preset"], {}).get("category") == "frame":
                continue
            xs = [mgn + i * (1 - 2 * mgn - b[2]) / 8 for i in range(9)] if 1 - 2 * mgn - b[2] > 0 else []
            ys = [mgn + j * (lim - mgn - b[3]) / 8 for j in range(9)] if lim - mgn - b[3] > 0 else []
            free = sorted(([round(x, 3), round(y, 3), b[2], b[3]] for x in xs for y in ys if worst([x, y, b[2], b[3]]) < 1e-9 and not crowded([x, y, b[2], b[3]], gi)),
                          key=lambda c: (c[0] - b[0]) ** 2 + (c[1] - b[1]) ** 2)
            if free:
                fx.setdefault(key, {})[g["preset"]] = free[0]
                cur[gi] = free[0]
                changes.append({"scene": sid, "kind": "graphic_moved", "preset": g["preset"], "from": b, "to": free[0], "why": "it lay on a text (planned area or drawn position); the new place does not touch any text, any other graphic or the margin"})
                moved += 1
            else:
                kept.append(f"{sid}: no place for '{g['preset']}' is clear of the text, the other graphics and the margin: it stays where it is, as a warning to review")
        floor = t0 + max(0.1, prev_dur)                                                     # not before the scene starts, not while the previous scene is still wiping out
        for i, t in enumerate(m["texts"]):
            at, until, need = (t["at"] if t.get("at") is not None else t0), reading_end(t, t1), reading_need(t)
            if until - at >= need:
                continue
            new = round(until - need - 0.01, 2)                                             # a hundredth of margin, so the reading time is met, not just touched
            if new >= floor and new < at:
                fx.setdefault("textAt", {})[str(i)] = new
                changes.append({"scene": sid, "kind": "text_earlier", "text": t["text"], "from": at, "to": new, "why": f"it needs {need:.1f} s on screen before it starts to leave; it now starts {at - new:.2f} s earlier"})
                earlier += 1
            else:
                kept.append(f"{sid}: '{t['text']}' needs {need:.1f} s but only {until - floor:.1f} s are available between the start of the scene (and its transition) and the exit of the text: shorten the text or lengthen the scene")
        prev_dur = (m.get("transition") or {}).get("dur") or 0.0
        if not fx:
            scenes.pop(str(m["id"]))
    accepted = sorted(set(old.get("accepted", [])) | {s["scene_id"] for s in plan["scenes"] for n in s["validation_notes"] if n["code"] == "element_fallback" and n["severity"] == "warning"})
    new_acc = len(accepted) - len(old.get("accepted", []))
    if not (moved or earlier or new_acc):
        return {"moved": 0, "earlier": 0, "accepted": 0, "kept": kept, "before": len(plan["validation"]["warnings"])}
    before = old.get("before", len(plan["validation"]["warnings"]))               # the count before the FIRST solve
    tmp =(pdir / FIXES).with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "before": before, "scenes": scenes, "accepted": accepted, "changes": changes}, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pdir / FIXES)
    return {"moved": moved, "earlier": earlier, "accepted": new_acc, "kept": kept, "before": before}


def align_emphasis(pdir: Path, aspect: str, decisions: list[dict]) -> list[dict]:
    """Put the emphasis of a marked on-screen word on the spoken word it translates. The library's own time is a placeholder (the text's start + 0.25 s / pace: it does not know the transcript), and the
    English text has no word timings of its own, so the mapping is a decision: each one names the scene, the on-screen text and the SPOKEN word (as it is in the transcript). The time becomes the
    start of that word, only when it lies inside the scene, after the text has entered and early enough for the emphasis to be seen before the text leaves; otherwise nothing is written and MotionError says why.
    The decision goes to `motion_fixes.json` (`emphasisAt`, applied by `build_composition.ts --fixes`) with a `changes` record; Motion Planning has to run again. Nothing else in the file is touched."""
    from .motion_generation import words as spoken
    mp = _read(pdir / _names(aspect)[0])
    if mp is None:
        raise MotionError(f"{_names(aspect)[0]} is missing: run Motion Planning first")
    ws = spoken(pdir)
    old = _read(pdir / FIXES) or {}
    scenes, changes, done = old.get("scenes", {}), list(old.get("changes", [])), []
    for d in decisions:
        m = next((x for x in mp["scenes"] if x["id"] == d["scene"]), None)
        if m is None:
            raise MotionError(f"scene {d['scene']} is not in the plan")
        sid = visual_planning._scene_id(m["id"])
        i = next((k for k, t in enumerate(m["texts"]) if norm(t["text"]) == norm(d["text"]) and t.get("emphasis_at")), None)
        if i is None:
            raise MotionError(f"{sid}: no text '{d['text']}' with an emphasis")
        t = m["texts"][i]
        cur = t["emphasis_at"][0]
        clean = lambda w: re.sub(r"[.,;:!?]+$", "", w["w"]).strip()
        hits = [w for w in ws if clean(w) == d["word"].strip() and m["start"] - EPS <= w["start"] and w["end"] <= m["end"] + EPS]
        if not hits:
            raise MotionError(f"{sid}: the spoken word '{d['word']}' is not in the scene")
        w = min(hits, key=lambda x: abs(x["start"] - cur))
        new = round(w["start"], 2)
        entered = (t["at"] if t.get("at") is not None else m["start"]) + (t.get("enter_s") or 0.5)
        if new < entered - EPS:
            raise MotionError(f"{sid}: '{d['word']}' starts at {new:g} s, before '{t['text']}' has entered ({entered:.2f} s): the emphasis would be seen on a text that is not there yet")
        if new + 0.4 > reading_end(t, m["end"]):
            raise MotionError(f"{sid}: '{d['word']}' starts at {new:g} s, too late for the emphasis to be seen before '{t['text']}' leaves ({reading_end(t, m['end']):.2f} s)")
        scenes.setdefault(str(m["id"]), {}).setdefault("emphasisAt", {})[str(i)] = new
        changes.append({"scene": sid, "kind": "emphasis_aligned", "text": t["text"], "word": d["word"], "from": cur, "to": new,
                        "why": d.get("why") or f"the marked word of '{t['text']}' is spoken as '{d['word']}' from {new:g} s; the library's placeholder time ({cur:g} s) was not on a word boundary"})
        done.append(changes[-1])
    if done:
        tmp = (pdir / FIXES).with_suffix(".tmp")
        tmp.write_text(json.dumps({**old, "version": old.get("version", 1), "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "scenes": scenes, "changes": changes}, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(pdir / FIXES)
    return done


def auto_align_emphasis(pdir: Path, aspect: str) -> dict:
    """The mechanical form of `align_emphasis`, for the warning "the emphasis ... is not on a spoken word": an emphasis time that lies INSIDE a spoken word (more than 0.06 s from both its
    ends) is put on the start of that very word. Only where the transcript itself says which word the time is in; an emphasis in a pause, or one that `align_emphasis` refuses (before the text
    has entered, too late to be seen), is left as it is and reported in `kept`. Returns {done: [changes], kept: [reasons]}; Motion Planning has to run again."""
    from .motion_generation import words as spoken
    plan = _read(pdir / _names(aspect)[0])
    if plan is None:
        raise MotionError(f"{_names(aspect)[0]} is missing: run Motion Planning first")
    ws = spoken(pdir)
    clean = lambda w: re.sub(r"[.,;:!?]+$", "", w["w"]).strip()
    done: list[dict] = []
    kept: list[str] = []
    for m in plan["scenes"]:
        for t in m["texts"]:
            for x in (t.get("emphasis_at") or [])[:1]:
                inside = next((w for w in ws if m["start"] - EPS <= w["start"] and w["end"] <= m["end"] + EPS and w["start"] + 0.06 < x < w["end"] - 0.06), None)
                if inside is None:
                    continue
                try:
                    done += align_emphasis(pdir, aspect, [{"scene": m["id"], "text": t["text"], "word": clean(inside), "why": f"the emphasis at {x:g} s lay inside the spoken word '{clean(inside)}': it now starts with that word"}])
                except MotionError as e:
                    kept.append(str(e))
    return {"done": done, "kept": kept}


# ---------- the file ----------
def save(pdir: Path, aspect: str, plan: dict) -> None:
    f = pdir / _names(aspect)[1]
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def load(pdir: Path, aspect: str) -> dict | None:
    """The stored plan with `stale` (made from other inputs than the current ones). None when it has not been made."""
    plan = _read(pdir / _names(aspect)[1])
    if not plan:
        return None
    try:
        plan["stale"] = plan.get("source_fingerprint") != fingerprint(pdir, aspect) or plan.get("schema_version") != SCHEMA or plan.get("version") != VERSION
    except OSError:
        plan["stale"] = True
    return plan


def blockers(pdir: Path, aspect: str) -> str | None:
    """Why Motion Generation must not run from this plan (None = it may)."""
    plan = load(pdir, aspect)
    if plan is None:
        return None                                       # a project made before this existed: the step that wrote motion_plan.json is the gate
    if plan["stale"]:
        return "the checked motion plan is out of date: run Motion Planning again"
    if plan["validation"]["errors"]:
        return f"the motion plan has {len(plan['validation']['errors'])} blocking error(s) ({plan['validation']['errors'][0]})"
    return None
