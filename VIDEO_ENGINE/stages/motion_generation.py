"""Motion Generation (roadmap improvements/Motion_Generation_Complete_Roadmap): the step `motion-build` turns the checked motion plan into the composition the Remotion renderer reads
(VIDEO_ENGINE/remotion/scripts/build_composition.ts). This module makes that step checked and traceable: it reads the plan, builds a descriptor for every element of the composition, validates
registry ids, timing in frames, audio sync, layout and the renderer contract, repairs only what is mechanical (bounded) and writes `motion_generation[_9x16].json`, the report the page shows.
No Claude call, no code from the plan is ever executed: the plan is data and presets are looked up in the real registry (`npx tsx scripts/motion_list.ts`). Same inputs = same output.

The 13 logical stages (steps of one module, not 13 agents; the rules are in motion_gen_rules.py):
  1 Plan Reader          motion_planning.json: current, valid, same mode / aspect / fps as the project
  2 Element Resolver     every planned element has something drawable in the composition (or is a recorded fallback)
  3 Preset Registry      every preset, exit, emphasis, transition and primitive in the composition is in the installed registry
  4 Effect Reuse         only existing presets are used, none is added; the fallbacks of the plan are carried over
  5 Animation Builder    one descriptor per composition layer / item and every planned action is built at its planned time
  6 Engine Adapter       every layer type has a registered frame-driven component; no wall clock or unseeded random in the animation code
  7 Composition Builder  scene order and intervals as planned, unique ids, no element drawn twice, transitions fit
  8 Audio Sync           frames follow the one seconds-to-frames rule, inside the scene, emphasis on a spoken word, audio file and duration
  9 Layout Validation    safe area of the aspect ratio, no graphic on a drawn text, nodes apart
  10 Code Validation     the renderer's zod schema, no code in the composition, parameter ranges
  11 Motion Testing      the motion library's checks and a second build that must be identical (determinism)
  12 Error Repair        only mechanical repairs (clamp a time, clamp a box into the safe area), at most two passes, each recorded
  13 Remotion Adapter    the composition is persisted, read back equal, and matches the mode (no pictures in motion-only)
"""
import hashlib
import json
import subprocess
from pathlib import Path

from . import motion_planning as mp

SCHEMA = "1.0"
VERSION = 1                                    # bump when the rules or the structure change (part of the fingerprint)
MAX_REPAIR_PASSES = 2
DOME_RATIOS = (1, 0.7, 0.5, 0.4, 0.3)             # mirror of VIDEO_ENGINE/remotion/src/components/domeGeometry.ts (compared by tests/test_motion_validation.py)
DOME_GAP = 0.1
EPS = mp.EPS
STAGES = (
    ("Plan Reader", "Reading motion-plan.json"),
    ("Element Resolver", "Finding what draws every planned element"),
    ("Preset Registry", "Checking every preset against the real registry"),
    ("Effect Reuse", "Reusing existing effects, adding none"),
    ("Animation Builder", "Building one descriptor per layer"),
    ("Engine Adapter", "Routing to frame-driven components"),
    ("Composition Builder", "Ordering scenes, layers and transitions"),
    ("Audio Sync", "Fixing seconds and frames on the audio timeline"),
    ("Layout Validation", "Checking safe areas and overlaps"),
    ("Code Validation", "Checking the composition against the renderer"),
    ("Motion Testing", "Running the motion checks and a repeat build"),
    ("Error Repair", "Repairing only what is safe to repair"),
    ("Remotion Adapter", "Writing the composition for Remotion"),
)
N = len(STAGES)


class GenerationError(Exception):
    """The generation cannot be checked (an input is missing): the message says what to do."""


def names(aspect: str) -> tuple[str, str, str]:
    """(composition, report, motion plan) file names of an aspect ratio."""
    sfx = "_9x16" if aspect == "9:16" else ""
    return f"composition{sfx}.json", f"motion_generation{sfx}.json", f"motion_plan{sfx}.json"


def dumps(comp: dict) -> str:
    return json.dumps(comp, indent=1)


def sha(data: str | bytes) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()[:16]


