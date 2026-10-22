"""The rules of the 13 Motion Generation stages (backend/motion_generation.py). Each function checks one stage against the composition that build_composition.ts wrote and the checked
motion plan, and records findings in a `motion_planning.Run` (an error blocks the step, a warning does not). Nothing here changes a file: repairs work on the composition in memory."""
from __future__ import annotations

from . import config, motion_planning as mp, visual_planning
from .motion_generation import EPS, MAX_REPAIR_PASSES, descriptors, rect_of_layer, words

SAFE = config.SAFE_AREA["margin"]
FRAME = "frame"


class G:
    """What the stages share: the project, the composition, the plans and the registry."""

    def __init__(self, pdir, aspect, comp, plan, mplan, reg, images, run):
        self.pdir, self.aspect, self.comp, self.plan, self.mplan, self.reg, self.images, self.run = pdir, aspect, comp, plan, mplan, reg, images, run
        self.tall = aspect == "9:16"
        self.fps = int(comp["meta"].get("fps") or mp.FPS)
        self.W, self.H = comp["meta"].get("width", 1920), comp["meta"].get("height", 1080)
        self.lim = 1 - config.SAFE_AREA["portrait_ui_bottom"] if self.tall else 1 - SAFE
        self.ps = {s["plan_scene_id"]: s for s in (plan or {}).get("scenes", [])}
        self.ms = {s["id"]: s for s in (mplan or {}).get("scenes", [])}
        self.desc: dict[int, list[dict]] = {}
        self.reuse: dict = {}

    def sid(self, s):
        return f"scene_{s['id']:02d}"

    def rebuild(self):
        self.desc = {s["id"]: descriptors(s, self.ps.get(s["id"]), self.fps) for s in self.comp["scenes"]}

    def all_desc(self):
        return [d for s in self.comp["scenes"] for d in self.desc.get(s["id"], [])]


def _box_rect(b):
    return [b[0], b[1], b[0] + b[2], b[1] + b[3]]


def _share(a, b):
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return visual_planning._overlap(tuple(a), tuple(b)) / small if small > 0 else 0.0


def _item_box(it, tall):
    return (it.get("boxTall") if tall else None) or it.get("box")


def _outside(rect, lim):
    return rect[0] < SAFE - 0.03 or rect[1] < SAFE - 0.03 or rect[2] > 1 - SAFE + 0.03 or rect[3] > lim + 0.03


# ---------- 1 Plan Reader ----------
def stage1(g: G) -> None:
    r, p = g.run, g.plan
    r.rule("plan_present", 1, None, p is None, "error", "plan_missing", "motion_planning.json is missing: run Motion Planning first")
    if p is None:
        return
    r.rule("plan_current", 1, None, bool(p.get("stale")), "error", "plan_stale", "the checked motion plan is out of date: run Motion Planning again")
    r.rule("plan_without_errors", 1, None, bool(p["validation"]["errors"]), "error", "plan_has_errors", f"the motion plan has {len(p['validation']['errors'])} blocking error(s)")
    r.rule("mode_matches", 1, None, p["project"]["mode"] != ("image" if g.images else "motion_only"), "error", "mode_mismatch", f"the plan is for '{p['project']['mode']}' but Use Images is {'ON' if g.images else 'OFF'}")
    r.rule("aspect_matches", 1, None, p["project"]["aspect_ratio"] != g.aspect or (g.H > g.W) != g.tall, "error", "aspect_mismatch", f"plan {p['project']['aspect_ratio']}, composition {g.W}x{g.H}, project {g.aspect}")
    r.rule("fps_matches", 1, None, int(p["project"]["fps"]) != g.fps, "error", "fps_mismatch", f"the plan is {p['project']['fps']} fps, the composition {g.fps} fps")
    n_m = len((g.mplan or {}).get("scenes", []))
    r.rule("scene_count", 1, None, not (len(p["scenes"]) == n_m == len(g.comp["scenes"])), "error", "scene_mismatch", f"{len(p['scenes'])} planned scenes, {n_m} in motion_plan.json, {len(g.comp['scenes'])} in the composition")