def words(pdir: Path) -> list[dict]:
    """The spoken words the composition was built from (the same file order as build_composition.ts)."""
    for n in ("transcript_fixed.json", "transcript_corrected.json", "transcript.json"):
        t = mp._read(pdir / n)
        if t:
            return [w for s in t.get("segments", []) for w in s.get("words", [])]
    return []


_val: dict = {}


def validate_composition(path: Path) -> dict:
    """The renderer's own contract (scripts/motion_validate.ts): zod schema, a registered component per layer type, no wall clock in the animation code. Cached by library source + file."""
    from . import pipeline
    key = (pipeline._remotion_src_digest(), sha(path.read_bytes()))
    if _val.get("key") == key:
        return _val["res"]
    try:
        r = subprocess.run(f'npx tsx scripts/motion_validate.ts "{path.resolve()}"', cwd=pipeline._REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        line = next((x for x in reversed(r.stdout.splitlines()) if x.startswith("{")), "")
        res = json.loads(line) if line else {"zod": [(r.stderr or r.stdout)[-200:]], "layer_types": {}, "unknown": [], "wallclock": []}
    except (subprocess.TimeoutExpired, ValueError, OSError) as e:
        res = {"zod": [f"the validator could not run: {e}"], "layer_types": {}, "unknown": [], "wallclock": [], "not_run": True}
    _val.update(key=key, res=res)
    return res


# ---------- stage 5: one descriptor per layer / item ----------
def descriptors(scene: dict, ps: dict | None, fps: int) -> list[dict]:
    """One descriptor per layer / item of a composition scene, linked to the planned action that asked for it (`plan_action_id`); planned actions that were not built come last with `missing`."""
    sid = f"scene_{scene['id']:02d}"
    s0, s1 = scene["start"], scene["end"]
    actions = [a for a in (ps or {}).get("sequence", []) if a["phase"] in ("establish", "reveal", "enter")]
    used: set[str] = set()
    out: list[dict] = []

    def take(preset, start, target=None, text=None, kind=None):
        best = None
        for a in actions:
            if a["action_id"] in used or a["preset"] != preset or (kind and a["kind"] != kind):
                continue
            if target and a["target"] != target:
                continue
            if text is not None and mp.norm((a.get("params") or {}).get("text") or "") != mp.norm(text):
                continue
            d = abs(a["start"] - start)
            if best is None or d < best[0]:
                best = (d, a)
        if best and best[0] <= 0.5:
            used.add(best[1]["action_id"])
            return best[1]
        return None

    def add(element_id, etype, comp_id, preset, props, start, end, z, act):
        did = f"{sid}:{element_id}:{comp_id}:{preset}"                   # one id per layer; the plan may give one element id to a text and to the graphic chosen for its hint
        n = sum(1 for x in out if x["descriptor_id"].split("#")[0] == did)
        out.append({"descriptor_id": did if not n else f"{did}#{n + 1}", "scene_id": sid, "element_id": element_id, "element_type": etype, "component_id": comp_id, "preset_id": preset, "props": props,
                    "start": round(start, 3), "end": round(end, 3), "start_frame": mp.fr(start, fps), "end_frame": mp.fr(end, fps), "duration_frames": max(0, mp.fr(end, fps) - mp.fr(start, fps)),
                    "z": z, "depends_on": (act or {}).get("depends_on", []), "plan_action_id": (act or {}).get("action_id"), "from_plan": bool(act)})
    ti = 0
    for k, l in enumerate(scene["layers"]):
        z = l.get("z", 0)
        if l["type"] == "motion_text":
            at = l.get("at", s0)
            act = take(l.get("preset"), at, text=l.get("text"))
            add((act or {}).get("target") or f"{sid}_text_{ti + 1:02d}", "text", "motion_text", l.get("preset"),
                {k2: l.get(k2) for k2 in ("text", "style", "exitPreset", "emphasis", "dir", "k", "mark", "emphasisAt", "dur", "exitDur") if l.get(k2) is not None}, at, l.get("until") if l.get("until") is not None else s1, z, act)
            ti += 1
        elif l["type"] == "motion_scene":
            for it in l.get("items", []):
                st = it.get("start", s0)
                act = take(it["preset"], st)
                add((act or {}).get("target") or f"{sid}_gfx_{k + 1:02d}_{it['preset']}", "graphic", "motion_scene", it["preset"],
                    {"box": it.get("box"), "boxTall": it.get("boxTall"), "k": it.get("k"), "dir": it.get("dir"), "speed": it.get("speed"), "bleed": bool(it.get("bleed")), "exitDur": it.get("exitDur")},
                    st, it.get("end") if it.get("end") is not None else s1, it.get("z", z), act)
        elif l["type"] in ("shape", "icon") and l.get("elementId"):
            pid = f"shape:{l.get('kind')}" if l["type"] == "shape" else f"resource:{l['resource_id']}" if l.get("resource_id") else f"icon:{l.get('lucide')}"      # a registry icon (Resource Library) is its own primitive id
            at = l.get("at", s0) if l["type"] == "shape" else (l.get("enter") or {}).get("at", s0)
            act = take(pid, at, target=l["elementId"])
            add(l["elementId"], l["type"], l["type"], pid, {kk: l.get(kk) for kk in ("kind", "lucide", "resource_id", "from", "to", "pos", "size", "color", "fill") if l.get(kk) is not None}, at, s1, z, act)
        elif l["type"] in ("custom_scene", "custom_motion"):
            comp_id = l.get("component") or f"Scene{scene['id']}"
            for a in actions:
                used.add(a["action_id"])
            add(f"{sid}_custom_scene", "custom_scene", "custom_scene", comp_id,
                {"scene_id": scene["id"], "component": comp_id}, s0, s1, z, None)
        else:                                                           # background, effect, pattern icon, classic text ...: the scene's own layers; an icon or text of the plan is matched to its action
            at = l.get("at", (l.get("enter") or {}).get("at", s0))
            act = take(None, at, kind="icon") if l["type"] == "icon" else take(None, at, kind="text", text=l["text"]) if isinstance(l.get("text"), str) and l.get("text") else None
            add((act or {}).get("target") or f"{sid}_layer_{k + 1:02d}", l["type"], l["type"], l.get("preset") or l.get("name") or l.get("lucide"),
                {kk: l.get(kk) for kk in ("kind", "lucide", "name", "pos", "text") if l.get(kk) is not None}, at, s1, z, act)
    for a in actions:                                                   # planned but not built
        if a["action_id"] not in used and a["kind"] in ("text", "graphic", "icon"):
            out.append({"descriptor_id": f"{sid}:{a['target']}:missing:{a['action_id']}", "scene_id": sid, "element_id": a["target"], "element_type": "missing", "component_id": None, "preset_id": a["preset"], "props": {}, "start": a["start"], "end": a["end"],
                        "start_frame": a["start_frame"], "end_frame": a["end_frame"], "duration_frames": 0, "z": 0, "depends_on": [], "plan_action_id": a["action_id"], "from_plan": True, "missing": True})
    return out


def rect_of_layer(l: dict, W: int, H: int):
    """Where a drawn element sits as [x0, y0, x1, y1] fractions. The `shape` layer draws its circle with the centre at from + (r, r) (an arc through two almost equal points)."""
    if l["type"] == "shape" and l.get("kind") == "circle" and l.get("from") and l.get("to"):
        (x1, y1), (x2, y2) = l["from"], l["to"]
        r = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        return [x1 / W, y1 / H, (x1 + 2 * r) / W, (y1 + 2 * r) / H]
    if l["type"] == "shape" and l.get("kind") == "dome" and l.get("from") and l.get("to"):        # a cluster of domes on a base line: its tallest dome is as high as DOME_RATIOS says (VIDEO_ENGINE/remotion/src/components/domeGeometry.ts)
        (x1, y1), (x2, y2) = l["from"], l["to"]
        n = max(1, min(len(DOME_RATIOS), round(l.get("count") or 1)))
        top = abs(x2 - x1) / (2 * sum(DOME_RATIOS[:n]) + DOME_GAP * (n - 1))
        base = (y1 + y2) / 2
        return [min(x1, x2) / W, (base - top) / H, max(x1, x2) / W, base / H]
    if l["type"] == "icon" and l.get("pos"):
        s = (l.get("size") or 160) / 2
        return [(l["pos"][0] - s) / W, (l["pos"][1] - s) / H, (l["pos"][0] + s) / W, (l["pos"][1] + s) / H]
    return None