# ---------- 2 Element Resolver ----------
def _verified_drawn(g: G) -> dict[int, set[str]]:
    """Per scene, the planned elements whose generated TSX carries a data-element-id node (only manifests that recorded that check count)."""
    from . import motion_animation
    anim = motion_animation.load_animation(g.pdir, g.aspect) or {}
    return {m["scene_id"]: set(m.get("implemented_elements", [])) for m in anim.get("scenes", []) if "missing_elements" in (m.get("generation") or {})}


def stage2(g: G) -> None:
    r = g.run
    verified = _verified_drawn(g)
    for s in g.comp["scenes"]:
        ps, sid, ds = g.ps.get(s["id"]), g.sid(s), g.desc[s["id"]]
        custom = any(d.get("component_id") in ("custom_scene", "custom_motion") for d in ds)
        for e in (ps or {}).get("elements", []):
            if e["status"] in ("fallback", "unresolved") and custom and e["element_id"] in verified.get(s["id"], ()):
                continue                                                # the plan's preset fallback does not apply: the generated code draws it
            if e["status"] in ("fallback", "unresolved"):
                why = (e.get("fallback") or {}).get("reason")
                r.rule("element_drawn", 2, sid, bool(e["required"]), "warning", "element_not_drawn", f"{sid}: {e['element_id']} is a recorded fallback of the plan and is NOT drawn" + (f" ({why})" if why else ""))
                continue
            kind, rid, eid = e.get("registry_kind"), e.get("registry_id"), e["element_id"]
            if e["type"] == "background" or kind == "layer":
                built = True
            elif any(d.get("component_id") in ("custom_scene", "custom_motion") for d in ds):
                built = True
            elif kind == "text_preset":
                built = any(d["element_id"] == eid or (d["component_id"] == "motion_text" and d["preset_id"] == rid) for d in ds)
            elif kind == "primitive":
                built = any(d["element_id"] == eid for d in ds)
            elif kind == "graphic_preset":
                built = any(d["preset_id"] == rid for d in ds)
            elif kind == "icon":
                built = any(d["component_id"] == "icon" for d in ds)
            else:
                built = True
            r.rule("element_drawn", 2, sid, not built, "error" if e["required"] else "warning", "element_not_built", f"{sid}: {eid} ({rid}) is planned as drawn but the composition has no layer for it")


# ---------- 3 Preset Registry ----------
def stage3(g: G, val: dict | None = None) -> None:
    r, reg = g.run, g.reg
    for name in (val or {}).get("bad_icons", []):                       # an icon name lucide does not have draws nothing
        r.rule("icon_exists", 3, None, True, "error", "unknown_registry_id", f"the icon '{name}' does not exist in lucide: the renderer would draw nothing")
    from . import resource_library
    for f in resource_library.check_composition(g.comp):                  # a resource of the Resource Library must exist, be verified, match its pinned hash and resolve locally
        r.rule("resource_resolves", 3, None, True, "error", f["code"], f["message"])
    trans = mp.transitions()
    for s in g.comp["scenes"]:
        sid = g.sid(s)
        for l in s["layers"]:
            if l["type"] == "motion_text":
                for key, kind in (("preset", "text"), ("exitPreset", "exit"), ("emphasis", "emphasis")):
                    if l.get(key):
                        r.rule("registry_id", 3, sid, l[key] not in reg[kind], "error", "unknown_registry_id", f"{sid}: '{l[key]}' is not a {kind} preset of the installed registry")
            elif l["type"] == "motion_scene":
                for it in l.get("items", []):
                    if it.get("kind", "gfx") == "gfx":
                        r.rule("registry_id", 3, sid, it["preset"] not in reg["graphic"], "error", "unknown_registry_id", f"{sid}: '{it['preset']}' is not a graphic preset of the installed registry")
            elif l["type"] == "shape" and l.get("elementId"):
                r.rule("registry_id", 3, sid, f"shape:{l.get('kind')}" not in reg["primitive"], "error", "unknown_registry_id", f"{sid}: shape '{l.get('kind')}' is not a drawing primitive of the registry")
            elif l["type"] == "icon" and l.get("elementId"):
                pid = f"resource:{l['resource_id']}" if l.get("resource_id") else f"icon:{l.get('lucide')}"
                r.rule("registry_id", 3, sid, pid not in reg["primitive"], "error", "unknown_registry_id", f"{sid}: icon '{l.get('resource_id') or l.get('lucide')}' is not a drawing primitive of the registry")
        t = s.get("transition_out")
        if t:
            r.rule("transition_known", 3, sid, t["type"] not in trans, "error", "unknown_registry_id", f"{sid}: the transition '{t['type']}' is not in the transition library")


# ---------- 4 Effect Reuse ----------
def stage4(g: G) -> None:
    r = g.run
    used = {d["preset_id"] for d in g.all_desc() if d["from_plan"] and d["preset_id"] and (d["component_id"] in ("motion_text", "motion_scene") or ":" in d["preset_id"])}      # presets of the library and drawing primitives; a pattern icon is a lucide name (checked in stage 3)
    known = set(g.reg["text"]) | set(g.reg["graphic"]) | set(g.reg["primitive"]) | set(g.reg["exit"]) | set(g.reg["emphasis"])
    r.rule("no_new_presets", 4, None, bool(used - known), "error", "new_preset", f"presets that are not in the registry were used: {sorted(used - known)[:3]}")
    for s in (g.plan or {}).get("scenes", []):
        for e in s["elements"]:
            r.rule("fallback_recorded", 4, s["scene_id"], e["status"] == "fallback" and not (e.get("fallback") or {}).get("reason"), "warning", "fallback_unexplained", f"{s['scene_id']}: the fallback of {e['element_id']} has no reason")
    g.reuse = {"presets_used": len(used), "new_presets_added": 0, "fallbacks_carried": sum(1 for s in (g.plan or {}).get("scenes", []) for e in s["elements"] if e["status"] == "fallback")}


# ---------- 5 Animation Builder ----------
def stage5(g: G) -> None:
    r = g.run
    for s in g.comp["scenes"]:
        sid, ds = g.sid(s), g.desc[s["id"]]
        ids = [d["descriptor_id"] for d in ds]
        r.rule("descriptor_ids_unique", 5, sid, len(ids) != len(set(ids)), "error", "schema_invalid", f"{sid}: two descriptors have the same id")
        for d in ds:
            if d.get("missing"):
                r.rule("action_built", 5, sid, True, "error", "action_not_built", f"{sid}: the planned action {d['plan_action_id']} ({d['preset_id']}) is not in the composition")
                continue
            if not d["plan_action_id"]:
                continue
            r.rule("action_built", 5, sid, False, "error", "action_not_built", "")
            a = next(x for x in g.ps[s["id"]]["sequence"] if x["action_id"] == d["plan_action_id"])
            r.rule("timing_matches_plan", 5, sid, abs(a["start"] - d["start"]) > 0.06 and not d.get("repaired"), "error", "invalid_timing", f"{sid}: {d['element_id']} starts at {d['start']:g} s but the plan says {a['start']:g} s")
            pb = (a.get("params") or {}).get("box")
            if a["kind"] == "graphic" and pb and d["component_id"] == "motion_scene" and not d.get("repaired"):
                cb = _item_box({"box": d["props"].get("box"), "boxTall": d["props"].get("boxTall")}, g.tall)
                r.rule("box_matches_plan", 5, sid, bool(cb) and any(abs(x - y) > 0.003 for x, y in zip(pb, cb)), "error", "plan_mismatch", f"{sid}: {d['element_id']} sits at {cb} but the plan says {pb}")


# ---------- 6 Engine Adapter ----------
def stage6(g: G, val: dict) -> None:
    r = g.run
    r.rule("validator_ran", 6, None, bool(val.get("not_run")), "warning", "validator_not_run", "the renderer's validator could not run: " + str(val.get("zod")))
    r.rule("component_registered", 6, None, bool(val.get("unknown")), "error", "unknown_layer_type", f"the renderer has no component for the layer type(s) {val.get('unknown')}: they would be skipped")
    r.rule("frame_driven", 6, None, bool(val.get("wallclock")), "error", "wallclock", f"animation code that depends on a clock or Math.random: {val.get('wallclock')}")


# ---------- 7 Composition Builder ----------
def stage7(g: G) -> None:
    r, comp = g.run, g.comp["scenes"]
    trans = mp.transitions()
    ids = [s["id"] for s in comp]
    r.rule("scene_ids_unique", 7, None, len(ids) != len(set(ids)), "error", "schema_invalid", "two scenes have the same id")
    prev_t = None
    for k, s in enumerate(comp):
        sid, ps = g.sid(s), g.ps.get(s["id"])
        if ps:
            r.rule("scene_interval", 7, sid, abs(ps["timing"]["start"] - s["start"]) > EPS or abs(ps["timing"]["end"] - s["end"]) > EPS, "error", "invalid_timing",
                   f"{sid}: the composition has {s['start']:g}-{s['end']:g} s but the plan has {ps['timing']['start']:g}-{ps['timing']['end']:g} s")
        if k:
            r.rule("scenes_in_order", 7, sid, s["start"] < comp[k - 1]["end"] - EPS, "error", "invalid_timing", f"{sid}: starts before the previous scene ends")
        seen: set[str] = set()
        for l in s["layers"]:
            eid = l.get("elementId")
            if eid:
                r.rule("one_owner", 7, sid, eid in seen, "error", "duplicate_element", f"{sid}: {eid} is drawn by two layers")
                seen.add(eid)
        t = s.get("transition_out")
        if t:
            nxt = comp[k + 1] if k + 1 < len(comp) else None
            cap = 0.5 * min(s["end"] - s["start"], (nxt["end"] - nxt["start"]) if nxt else s["end"] - s["start"])
            r.rule("transition_known", 7, sid, t["type"] not in trans, "error", "unknown_registry_id", f"{sid}: the transition '{t['type']}' is not in the transition library")
            r.rule("transition_not_repeated", 7, sid, t["type"] == prev_t, "error", "invalid_transition", f"{sid}: the transition '{t['type']}' repeats the previous scene's")
            r.rule("transition_fits", 7, sid, t["dur"] < mp.MIN_DUR - 1e-6 or t["dur"] > cap + EPS, "error", "invalid_timing", f"{sid}: the transition lasts {t['dur']} s, it must be {mp.MIN_DUR}-{cap:.2f} s")
            if ps and ps.get("transition_out"):
                r.rule("transition_as_planned", 7, sid, ps["transition_out"]["type"] != t["type"], "error", "plan_mismatch", f"{sid}: the plan says '{ps['transition_out']['type']}', the composition '{t['type']}'")
            prev_t = t["type"]
        else:
            prev_t = None
        r.rule("z_order_defined", 7, sid, any(not isinstance(l.get("z", 0), (int, float)) for l in s["layers"]), "error", "schema_invalid", f"{sid}: a layer has no numeric z-order")


# ---------- 8 Audio Sync ----------
def stage8(g: G) -> None:
    r, fps = g.run, g.fps
    ws = words(g.pdir)
    marks = sorted({round(w["start"], 2) for w in ws} | {round(w["end"], 2) for w in ws})
    for s in g.comp["scenes"]:
        sid = g.sid(s)
        f0, f1 = mp.fr(s["start"], fps), mp.fr(s["end"], fps)
        for d in g.desc[s["id"]]:
            if d.get("missing"):
                continue
            r.rule("frames_in_scene", 8, sid, d["start_frame"] < f0 - 1 or d["end_frame"] > f1 + 1 or d["end_frame"] < d["start_frame"], "error", "invalid_timing",
                   f"{sid}: {d['element_id']} runs frames {d['start_frame']}-{d['end_frame']}, outside the scene {f0}-{f1}")
            for t in (d["props"].get("emphasisAt") or []):
                r.rule("emphasis_on_a_word", 8, sid, bool(marks) and min(abs(t - x) for x in marks) > 0.06, "warning", "emphasis_off_word", f"{sid}: the emphasis of '{d['props'].get('text')}' at {t:g} s is not on a spoken word")
    meta = g.comp["meta"]
    has_audio = any(g.pdir.glob("audio.*"))                                  # a project made without its audio file (a test fixture) can still be checked, but it is said
    r.rule("audio_file", 8, None, not (g.pdir / str(meta.get("audio", "-"))).exists(), "error" if has_audio else "warning", "audio_missing", f"the composition refers to audio '{meta.get('audio')}' which is not in the project")
    last = g.comp["scenes"][-1]["end"] if g.comp["scenes"] else 0
    r.rule("duration_is_audio", 8, None, abs(last - meta.get("duration", 0)) > 0.25, "warning", "duration_mismatch", f"the last scene ends at {last:g} s, the audio is {meta.get('duration')} s")


# ---------- 9 Layout Validation ----------
def stage9(g: G) -> None:
    r, tall = g.run, g.tall
    for s in g.comp["scenes"]:
        sid = g.sid(s)
        texts = [(t["text"], t["drawn_box"]) for t in ((g.ms.get(s["id"]) or {}).get("texts") or []) if t.get("drawn_box")]
        for text, db in texts:
            r.rule("text_in_safe_area", 9, sid, _outside(db, g.lim), "warning", "layout_out_of_bounds", f"{sid}: the text '{text}' is drawn outside the safe area")
        nodes = []
        for l in s["layers"]:
            if l["type"] == "motion_scene":
                for it in l.get("items", []):
                    b = _item_box(it, tall)
                    if it.get("bleed") or not b or b[2] * b[3] >= 0.5 or it.get("kind", "gfx") != "gfx" or g.reg["graphic"].get(it["preset"], {}).get("category") == FRAME:
                        continue
                    rect = _box_rect(b)
                    r.rule("graphic_in_safe_area", 9, sid, _outside(rect, g.lim), "warning", "layout_out_of_bounds", f"{sid}: '{it['preset']}' reaches outside the safe area")
                    for text, db in texts:
                        r.rule("graphic_clear_of_text", 9, sid, _share(rect, db) > 0.25, "warning", "layout_overlap", f"{sid}: '{it['preset']}' lies on the text '{text}'")
            elif l.get("elementId") and l["type"] in ("shape", "icon"):
                rect = rect_of_layer(l, g.W, g.H)
                if rect:
                    nodes.append((l["elementId"], rect))
                    r.rule("node_in_safe_area", 9, sid, _outside(rect, g.lim), "warning", "layout_out_of_bounds", f"{sid}: {l['elementId']} reaches outside the safe area")
                    for text, db in texts:
                        r.rule("node_clear_of_text", 9, sid, _share(rect, db) > 0.02, "warning", "layout_overlap", f"{sid}: {l['elementId']} lies on the text '{text}'")
        for a in range(len(nodes)):
            for b in range(a + 1, len(nodes)):
                r.rule("nodes_apart", 9, sid, _share(nodes[a][1], nodes[b][1]) > 0.05, "warning", "layout_overlap", f"{sid}: {nodes[a][0]} and {nodes[b][0]} overlap")


# ---------- 10 Code Validation ----------
def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def stage10(g: G, val: dict) -> None:
    r = g.run
    r.rule("renderer_schema", 10, None, val.get("zod") is not True and not val.get("not_run"), "error", "schema_invalid", f"the composition does not satisfy the renderer's schema: {val.get('zod')}")
    code = [x for x in _strings(g.comp) if mp.CODE_LIKE.search(x)]
    r.rule("no_code", 10, None, bool(code), "error", "schema_invalid", f"the composition contains code-like text: {code[:2]}")
    for s in g.comp["scenes"]:
        sid = g.sid(s)
        for l in s["layers"]:
            if l["type"] == "motion_text":
                if l.get("k") is not None:
                    r.rule("intensity_range", 10, sid, not 0.3 <= l["k"] <= 2.0, "warning", "unsupported_parameter", f"{sid}: the intensity {l['k']} of '{l.get('text')}' is outside 0.3-2.0")
                for key in ("dur", "exitDur"):
                    if l.get(key) is not None:
                        r.rule("min_duration", 10, sid, l[key] < mp.MIN_DUR - 1e-6, "warning", "unsupported_parameter", f"{sid}: {key} {l[key]} s of '{l.get('text')}' is shorter than {mp.MIN_DUR} s")
            elif l["type"] == "motion_scene":
                for it in l.get("items", []):
                    r.rule("speed_range", 10, sid, not 0.5 <= (it.get("speed") or 1) <= 2, "warning", "unsupported_parameter", f"{sid}: the pace {it.get('speed')} of '{it['preset']}' is outside 0.5-2")


# ---------- 12 Error Repair (in memory, bounded) ----------
def problems(g: G) -> list[tuple]:
    """What the repair can fix: a time outside the scene, a box outside the safe area (never a text, never a diagram node, never a frame)."""
    out = []
    for s in g.comp["scenes"]:
        for l in s["layers"]:
            if l["type"] == "motion_text":
                if l.get("at") is not None and not s["start"] - EPS <= l["at"] <= s["end"] + EPS:
                    out.append(("time", s["id"], l, "at"))
            elif l["type"] == "motion_scene":
                for it in l.get("items", []):
                    for key in ("start", "end"):
                        if it.get(key) is not None and not s["start"] - EPS <= it[key] <= s["end"] + EPS:
                            out.append(("time", s["id"], it, key))
                    b = _item_box(it, g.tall)
                    if (not it.get("bleed") and b and b[2] * b[3] < 0.5 and g.reg["graphic"].get(it["preset"], {}).get("category") != FRAME and _outside(_box_rect(b), g.lim)
                            and b[2] <= 1 - 2 * SAFE and b[3] <= g.lim - SAFE):
                        out.append(("box", s["id"], it, None))
    return out


def repair(g: G, repairs: list[dict]) -> int:
    """At most MAX_REPAIR_PASSES passes; every change is recorded (what, from, to, why). Returns the number of passes used. Anything else stays a finding."""
    for n in range(MAX_REPAIR_PASSES):
        found = problems(g)
        if not found:
            return n
        for kind, scene_id, obj, key in found:
            sid = f"scene_{scene_id:02d}"
            s = next(x for x in g.comp["scenes"] if x["id"] == scene_id)
            if kind == "time":
                old = obj[key]
                obj[key] = round(min(max(old, s["start"]), s["end"]), 3)
                repairs.append({"scene": sid, "layer": obj.get("preset") or obj.get("text"), "field": key, "from": old, "to": obj[key], "reason": "a time outside the scene is clamped into it"})
            else:
                field = "boxTall" if g.tall and obj.get("boxTall") else "box"
                b = list(obj[field])
                nb = [round(min(max(b[0], SAFE), 1 - SAFE - b[2]), 3), round(min(max(b[1], SAFE), g.lim - b[3]), 3), b[2], b[3]]
                obj[field] = nb
                repairs.append({"scene": sid, "layer": obj["preset"], "field": field, "from": b, "to": nb, "reason": "a box outside the safe area is moved inside it (same size)"})
    return MAX_REPAIR_PASSES
