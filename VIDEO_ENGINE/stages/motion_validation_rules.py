"""The rules of the 12 Motion & Timeline Validation stages (backend/motion_validation.py). Every function `stage_<id>(x, v)` reads the artifacts through `X` and records its checks in `v`;
none of them writes a file or calls a model. Rule ids are those of the roadmap's rule catalog (05_RULE_CATALOG.md). Where Motion Generation already has the same rule, the check is made
again here from the artifacts on disk (not from the generation report's verdict), with the renderer's own geometry where it is known and an honest "unknown" where it is not."""
from __future__ import annotations

import json
import wave
from pathlib import Path

from SYSTEM.core import media_kinds as mk

from . import config, motion_generation as mg, motion_gen_report as mgr, motion_planning as mp, scene_segmentation, store, visual_planning
from .motion_gen_rules import SAFE, _box_rect, _item_box, _outside, _share
from .motion_validation import EMPHASIS_TOLERANCE_S, EPS, V, sha

OWNER_OF = {"project": "project", "segmentation": "scene_segmentation", "visual_plan": "visual_planning", "motion_plan": "motion_planning", "motion_planning": "motion_planning",
            "motion_generation": "motion_generation", "motion_template_selection": "motion_template_selection", "motion_animation": "motion_animation", "composition": "motion_generation", "fixes": "motion_planning"}
FRAME = "frame"


def sid_of(scene_id: int) -> str:
    return f"scene_{scene_id:02d}"


class X:
    """The inputs of one validation, read once and never written."""

    def __init__(self, pdir: Path, aspect: str) -> None:
        from . import motion_validation as mv
        self.pdir, self.aspect, self.tall = pdir, aspect, aspect == "9:16"
        self.files = mv.input_files(pdir, aspect)
        self.bad: dict[str, str] = {}
        raw: dict = {}
        for role, p in self.files.items():
            if p.exists():
                try:
                    raw[role] = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError) as e:
                    self.bad[role] = str(e)[:160]
        self.vp, self.seg, self.mplan, self.comp, self.fixes = raw.get("visual_plan"), raw.get("segmentation"), raw.get("motion_plan"), raw.get("composition"), raw.get("fixes")
        self.plan = mp.load(pdir, aspect) if "motion_planning" in raw else None
        self.gen = mgr.load(pdir, aspect) if "motion_generation" in raw else None
        # A project whose Visual Plan had no Scene Segmentation to follow (its `source_segmentation` is null: the scene plan is the only source of the scene boundaries) is checked, but said: never silently.
        self.derived = bool(self.plan and self.vp is not None and self.seg is None and not self.vp.get("source_segmentation"))
        if "motion_planning" in raw:
            try:
                mp.PlanM.model_validate(raw["motion_planning"])
            except Exception as e:                                                 # pydantic ValidationError: the plan does not follow its contract
                self.bad["motion_planning"] = f"schema: {str(e)[:140]}"
        self.images = store.uses_images(pdir)
        meta = (self.comp or {}).get("meta", {})
        self.fps, self.W, self.H = int(meta.get("fps") or mp.FPS), meta.get("width", 1920), meta.get("height", 1080)
        self.lim = 1 - config.SAFE_AREA["portrait_ui_bottom"] if self.tall else 1 - SAFE
        self.words = mg.words(pdir)
        self._reg, self._reg_err = None, None
        self.ps_by_id = {s["plan_scene_id"]: s for s in (self.plan or {}).get("scenes", [])}
        self.ps_by_vid = {s["scene_id"]: s for s in (self.plan or {}).get("scenes", [])}
        self.ms_by_id = {s["id"]: s for s in (self.mplan or {}).get("scenes", [])}
        self.element_summary: dict = {}
        self.element_rows: list[dict] = []
        self.preview_samples: list[dict] = []
        self.preview_levels: dict = {}
        self._desc: dict | None = None
        self._anim: dict | None = None

    def custom_code(self, s: dict) -> tuple[dict | None, str | None] | None:
        """For a scene drawn by generated code: (its Motion Animation manifest entry, its TSX source or None when the file is missing). None for any other scene."""
        if not any(l["type"] == "custom_scene" for l in s["layers"]):
            return None
        if self._anim is None:
            from . import motion_animation
            self._anim = {m["scene_id"]: m for m in (motion_animation.load_animation(self.pdir, self.aspect) or {}).get("scenes", [])}
        m = self._anim.get(s["id"])
        f = self.pdir / "generated_motion" / Path(m["source_path"]).name if m else None
        return m, (f.read_text(encoding="utf-8") if f and f.exists() else None)

    @property
    def reg(self):
        if self._reg is None and self._reg_err is None:
            try:
                self._reg = mp.registry()
            except Exception as e:                                                 # MotionError, or the node tool is missing
                self._reg_err = str(e)[:200]
        return self._reg

    @property
    def desc(self) -> dict[int, list[dict]]:
        if self._desc is None:
            self._desc = {s["id"]: mg.descriptors(s, self.ps_by_id.get(s["id"]), self.fps) for s in self.scenes()}
        return self._desc

    def scenes(self) -> list[dict]:
        return (self.comp or {}).get("scenes", [])

    def cfg(self) -> dict:
        meta = (self.comp or {}).get("meta", {})
        return {"aspect_ratio": self.aspect, "width": self.W, "height": self.H, "fps": self.fps, "duration_seconds": meta.get("duration"), "mode": "image" if self.images else "motion_only",
                "motion_speed": meta.get("motionSpeed")}

    def inputs_block(self, digests: dict) -> dict:
        return {"visual_plan_fingerprint": (self.vp or {}).get("source_fingerprint"), "scene_segmentation_fingerprint": (self.seg or {}).get("source_fingerprint"),
                "motion_plan_fingerprint": (self.plan or {}).get("source_fingerprint"), "motion_generation_fingerprint": (self.gen or {}).get("source_fingerprint"),
                "composition_fingerprint": digests.get("composition"), "renderer_registry_fingerprint": digests.get("renderer"),
                "artifacts": {k: {"file": p.name, "sha": digests.get(k)} for k, p in self.files.items()}, "audio": digests.get("audio"), "transcript_words": digests.get("words")}

    def preview_block(self) -> list[dict]:
        return self.preview_samples

    def text_layers(self, s: dict) -> list[dict]:
        return [l for l in s["layers"] if l["type"] == "motion_text"]

    def planned_text(self, scene_id: int, text: str) -> dict | None:
        return next((t for t in (self.ms_by_id.get(scene_id) or {}).get("texts", []) if mp.norm(t["text"]) == mp.norm(text)), None)


def _fin(*vals) -> bool:
    return all(isinstance(x, (int, float)) and x == x and abs(x) != float("inf") for x in vals)


def _strings(x) -> list[str]:
    out: list[str] = []
    stack = [x]
    while stack:
        y = stack.pop()
        if isinstance(y, str):
            out.append(y)
        elif isinstance(y, dict):
            stack.extend(y.values())
        elif isinstance(y, list):
            stack.extend(y)
    return out


def _in_frame(r) -> bool:
    return r[0] >= -0.001 and r[1] >= -0.001 and r[2] <= 1.001 and r[3] <= 1.001


# ---------- 1 Input Reader & Provenance ----------
def stage_input_provenance(x: X, v: V) -> None:
    S = "input_provenance"
    for role, p in x.files.items():
        if role in ("fixes", "motion_template_selection", "motion_animation") and not p.exists():
            continue                                                               # optional / backward compatible for legacy projects
        ok = p.exists()
        legacy = x.derived and role == "segmentation"
        v.check(S, "input.exists", ok, "warning" if legacy else "blocker", f"{p.name} is missing" + (" (this project has no Scene Segmentation: the scene boundaries are the scene plan's, not checked against the narration)" if legacy else ""),
                None, p.name, {"file": p.name, "legacy_derived": legacy}, OWNER_OF[role], f"make it in {OWNER_OF[role].replace('_', ' ')}")
        if ok:
            v.check(S, "input.parseable", role not in x.bad, "blocker", f"{p.name} cannot be read as its schema: {x.bad.get(role)}", None, p.name, {"file": p.name, "error": x.bad.get(role)}, OWNER_OF[role],
                    f"run {OWNER_OF[role].replace('_', ' ')} again")
    v.check(S, "input.exists", next(iter(x.pdir.glob("audio.*")), None) is not None, "blocker", "the project has no audio file", None, "audio.*", {}, "project", "upload the audio")
    v.check(S, "input.exists", bool(x.words), "warning", "no transcript words: the emphasis timing cannot be compared with the spoken words", None, "transcript", {}, "project", "run the Audio Analyzer")
    if not (x.vp and x.plan and x.gen and x.comp and (x.seg or x.derived) and x.mplan) or x.bad:
        return                                                                     # a missing or unreadable file is already a blocker: the rest would only repeat it
    mode = "image" if x.images else "motion_only"
    docs = {"visual_plan": (x.vp, "visual_planning"), "motion_plan": (x.plan, "motion_planning"), "motion_generation": (x.gen, "motion_generation")}
    for name, (doc, owner) in docs.items():
        pr = doc["project"]
        label = name.replace("_", " ")
        v.check(S, "input.project_match", pr.get("aspect_ratio") == x.aspect, "blocker", f"the {label} is for {pr.get('aspect_ratio')} but the project is {x.aspect}", None, f"{name}:aspect", {"found": pr.get("aspect_ratio")}, owner,
                "run the stage for this aspect ratio")
        if name != "visual_plan":
            v.check(S, "input.project_match", pr.get("mode") == mode, "blocker", f"the {label} is '{pr.get('mode')}' but Use Images says '{mode}'", None, f"{name}:mode", {"found": pr.get("mode")}, owner, "run the stage again")
        v.check(S, "input.project_match", int(pr.get("fps", 0)) == x.fps and pr.get("width") == x.W and pr.get("height") == x.H, "blocker",
                f"the {label} says {pr.get('width')}x{pr.get('height')} at {pr.get('fps')} fps but the composition is {x.W}x{x.H} at {x.fps} fps", None, f"{name}:size", {"found": pr}, owner, "run the stage again")
        v.check(S, "input.parseable", doc.get("schema_version") == {"visual_plan": visual_planning.SCHEMA, "motion_plan": mp.SCHEMA, "motion_generation": mg.SCHEMA}[name], "blocker",
                f"the {label} has schema {doc.get('schema_version')}, which this validator does not support", None, f"{name}:schema", {}, owner, "run the stage again")
    v.check(S, "input.project_match", (x.H > x.W) == x.tall, "blocker", f"the composition is {x.W}x{x.H} but the project is {x.aspect}", None, "composition:aspect", {}, "motion_generation", "build again")
    v.check(S, "input.approved_source", not x.vp["validation"]["errors"], "blocker", f"the Visual Plan has {len(x.vp['validation']['errors'])} blocking error(s)", None, "visual_plan", {"first": (x.vp["validation"]["errors"] or [None])[0]},
            "visual_planning", "fix it in Visual Planning")
    v.check(S, "input.approved_source", not x.plan["validation"]["errors"], "blocker", f"the motion plan has {len(x.plan['validation']['errors'])} blocking error(s)", None, "motion_planning", {"first": (x.plan["validation"]["errors"] or [None])[0]},
            "motion_planning", "fix it in Motion Planning")
    v.check(S, "input.approved_source", not x.gen["validation"]["errors"] and x.gen["output"].get("persisted") is True, "blocker", f"Motion Generation has {len(x.gen['validation']['errors'])} blocking error(s) or did not persist its output", None,
            "motion_generation", {"first": (x.gen["validation"]["errors"] or [None])[0]}, "motion_generation", "fix it in Motion Generation")


# ---------- 2 Fingerprint & Freshness ----------
def stage_fingerprint_freshness(x: X, v: V) -> None:
    S, pdir = "fingerprint_freshness", x.pdir
    vp_now = visual_planning.load(pdir)
    v.check(S, "input.fingerprint_current", bool(vp_now) and not vp_now.get("stale"), "blocker", "the Visual Plan is out of date (its sources changed): run Visual Planning again", None, "visual_plan", {"stored": x.vp.get("source_fingerprint")},
            "visual_planning", "run Visual Planning again")
    if x.seg:
        v.check(S, "input.fingerprint_current", scene_segmentation.load_fresh(pdir) is not None, "blocker", "Scene Segmentation is out of date (the transcript changed): run it again", None, "segmentation", {"stored": x.seg.get("source_fingerprint")},
                "scene_segmentation", "run Scene Segmentation again")
    else:
        v.skip(S, "input.fingerprint_current", "Scene Segmentation was not run for this project: its freshness is not applicable", None, "segmentation", {}, "scene_segmentation")
    v.check(S, "input.fingerprint_current", not x.plan.get("stale"), "blocker", "the motion plan is out of date (the Visual Plan, the motion library or the rules changed): run Motion Planning again", None, "motion_planning",
            {"stored": x.plan.get("source_fingerprint"), "now": mp.fingerprint(pdir, x.aspect)}, "motion_planning", "run Motion Planning again")
    if (x.plan.get("visual_plan") or {}).get("file"):
        v.check(S, "input.fingerprint_current", (x.plan.get("visual_plan") or {}).get("fingerprint") == x.vp.get("source_fingerprint"), "blocker", "the motion plan was made from another Visual Plan than the current one", None,
                "motion_planning:visual_plan", {"plan_used": (x.plan.get("visual_plan") or {}).get("fingerprint"), "visual_plan_now": x.vp.get("source_fingerprint")}, "motion_planning", "run Motion Planning again")
    else:
        v.skip(S, "input.fingerprint_current", "the motion plan was made without a stored Visual Plan (from the scene plan): which Visual Plan it followed cannot be compared", None, "motion_planning:visual_plan", {}, "motion_planning")
    v.check(S, "input.fingerprint_current", not x.gen.get("stale"), "blocker", "the Motion Generation report is out of date: run Motion Generation again", None, "motion_generation",
            {"stored": x.gen.get("source_fingerprint"), "now": mgr.fingerprint(pdir, x.aspect)}, "motion_generation", "run Motion Generation again")
    v.check(S, "input.fingerprint_current", x.gen["input"].get("plan_fingerprint") == x.plan.get("source_fingerprint"), "blocker", "Motion Generation was built from another motion plan than the current one", None, "motion_generation:plan",
            {"built_from": x.gen["input"].get("plan_fingerprint"), "plan_now": x.plan.get("source_fingerprint")}, "motion_generation", "run Motion Generation again")
    v.check(S, "input.fingerprint_current", x.gen["input"].get("motion_plan_sha") == sha(x.files["motion_plan"].read_bytes()), "blocker", "motion_plan.json changed after Motion Generation read it", None, "motion_generation:motion_plan_sha", {},
            "motion_generation", "run Motion Generation again")
    v.check(S, "composition.inputs_current", mg.sha(mg.dumps(x.comp)) == x.gen["output"].get("composition_sha"), "blocker", "composition.json is not the composition Motion Generation validated and wrote", None, "composition",
            {"report": x.gen["output"].get("composition_sha"), "disk": mg.sha(mg.dumps(x.comp))}, "motion_generation", "run Motion Generation again")
    v.check(S, "input.fingerprint_current", x.plan.get("version") == mp.VERSION and x.gen.get("version") == mg.VERSION, "blocker", "a stage was made by an older version of its rules", None, "rule_versions",
            {"plan": x.plan.get("version"), "generation": x.gen.get("version"), "now": [mp.VERSION, mg.VERSION]}, "motion_generation", "run the stage again")


# ---------- 3 Scene Mapping & Coverage ----------
def stage_scene_mapping(x: X, v: V) -> None:
    S = "scene_mapping"
    seg, vps, pls, mss, cs, gs = (x.seg or {}).get("scenes", []), x.vp["scenes"], x.plan["scenes"], x.mplan["scenes"], x.scenes(), x.gen["scenes"]
    counts = {"visual_plan": len(vps), "motion_plan": len(pls), "motion_plan.json": len(mss), "composition": len(cs), "generation": len(gs), **({"segmentation": len(seg)} if x.seg else {})}
    v.check(S, "scene.count_match", len(set(counts.values())) == 1, "error", f"scene counts differ: {counts}", None, "scenes", {"counts": counts}, "motion_planning", "make every stage follow the Scene Segmentation scenes")
    for name, ids in (("composition", [s["id"] for s in cs]), ("visual plan", [s["scene_id"] for s in vps]), ("motion plan", [s["scene_id"] for s in pls])):
        v.check(S, "scene.id_unique", len(ids) == len(set(ids)), "error", f"two scenes of the {name} have the same id", None, name, {"ids": ids}, "motion_planning", "run the stage again")
    v.check(S, "scene.order_preserved", [s["plan_scene_id"] for s in pls] == [s["id"] for s in cs] == sorted(s["id"] for s in cs) and [s["scene_id"] for s in pls] == [s["scene_id"] for s in vps], "error",
            "the scene order differs between the Visual Plan, the motion plan and the composition", None, "scenes", {"visual_plan": [s["scene_id"] for s in vps], "composition": [s["id"] for s in cs]}, "motion_generation", "build again")
    by_seg = {s["scene_id"]: s for s in seg}
    claimed: dict[str, str] = {}
    if not x.seg:
        v.skip(S, "scene.source_map_unique", "the scenes are not checked against the narration: Scene Segmentation was not run for this project", None, "segmentation", {}, "scene_segmentation")
    for vs in vps if x.seg else []:
        sid, sm = vs["scene_id"], vs["source_mapping"]
        c = by_seg.get(sm.get("segmentation_scene_id"))
        v.check(S, "scene.source_map_unique", c is not None and sm.get("segmentation_scene_id") not in claimed, "error", f"{sid}: its Scene Segmentation scene {sm.get('segmentation_scene_id')} is missing or used by two scenes", sid,
                "source_mapping", {"maps_to": sm.get("segmentation_scene_id"), "already_used_by": claimed.get(sm.get("segmentation_scene_id"))}, "visual_planning", "run Visual Planning again")
        claimed.setdefault(sm.get("segmentation_scene_id"), sid)
        if c is None:
            continue
        v.check(S, "scene.narration_mapped", abs(sm["plan_start"] - c["start_time"]) <= EPS and abs(sm["plan_end"] - c["end_time"]) <= EPS, "error",
                f"{sid}: its times {sm['plan_start']:g}-{sm['plan_end']:g} s are not the canonical {c['start_time']:g}-{c['end_time']:g} s of its narration", sid, "plan_times",
                {"visual_plan": [sm["plan_start"], sm["plan_end"]], "segmentation": [c["start_time"], c["end_time"]]}, "visual_planning", "run Visual Planning again")
        v.check(S, "scene.narration_mapped", sorted(vs.get("source_segment_ids", [])) == sorted(c.get("source_segment_ids", [])), "error", f"{sid}: its source segments differ from those of Scene Segmentation", sid, "source_segment_ids",
                {"visual_plan": vs.get("source_segment_ids"), "segmentation": c.get("source_segment_ids")}, "visual_planning", "run Visual Planning again")
        nar = (vs.get("narration") or {}).get("text") or ""
        v.check(S, "scene.narration_mapped", bool(nar.strip()) and mp.norm(nar) == mp.norm(c.get("transcript") or nar), "error", f"{sid}: the narration of the Visual Plan is not the narration of Scene Segmentation", sid, "narration", {},
                "visual_planning", "run Visual Planning again")
        ps = x.ps_by_vid.get(sid)
        if ps:
            t = ps["timing"]
            v.check(S, "scene.narration_mapped", ps["plan_scene_id"] == vs["plan_scene_id"] and abs(t.get("canonical_start", -1) - c["start_time"]) <= EPS and abs(t.get("canonical_end", -1) - c["end_time"]) <= EPS
                    and t.get("source") == "scene_segmentation", "error", f"{sid}: the motion plan's canonical times differ from Scene Segmentation", sid, "motion_plan_times",
                    {"motion_plan": [t.get("canonical_start"), t.get("canonical_end")], "segmentation": [c["start_time"], c["end_time"]]}, "motion_planning", "run Motion Planning again")
            gap = sm.get("gap_after_seconds")
            end_ok = abs((sm["timeline_end"] - sm["plan_end"]) - gap) <= EPS and abs((t["end"] - t["canonical_end"]) - gap) <= EPS if gap is not None else abs(sm["timeline_end"] - (x.seg.get("audio_duration_seconds") or sm["timeline_end"])) <= 0.02
            v.check(S, "scene.pause_policy", end_ok and abs(t["end"] - sm["timeline_end"]) <= EPS, "error",
                    f"{sid}: the pause after the scene ({'until the end of the audio' if gap is None else f'{gap:g} s'}) is not held on the timeline as planned", sid, "pause",
                    {"gap_after_seconds": gap, "timeline_end": sm["timeline_end"], "motion_plan_end": t["end"], "audio_duration": x.seg.get("audio_duration_seconds")}, "motion_planning", "run Motion Planning again")
    for c in seg:
        v.check(S, "scene.coverage_complete", c["scene_id"] in claimed, "error", f"Scene Segmentation scene {c['scene_id']} has no planned scene", c["scene_id"], "coverage", {}, "visual_planning", "run Visual Planning again")
    cids = {s["id"] for s in cs}
    for ps in pls:
        v.check(S, "scene.coverage_complete", ps["plan_scene_id"] in cids, "error", f"{ps['scene_id']} is planned but not in the composition", ps["scene_id"], "composition", {}, "motion_generation", "run Motion Generation again")


# ---------- 4 Timing & Frame Integrity ----------
def stage_timing_frame(x: X, v: V) -> None:
    S, fps = "timing_frame", x.fps
    meta = x.comp.get("meta", {})
    v.check(S, "timing.non_negative", _fin(meta.get("duration"), fps) and fps > 0 and meta["duration"] > 0, "error", "the composition has no valid duration or frame rate", None, "meta", {"fps": meta.get("fps"), "duration": meta.get("duration")},
            "motion_generation", "build again")
    v.check(S, "timing.seconds_frames_consistent", fps == int(x.plan["project"]["fps"]) == int(x.gen["project"]["fps"]), "error",
            f"the frame rates differ: composition {fps}, plan {x.plan['project']['fps']}, generation {x.gen['project']['fps']}", None, "fps", {}, "motion_generation", "build again")
    prev_end = None
    for s in x.scenes():
        sid = sid_of(s["id"])
        times = [s["start"], s["end"]] + [l.get("at") for l in s["layers"] if l.get("at") is not None] + [l.get("until") for l in s["layers"] if l.get("until") is not None]
        times += [it.get(k) for l in s["layers"] if l["type"] == "motion_scene" for it in l.get("items", []) for k in ("start", "end") if it.get(k) is not None]
        v.check(S, "timing.non_negative", _fin(*times) and min(times) >= 0, "error", f"{sid}: a time is negative or not a number", sid, "times", {}, "motion_generation", "build again")
        v.check(S, "timing.duration_valid", s["end"] > s["start"], "error", f"{sid}: it ends ({s['end']:g} s) before it starts ({s['start']:g} s)", sid, "scene", {"start": s["start"], "end": s["end"]}, "motion_planning", "run Motion Planning again")
        ps = x.ps_by_id.get(s["id"])
        if ps:
            t = ps["timing"]
            v.check(S, "timing.seconds_frames_consistent", t["start_frame"] == mp.fr(t["start"], fps) and t["end_frame"] == mp.fr(t["end"], fps) and t["end_frame"] > t["start_frame"], "error",
                    f"{sid}: the plan's frames do not follow the one seconds-to-frames rule", sid, "scene_frames", {"start": t["start"], "start_frame": t["start_frame"], "end": t["end"], "end_frame": t["end_frame"]},
                    "motion_planning", "run Motion Planning again")
            v.check(S, "timing.no_prohibited_overlap", abs(t["start"] - s["start"]) <= EPS and abs(t["end"] - s["end"]) <= EPS, "error", f"{sid}: the composition has {s['start']:g}-{s['end']:g} s, the plan {t['start']:g}-{t['end']:g} s", sid,
                    "scene_interval", {"composition": [s["start"], s["end"]], "plan": [t["start"], t["end"]]}, "motion_generation", "build again")
            gap = t.get("gap_after_seconds")                                       # the last scene has none: its tail is held until the end of the audio
            held = (abs((s["end"] - t["canonical_end"]) - gap) <= EPS if gap is not None else abs(s["end"] - meta.get("duration", s["end"])) <= 0.02) if "canonical_end" in t and not x.derived else True      # a project without Scene Segmentation has no canonical narration end to hold
            v.check(S, "timing.gaps_preserved", held, "error", f"{sid}: the planned pause ({'until the end of the audio' if gap is None else f'{gap:g} s'}) is not held at the end of the scene", sid, "gap",
                    {"gap_after_seconds": gap, "scene_end": s["end"], "canonical_end": t["canonical_end"], "audio_duration": meta.get("duration")}, "motion_generation", "build again")
        if prev_end is not None:
            v.check(S, "timing.no_prohibited_overlap", abs(s["start"] - prev_end) <= EPS, "error", f"{sid}: starts at {s['start']:g} s, the previous scene ends at {prev_end:g} s (scenes follow without overlap or an unplanned gap)", sid, "boundary",
                    {"previous_end": prev_end, "start": s["start"]}, "motion_generation", "build again")
        prev_end = s["end"]
        f0, f1 = mp.fr(s["start"], fps), mp.fr(s["end"], fps)
        for d in x.desc[s["id"]]:
            if d.get("missing"):
                continue
            # the descriptor keeps its seconds to 3 decimals but its frames from the unrounded time: a time that lies on a rounding boundary may differ by ONE frame, never more
            ok = abs(d["start_frame"] - mp.fr(d["start"], fps)) <= 1 and abs(d["end_frame"] - mp.fr(d["end"], fps)) <= 1 and d["duration_frames"] == max(0, d["end_frame"] - d["start_frame"])
            v.check(S, "timing.seconds_frames_consistent", ok, "error", f"{sid}: {d['element_id']} has frames that do not follow the one rule", sid, d["descriptor_id"], {"start": d["start"], "end": d["end"],
                    "frames": [d["start_frame"], d["end_frame"]]}, "motion_generation", "build again")
            v.check(S, "timing.within_parent", d["start_frame"] >= f0 - 1 and d["end_frame"] <= f1 + 1 and d["end_frame"] >= d["start_frame"], "error",
                    f"{sid}: {d['element_id']} runs frames {d['start_frame']}-{d['end_frame']}, outside its scene {f0}-{f1}", sid, d["descriptor_id"], {"element_frames": [d["start_frame"], d["end_frame"]], "scene_frames": [f0, f1]},
                    "motion_generation", "build again")
        for l in x.text_layers(s):
            planned = x.planned_text(s["id"], l.get("text", ""))
            exit_s = l.get("exitDur") if l.get("exitDur") is not None else (planned or {}).get("exit_s") or 0
            enter_s = l.get("dur") if l.get("dur") is not None else (planned or {}).get("enter_s") or 0.5
            target = mp.norm(l.get("text", ""))[:40]
            if planned and planned.get("exit"):
                v.check(S, "timing.exit_exists", l.get("exitPreset") == planned["exit"] and (x.reg is None or l.get("exitPreset") in x.reg["exit"]), "error",
                        f"{sid}: the plan gives '{l.get('text')}' the exit '{planned['exit']}' but the composition has '{l.get('exitPreset')}'", sid, target, {"plan": planned["exit"], "composition": l.get("exitPreset")},
                        "motion_generation", "build again")
            t = {"until": l.get("until"), "exit_s": exit_s, "enter_s": enter_s, "text": l.get("text", "")}
            seen, need = mp.reading_end(t, s["end"]) - l.get("at", s["start"]), mp.reading_need(t)
            v.check(S, "timing.readability_before_exit", seen + EPS >= need, "warning", f"{sid}: '{l.get('text')}' is on screen {seen:.2f} s before it starts to leave, it needs {need:.2f} s", sid, target,
                    {"visible_seconds_before_exit": round(seen, 2), "needed_seconds": round(need, 2), "text_at": l.get("at"), "exit_starts": round(mp.reading_end(t, s["end"]), 2)}, "motion_planning",
                    "move the text earlier (Solve warnings) or lengthen the scene")


# ---------- 5 Element Completeness & Drawn Support ----------
def _built(pe: dict, ds: list[dict]) -> bool:
    """The same meaning as Motion Generation's Element Resolver: something in the composition draws the planned element."""
    kind, rid, eid = pe.get("registry_kind"), pe.get("registry_id"), pe["element_id"]
    if pe["type"] == "background" or kind == "layer":
        return True
    if any(d.get("component_id") in ("custom_scene", "custom_motion") for d in ds):
        return True
    if kind == "text_preset":
        return any(d["element_id"] == eid or (d["component_id"] == "motion_text" and d["preset_id"] == rid) for d in ds)
    if kind == "primitive":
        return any(d["element_id"] == eid for d in ds)
    if kind == "graphic_preset":
        return any(d["preset_id"] == rid for d in ds)
    if kind == "icon":
        return any(d["component_id"] == "icon" for d in ds)
    return True


def stage_element_completeness(x: X, v: V) -> None:
    S = "element_completeness"
    accepted = set((x.fixes or {}).get("accepted", []))
    rows, req_nd, opt_nd, approx = [], 0, 0, 0
    for vs in x.vp["scenes"]:
        sid = vs["scene_id"]
        pls = x.ps_by_vid.get(sid)
        if pls is None:
            continue
        ds = x.desc.get(pls["plan_scene_id"], [])
        cs = next((s for s in x.scenes() if s["id"] == pls["plan_scene_id"]), None)
        owners = {l.get("elementId") for l in (cs or {}).get("layers", []) if l.get("elementId")}
        els = {(e.get("source_element_id") or e["element_id"]): e for e in pls["elements"]}
        # without Scene Segmentation the elements are the motion plan's own (it resolved them from the Visual Plan): they are checked against the composition
        for ve in ([{"element_id": e["element_id"], "type": e["type"], "required": e["required"]} for e in pls["elements"]] if x.derived else vs["elements"]):
            eid, req = ve["element_id"], bool(ve["required"])
            pe = els.get(eid)
            state, why = "drawn", "drawn"
            if pe is None:
                state, why = "missing", "the motion plan has no element for it"
                v.check(S, "element.no_orphan_required", not req, "blocker", f"{sid}: the required element {eid} is in the Visual Plan but not in the motion plan", sid, eid, {"visual_plan_required": True, "in_motion_plan": False},
                        "motion_planning", "run Motion Planning again")
            else:
                st = pe["status"]
                if _built(pe, ds) or st in ("resolved", "approximate"):
                    drawn = _built(pe, ds)
                    state = ("approximate" if st == "approximate" else "drawn") if drawn else "missing"
                    why = "drawn" if drawn else "the plan resolved it but the composition has no layer for it"
                elif pe["element_id"] in owners or eid in owners:
                    state, why = "approximate", "drawn as a stand-in by its own layer"
                else:
                    state = "accepted_not_drawn" if sid in accepted else "missing"
                    why = (pe.get("fallback") or {}).get("reason") or "recorded fallback"
            if state in ("missing", "accepted_not_drawn") and not req:
                state = "optional_missing"
            if pe is not None and req:
                if state in ("missing", "accepted_not_drawn"):
                    v.check(S, "element.required_has_drawable", False, "blocker", f"{sid}: {eid} is a required visual with no drawable representation in the current composition"
                            + (" (accepted in Solve warnings, which does not draw it)" if state == "accepted_not_drawn" else ""), sid, eid,
                            {"visual_plan_required": True, "composition_layer_found": False, "plan_status": pe["status"], "accepted_in_solve_warnings": sid in accepted, "reason": why}, "motion_generation",
                            "implement a supported drawable representation for it, or record an explicit authorized exception")
                else:
                    v.check(S, "element.required_has_drawable", True, "blocker", "", sid, eid)
            if state == "optional_missing":
                v.skip(S, "element.optional_missing_classified", f"{sid}: the optional element {eid} is not drawn ({why})", sid, eid, {"visual_plan_required": False}, "motion_generation")
                opt_nd += 1
            if state == "approximate":
                v.check(S, "element.approximation_disclosed", bool(pe and (pe.get("note") or pe.get("fallback") or pe["status"] == "approximate")), "warning", f"{sid}: {eid} is drawn as a stand-in and the plan does not say so", sid, eid, {},
                        "motion_planning", "run Motion Planning again")
                approx += 1
            if req and state in ("missing", "accepted_not_drawn"):
                req_nd += 1
            rows.append({"scene_id": sid, "element_id": eid, "type": ve["type"], "required": req, "state": state, "plan_status": pe["status"] if pe else None, "why": why})
        ids = {e["element_id"] for e in pls["elements"]} | {d["element_id"] for d in ds}
        acts = {a["action_id"] for a in pls.get("sequence", [])}
        for a in pls.get("sequence", []):
            v.check(S, "element.reference_resolves", a["target"] in ids and all(d in acts for d in a.get("depends_on", [])), "error", f"{sid}: the planned action {a['action_id']} points at {a['target']} or at an action that does not exist", sid, a["action_id"],
                    {"target": a["target"], "depends_on": a.get("depends_on")}, "motion_planning", "run Motion Planning again")
        for d in ds:
            if d.get("plan_action_id"):
                v.check(S, "element.reference_resolves", d["plan_action_id"] in acts and not d.get("missing"), "error", f"{sid}: the planned action {d['plan_action_id']} ({d['preset_id']}) is not built in the composition" if d.get("missing")
                        else f"{sid}: the layer {d['element_id']} points at an unknown planned action", sid, d["descriptor_id"], {"action": d["plan_action_id"]}, "motion_generation", "run Motion Generation again")
    x.element_rows = rows
    x.element_summary = {"scenes_expected": len((x.seg or x.vp)["scenes"]), "scenes_checked": len(x.vp["scenes"]), "required_not_drawn": req_nd, "optional_not_drawn": opt_nd, "approximate": approx,
                         "drawn": sum(1 for r in rows if r["state"] == "drawn"), "elements": len(rows)}


# ---------- 6 Animation & Preset Validity ----------
def stage_animation_preset(x: X, v: V) -> None:
    S = "animation_preset"
    reg = x.reg
    v.check(S, "animation.preset_supported", reg is not None, "blocker", f"the preset registry could not be read: {x._reg_err}", None, "registry", {}, "motion_generation", "check that Node and the Remotion folder work")
    for s in x.scenes():
        sid = sid_of(s["id"])
        ids = [d["descriptor_id"] for d in x.desc[s["id"]]]
        v.check(S, "animation.order_deterministic", ids == [d["descriptor_id"] for d in mg.descriptors(s, x.ps_by_id.get(s["id"]), x.fps)], "error", f"{sid}: the order of its animations changes between two reads", sid, "order", {},
                "motion_generation", "build again")
        v.check(S, "element.id_unique", len(ids) == len(set(ids)), "error", f"{sid}: two animations have the same id", sid, "descriptor_ids", {}, "motion_generation", "build again")
        owners: set[str] = set()
        for l in s["layers"]:
            if l.get("elementId"):
                v.check(S, "element.id_unique", l["elementId"] not in owners, "error", f"{sid}: {l['elementId']} is drawn by two layers (the owner is ambiguous)", sid, l["elementId"], {}, "motion_generation", "build again")
                owners.add(l["elementId"])
            if l["type"] == "motion_text":
                if reg:
                    for key, kind in (("preset", "text"), ("exitPreset", "exit"), ("emphasis", "emphasis")):
                        if l.get(key):
                            v.check(S, "animation.preset_supported", l[key] in reg[kind], "blocker", f"{sid}: '{l[key]}' is not a {kind} preset of the installed registry", sid, f"{kind}:{l[key]}", {}, "motion_generation", "build again")
                v.check(S, "animation.properties_supported", l.get("style") in mp.TEXT_STYLES and (l.get("k") is None or 0.3 <= l["k"] <= 2.0) and all(l.get(k) is None or l[k] >= mp.MIN_DUR - 1e-6 for k in ("dur", "exitDur")), "warning",
                        f"{sid}: the text '{l.get('text')}' has a style, intensity or duration the animation engine does not support", sid, mp.norm(l.get("text", ""))[:40],
                        {"style": l.get("style"), "k": l.get("k"), "dur": l.get("dur"), "exitDur": l.get("exitDur")}, "motion_generation", "build again")
            elif l["type"] == "motion_scene":
                for it in l.get("items", []):
                    if reg and it.get("kind", "gfx") == "gfx":
                        v.check(S, "animation.preset_supported", it["preset"] in reg["graphic"], "blocker", f"{sid}: '{it['preset']}' is not a graphic preset of the installed registry", sid, f"graphic:{it['preset']}", {}, "motion_generation", "build again")
                    v.check(S, "animation.properties_supported", 0.5 <= (it.get("speed") or 1) <= 2, "warning", f"{sid}: the pace {it.get('speed')} of '{it['preset']}' is outside 0.5-2", sid, f"speed:{it['preset']}", {}, "motion_generation", "build again")
            elif l["type"] in ("shape", "icon") and l.get("elementId") and reg:
                pid = f"shape:{l.get('kind')}" if l["type"] == "shape" else f"resource:{l['resource_id']}" if l.get("resource_id") else f"icon:{l.get('lucide')}"
                v.check(S, "animation.preset_supported", pid in reg["primitive"], "blocker", f"{sid}: '{pid}' is not a drawing primitive of the registry", sid, pid, {}, "motion_generation", "build again")
        for d in x.desc[s["id"]]:
            if not d.get("missing"):
                v.check(S, "animation.loop_valid", _fin(d["start"], d["end"]) and d["end"] > d["start"], "error", f"{sid}: {d['element_id']} has a duration of {d['end'] - d['start']:g} s", sid, d["descriptor_id"], {"start": d["start"], "end": d["end"]},
                        "motion_generation", "build again")
    from . import resource_library
    res = resource_library.check_composition(x.comp)                      # Resource Library: every used resource exists, is verified, matches its pinned hash and resolves locally (offline)
    for f in res:
        v.check(S, "animation.resource_resolves", False, "blocker", f["message"], None, f["resource_id"], {"code": f["code"], "where": f["where"]}, "resource_manager",
                "open the Resource Manager: verify or refresh the resource, then build again")
    if not res:
        v.check(S, "animation.resource_resolves", True, "blocker", "", None, None, {"used": len(resource_library.used_resources(x.comp))}, "resource_manager")
    code = [t for t in _strings(x.comp) + _strings(x.mplan) if mp.CODE_LIKE.search(t)]
    v.check(S, "animation.no_untrusted_execution", not code, "blocker", f"the plan or composition contains code-like text, which is never executed: {code[:1]}", None, "code_like", {"examples": code[:2]}, "motion_planning",
            "remove it from the plan")

    from . import motion_animation
    anim = motion_animation.load_animation(x.pdir, x.aspect)
    v.check(S, "codegen.manifest_valid", anim is not None and anim.get("status") == "generated" and anim.get("mode") == "custom_code",
            "blocker", "Motion Animation manifest is missing or not generated", None, "animation_manifest", {}, "motion_generation", "run Motion Animation again")

    if anim:
        for sc in anim.get("scenes", []):
            sid = sc.get("scene_id")
            spath = Path(sc.get("source_path", ""))
            v.check(S, "codegen.source_exists", spath.exists(), "blocker", f"{sid_of(sid)}: generated TSX source does not exist at {spath}", sid_of(sid), "source_file", {}, "motion_generation", "generate animation code")
            if spath.exists():
                computed_sha = motion_animation.file_sha256(spath)
                v.check(S, "codegen.hash_valid", computed_sha == sc.get("source_sha256"), "blocker", f"{sid_of(sid)}: source SHA-256 mismatch (modified on disk)", sid_of(sid), "sha256", {"expected": sc.get("source_sha256"), "computed": computed_sha}, "motion_generation", "rebuild animation code")
                source_content = spath.read_text(encoding="utf-8")
                prohibited = motion_animation.scan_prohibited_presets(source_content)
                v.check(S, "policy.no_prohibited_presets", len(prohibited) == 0, "blocker", f"{sid_of(sid)}: prohibited reusable preset(s) imported or referenced: {', '.join(prohibited)}", sid_of(sid), "prohibited_presets", {"prohibited": prohibited}, "motion_generation", "regenerate without prohibited presets")


# ---------- 7 Layout & Collision ----------
def _generated_code_layout(x: X, v: V, sid: str, code: str | None) -> None:
    """A scene drawn by generated code has no measured boxes: its source is inspected statically (safe-zone padding/centering, text size, contrast) by the same verifier Motion Animation uses."""
    S = "layout_collision"
    v.check(S, "layout.generated_code_present", code is not None, "error", f"{sid}: the generated scene code file is missing", sid, "scene_code", {}, "motion_generation", "build again")
    if code is None:
        return
    from SYSTEM.agents.video_generation_agents.motion_animation.animation_intelligence import VisualPreviewVerifier
    r = VisualPreviewVerifier().verify(code, aspect=x.aspect)
    ev = {"findings": r.findings}
    v.check(S, "layout.generated_code_safe_zone", r.safe_zone_passed, "warning", f"{sid}: the generated code has no safe-zone padding or centering", sid, "scene_code", ev, "motion_generation", "generate the scene again")
    v.check(S, "layout.generated_code_typography", r.typography_passed, "warning", f"{sid}: the generated code uses text smaller than the minimum size", sid, "scene_code", ev, "motion_generation", "generate the scene again")
    v.check(S, "layout.generated_code_contrast", r.contrast_passed, "warning", f"{sid}: the generated code sets no high-contrast text colour or shadow", sid, "scene_code", ev, "motion_generation", "generate the scene again")


def stage_layout_collision(x: X, v: V) -> None:
    S, tall = "layout_collision", x.tall
    ratio = x.W / x.H if x.H else 0
    v.check(S, "layout.aspect_compatible", abs(ratio - (9 / 16 if tall else 16 / 9)) < 0.01, "error", f"the composition is {x.W}x{x.H}, not {x.aspect}", None, "frame", {"width": x.W, "height": x.H}, "motion_generation", "build again")
    for s in x.scenes():
        sid = sid_of(s["id"])
        v.check(S, "layout.z_order_valid", all(_fin(l.get("z", 0)) for l in s["layers"]), "error", f"{sid}: a layer has no numeric z-order", sid, "z", {}, "motion_generation", "build again")
        if (cc := x.custom_code(s)) is not None:
            _generated_code_layout(x, v, sid, cc[1])
        texts = []
        for l in x.text_layers(s):
            db = (x.planned_text(s["id"], l.get("text", "")) or {}).get("drawn_box")
            target = mp.norm(l.get("text", ""))[:40]
            if db:
                texts.append((l.get("text", ""), db, l.get("z", 0), target))
                v.check(S, "layout.inside_frame", _in_frame(db), "error", f"{sid}: the text '{l.get('text')}' is drawn partly outside the frame", sid, target, {"drawn_box": db}, "motion_generation", "build again")
                v.check(S, "text.safe_area", not _outside(db, x.lim), "warning", f"{sid}: the text '{l.get('text')}' is drawn outside the safe area", sid, target, {"drawn_box": db, "limit": round(x.lim, 3), "margin": SAFE},
                        "motion_generation", "move or shorten the text")
                v.check(S, "layout.overflow_clip", db[2] - db[0] <= 1 - 2 * SAFE + 0.03, "warning", f"{sid}: the text '{l.get('text')}' is wider than the safe width and may be clipped", sid, target, {"width": round(db[2] - db[0], 3)},
                        "motion_generation", "shorten the text")
            else:
                v.skip(S, "layout.renderer_geometry_known", f"{sid}: the drawn position of the text '{l.get('text')}' is not known (the planner did not measure it): its collisions are NOT verified", sid, target, {"drawn_box": None},
                       "motion_generation")
        nodes = []
        for l in s["layers"]:
            if l["type"] == "motion_scene":
                for it in l.get("items", []):
                    b = _item_box(it, tall)
                    if it.get("bleed") or not b or b[2] * b[3] >= 0.5 or it.get("kind", "gfx") != "gfx" or ((x.reg or {}).get("graphic", {}).get(it["preset"], {}).get("category") == FRAME):
                        continue
                    rect, tgt = _box_rect(b), it["preset"]
                    v.check(S, "layout.inside_frame", _in_frame(rect), "error", f"{sid}: '{tgt}' lies partly outside the frame", sid, tgt, {"box": b}, "motion_generation", "build again")
                    v.check(S, "layout.safe_margins", not _outside(rect, x.lim), "warning", f"{sid}: '{tgt}' reaches outside the safe area", sid, tgt, {"box": b, "limit": round(x.lim, 3)}, "motion_planning",
                            "move it inside the safe area (Solve warnings)")
                    for text, db, tz, ttarget in texts:
                        share = _share(rect, db)
                        v.check(S, "layout.text_graphic_collision", share <= 0.25, "warning", f"{sid}: '{tgt}' lies on the text '{text}'", sid, f"{tgt}~{ttarget}", {"graphic_box": b, "text_box": db, "overlap_share": round(share, 3)},
                                "motion_planning", "move the graphic (Solve warnings)")
                        if share > 0.25:
                            v.check(S, "layout.z_order_valid", it.get("z", l.get("z", 0)) < tz, "error", f"{sid}: '{tgt}' is drawn above the text '{text}' it covers", sid, f"{tgt}>{ttarget}",
                                    {"graphic_z": it.get("z", l.get("z", 0)), "text_z": tz}, "motion_generation", "build again")
            elif l.get("elementId") and l["type"] in ("shape", "icon"):
                rect = mg.rect_of_layer(l, x.W, x.H)
                if rect:
                    nodes.append((l["elementId"], rect))
                    v.check(S, "layout.inside_frame", _in_frame(rect), "error", f"{sid}: {l['elementId']} lies partly outside the frame", sid, l["elementId"], {"rect": [round(r, 3) for r in rect]}, "motion_generation", "build again")
                    v.check(S, "layout.safe_margins", not _outside(rect, x.lim), "warning", f"{sid}: {l['elementId']} reaches outside the safe area", sid, l["elementId"], {"rect": [round(r, 3) for r in rect]}, "motion_planning",
                            "move it inside the safe area")
                    for text, db, tz, ttarget in texts:
                        share = _share(rect, db)
                        v.check(S, "layout.text_graphic_collision", share <= 0.02, "warning", f"{sid}: {l['elementId']} lies on the text '{text}'", sid, f"{l['elementId']}~{ttarget}",
                                {"rect": [round(r, 3) for r in rect], "text_box": db, "overlap_share": round(share, 3)}, "motion_planning", "move it (Solve warnings)")
        for a in range(len(nodes)):
            for b in range(a + 1, len(nodes)):
                share = _share(nodes[a][1], nodes[b][1])
                v.check(S, "layout.graphic_graphic_collision", share <= 0.05, "warning", f"{sid}: {nodes[a][0]} and {nodes[b][0]} overlap", sid, f"{nodes[a][0]}~{nodes[b][0]}", {"overlap_share": round(share, 3)}, "motion_planning",
                        "move one of them")


# ---------- 8 Audio & Text Synchronization ----------
def _wav_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / w.getframerate()
    except (OSError, wave.Error, EOFError):
        return None


def _audio_seconds(path: Path) -> float | None:
    """The length of the audio file itself: a WAV is read directly, any other format (the project's own mp3, m4a ...) is measured with ffprobe, the tool the Audio Analyzer uses. None = could not be measured."""
    if path.suffix.lower() == ".wav":
        return _wav_seconds(path)
    try:
        from . import audio_analysis
        return float(audio_analysis.probe(path)["duration_seconds"])
    except Exception:                                     # an unreadable file or no ffprobe: the check then says it could not be verified, as before
        return None


def stage_audio_text_sync(x: X, v: V) -> None:
    S, meta = "audio_text_sync", x.comp.get("meta", {})
    audio = x.pdir / str(meta.get("audio", "-"))
    v.check(S, "audio.required_present", audio.exists(), "blocker", f"the composition refers to the audio '{meta.get('audio')}', which is not in the project", None, "audio", {"audio": meta.get("audio")}, "project", "upload the audio")
    seg_len = (x.seg or {}).get("audio_duration_seconds")
    if seg_len is not None:
        v.check(S, "audio.duration_compatible", abs(meta.get("duration", 0) - seg_len) <= 0.05, "warning", f"the composition lasts {meta.get('duration')} s but the audio analysis says {seg_len} s", None, "duration",
                {"composition": meta.get("duration"), "audio_analysis": seg_len}, "motion_generation", "build again")
    secs = _audio_seconds(audio) if audio.exists() else None
    if secs is not None:
        v.check(S, "audio.duration_compatible", abs(meta.get("duration", 0) - secs) <= 0.05, "warning", f"the audio file lasts {secs:.3f} s but the composition {meta.get('duration')} s", None, "audio_file",
                {"file": round(secs, 3), "composition": meta.get("duration")}, "motion_generation", "build again")
    elif audio.exists():
        v.skip(S, "audio.duration_compatible", "the length of the audio file could not be measured here (the file is unreadable or ffprobe is missing): only the analysis' length was compared", None, "audio_file", {}, "project")
    last = x.scenes()[-1]["end"] if x.scenes() else 0
    v.check(S, "audio.duration_compatible", abs(last - meta.get("duration", 0)) <= 0.25, "warning", f"the last scene ends at {last:g} s, the audio is {meta.get('duration')} s", None, "last_scene", {"last_scene_end": last}, "motion_generation",
            "build again")
    pace = [meta.get("motionSpeed"), x.mplan.get("speed"), (x.plan.get("timing_policy") or {}).get("pace")]
    v.check(S, "audio.sync_associations_valid", len({p for p in pace if p is not None}) == 1, "error", f"the pace is not the same everywhere (it would be applied twice or not at all): {pace}", None, "pace",
            {"composition": pace[0], "motion_plan": pace[1], "plan": pace[2]}, "motion_generation", "build again")
    ws = x.words
    marks = sorted({round(w["start"], 3) for w in ws} | {round(w["end"], 3) for w in ws})
    grounded: dict[int, set] = {}
    for vs in x.vp["scenes"]:
        pls = x.ps_by_vid.get(vs["scene_id"])
        if pls:
            ms = x.ms_by_id.get(pls["plan_scene_id"]) or {}
            grounded[pls["plan_scene_id"]] = ({mp.norm(e.get("content") or "") for e in vs["elements"] if e.get("content")} | {mp.norm(t["text"]) for t in ms.get("texts", [])}
                                              | {mp.norm(t.get("text", "") if isinstance(t, dict) else str(t)) for t in ms.get("classic_texts", [])})
    planned = {pls["plan_scene_id"]: [(e["content"], bool(e.get("required"))) for e in vs["elements"] if e.get("content") and mk.is_text(e.get("type", ""))]
               for vs in x.vp["scenes"] if (pls := x.ps_by_vid.get(vs["scene_id"]))}
    for s in x.scenes():
        sid = sid_of(s["id"])
        if (cc := x.custom_code(s)) is not None and cc[1] is not None:       # generated code: the planned on-screen text must be in the source
            src = mp.norm(cc[1].replace("&amp;", "&"))
            for content, req in planned.get(s["id"], []):
                v.check(S, "text.planned_text_drawn", mp.norm(content) in src, "error" if req else "warning", f"{sid}: the planned text '{content}' is not in the generated code", sid, mp.norm(content)[:40],
                        {"required": req}, "motion_generation", "generate the scene again")
        for l in x.text_layers(s):
            txt, at = l.get("text", ""), l.get("at", s["start"])
            target = mp.norm(txt)[:40]
            v.check(S, "text.content_grounded", mp.norm(txt) in grounded.get(s["id"], {mp.norm(txt)}), "error", f"{sid}: the text '{txt}' is not in the approved plan", sid, target, {}, "motion_planning", "run Motion Planning again")
            end = l.get("until") if l.get("until") is not None else s["end"]
            v.check(S, "audio.sync_associations_valid", s["start"] - EPS <= at <= s["end"] + EPS and end <= s["end"] + EPS, "error", f"{sid}: '{txt}' is shown {'before' if at < s['start'] - EPS else 'after'} its scene", sid, target,
                    {"at": at, "until": l.get("until"), "scene": [s["start"], s["end"]]}, "motion_generation", "build again")
            for t in l.get("emphasisAt") or []:
                v.check(S, "audio.sync_associations_valid", at - EPS <= t <= end + EPS, "error", f"{sid}: the emphasis of '{txt}' at {t:g} s is outside the time the text is shown", sid, f"{target}@{t:g}",
                        {"emphasis": t, "shown": [at, end]}, "motion_generation", "build again")
                if not ws:
                    v.skip(S, "timing.emphasis_alignment", f"{sid}: the emphasis of '{txt}' at {t:g} s was not compared (no transcript words)", sid, f"{target}@{t:g}", {}, "motion_generation")
                    continue
                near = min((abs(t - m) for m in marks), default=9)
                word = next((w for w in ws if w["start"] - 1e-6 <= t <= w["end"] + 1e-6), None)
                ev = {"emphasis_seconds": t, "tolerance_ms": round(EMPHASIS_TOLERANCE_S * 1000), "nearest_boundary_ms": round(near * 1000)}
                if word:
                    ev.update(word=word.get("w") or word.get("word"), word_start_seconds=word["start"], word_end_seconds=word["end"], delta_from_start_seconds=round(t - word["start"], 3),
                              delta_from_end_seconds=round(word["end"] - t, 3))
                v.check(S, "timing.emphasis_alignment", near <= EMPHASIS_TOLERANCE_S, "warning",
                        f"{sid}: the emphasis of '{txt}' at {t:g} s is {'inside the spoken word ' + repr(ev.get('word')) if word else 'in a pause'}, not on a word boundary", sid, f"{target}@{t:g}", ev, "motion_generation",
                        "align the emphasis with the intended word boundary if the library supports it, otherwise keep it as a visible warning")


# ---------- 9 Transition & Continuity Readiness ----------
def stage_transition_readiness(x: X, v: V) -> None:
    S = "transition_readiness"
    known = mp.transitions()
    cs = x.scenes()
    ids = {s["id"] for s in cs}
    prev = None
    for k, s in enumerate(cs):
        sid, t = sid_of(s["id"]), s.get("transition_out")
        if not t:
            prev = None
            continue
        nxt = cs[k + 1] if k + 1 < len(cs) else None
        v.check(S, "transition.type_supported", t["type"] in known, "blocker", f"{sid}: the transition '{t['type']}' is not in the transition library", sid, t["type"], {}, "motion_generation", "build again")
        v.check(S, "transition.references_valid", nxt is not None and nxt["id"] in ids, "error", f"{sid}: it has an outgoing transition but no next scene", sid, "next_scene", {}, "motion_planning", "run Motion Planning again")
        cap = 0.5 * min(s["end"] - s["start"], (nxt["end"] - nxt["start"]) if nxt else s["end"] - s["start"])
        v.check(S, "transition.duration_feasible", mp.MIN_DUR - 1e-6 <= t["dur"] <= cap + EPS, "error", f"{sid}: the transition lasts {t['dur']} s, it must be {mp.MIN_DUR}-{cap:.2f} s", sid, "duration",
                {"duration": t["dur"], "allowed": [mp.MIN_DUR, round(cap, 2)]}, "motion_generation", "build again")
        v.check(S, "transition.duration_feasible", t["type"] != prev, "error", f"{sid}: the transition '{t['type']}' repeats the previous scene's", sid, "repeat", {"previous": prev}, "motion_planning", "run Motion Planning again")
        prev = t["type"]
    if cs:
        last = sid_of(cs[-1]["id"])
        v.check(S, "transition.first_last_defined", not cs[-1].get("transition_out"), "error", f"{last}: the last scene has an outgoing transition and nothing to go to", last, "last_scene", {}, "motion_planning", "run Motion Planning again")
    reg = x.reg or {}
    sids = {p["scene_id"] for p in x.plan["scenes"]}
    for ps in x.plan["scenes"]:
        c = ps.get("continuity") or {}
        sid = ps["scene_id"]
        refs_ok = all(r is None or r in sids for r in (c.get("previous_scene_id"), c.get("next_scene_id")))
        gfx_ok = all(g in reg["graphic"] for g in c.get("placed_graphics", [])) if reg else True
        txt_ok = c.get("main_text_preset") in (None, *reg["text"]) if reg else True
        v.check(S, "continuity.motif_notes_valid", refs_ok and gfx_ok and txt_ok, "warning", f"{sid}: its continuity notes refer to a scene, graphic or text preset that does not exist", sid, "continuity",
                {k: c.get(k) for k in ("previous_scene_id", "next_scene_id", "main_text_preset", "placed_graphics")}, "motion_planning", "run Motion Planning again")


# ---------- 10 Composition Buildability & Determinism ----------
def stage_buildability(x: X, v: V) -> None:
    S = "buildability"
    val = mg.validate_composition(x.files["composition"])
    v.check(S, "renderer.layer_type_registered", not val.get("unknown"), "blocker", f"the renderer has no component for the layer type(s) {val.get('unknown')}: they would be skipped", None, "layer_types", {"unknown": val.get("unknown")},
            "motion_generation", "register the component")
    v.check(S, "renderer.schema_valid", val.get("zod") is True, "blocker", f"the composition does not satisfy the renderer's schema: {val.get('zod')}", None, "schema", {"zod": val.get("zod")}, "motion_generation", "build again")
    v.check(S, "animation.no_untrusted_execution", not val.get("wallclock"), "blocker", f"animation code depends on a clock or Math.random: {val.get('wallclock')}", None, "wallclock", {}, "motion_generation", "make the animation frame-driven")
    text = x.files["composition"].read_text(encoding="utf-8")
    v.check(S, "renderer.readback_equal", text == mg.dumps(x.comp) and json.loads(text) == x.comp, "error", "the composition on disk is not its own canonical serialization", None, "readback", {}, "motion_generation", "build again")
    det = (x.gen.get("tests") or {}).get("determinism") or {}
    if det.get("identical") is False:
        v.check(S, "composition.deterministic", False, "error", "two builds of the same plan gave different compositions (recorded by Motion Generation)", None, "determinism", det, "motion_generation", "make the build deterministic")
    elif det.get("identical") is True:
        v.check(S, "composition.deterministic", True, "error", "")
    else:
        v.skip(S, "composition.deterministic", "Motion Generation did not record a repeat build: determinism is not verified (a dry build here would overwrite the composition, so none is made)", None, "determinism", det, "motion_generation", "warning")
    gen_ids = {s["scene_id"]: [d["descriptor_id"] for d in s["descriptors"]] for s in x.gen["scenes"]}
    for s in x.scenes():
        sid = sid_of(s["id"])
        mine = [d["descriptor_id"] for d in x.desc[s["id"]]]
        v.check(S, "composition.descriptors_complete", mine == gen_ids.get(sid) and not any(d.get("missing") for d in x.desc[s["id"]]), "error",
                f"{sid}: its animations are not those Motion Generation reported, or a planned action is not built", sid, "descriptors", {"now": len(mine), "report": len(gen_ids.get(sid, []))}, "motion_generation",
                "run Motion Generation again")
        pics = [l for l in s["layers"] if l["type"] == "image"]
        v.check(S, "composition.assets_resolve", x.images or not pics, "error", f"{sid}: a Motion-Only composition has {len(pics)} picture layer(s)", sid, "pictures", {}, "motion_generation", "build again")
        for l in pics if x.images else []:
            f = l.get("file")
            v.check(S, "composition.assets_resolve", f is None or (config.REMOTION_DIR / "public" / f).exists(), "error", f"{sid}: the picture {f} is not in the Remotion folder", sid, str(f), {}, "motion_generation",
                    "fill the image slots")
    v.check(S, "renderer.readback_equal", x.gen["output"].get("persisted") is True, "error", "Motion Generation did not read its composition back equal", None, "persisted", {}, "motion_generation", "run Motion Generation again")


# ---------- 11 Preview Validation & Visual Evidence ----------
def stage_preview_validation(x: X, v: V) -> None:
    """The preview is optional on the first run: nothing here claims a person looked at anything. Four separate facts: evidence generated / technical checks passed / stills reviewed by a person / motion played and reviewed."""
    from . import motion_validation_preview as pv
    S = "preview_validation"
    man = pv.load(x.pdir, x.aspect)
    gen_sha = ((x.gen or {}).get("output") or {}).get("composition_sha")
    levels = {"evidence_generated": False, "technical_checks_passed": False, "stills_reviewed_by_person": False, "motion_playback_reviewed": False, "samples": 0, "scenes_sampled": 0, "reviews": []}
    x.preview_levels = levels
    if man is None:
        v.skip(S, "preview.evidence_present", "no preview was generated: the scenes have not been looked at (Generate Preview makes low-resolution stills; it never renders the video)", None, "preview", {}, "motion_generation", "warning")
        return
    cur = pv.is_current(man, gen_sha)
    v.check(S, "preview.evidence_current", cur, "warning", "the preview was made from another composition or renderer than the current one: generate it again", None, "preview", {"preview": man.get("composition_sha"), "now": gen_sha},
            "motion_generation", "generate the preview again")
    if not cur:
        levels.update(evidence_generated=True, samples=len(man.get("samples", [])))
        return
    samples, good_all = man.get("samples", []), []
    for smp in samples:
        f = pv.folder(x.pdir, x.aspect) / smp["file"]
        good = f.exists() and sha(f.read_bytes()) == smp.get("sha") and smp.get("decode_ok") is True
        v.check(S, "preview.frames_decode", good, "warning", f"{smp['scene_id']}: the preview frame {smp['file']} is missing, changed or did not decode", smp["scene_id"], smp["file"], {}, "motion_generation", "generate the preview again")
        v.check(S, "preview.not_blank", not smp.get("blank"), "warning", f"{smp['scene_id']}: the preview frame {smp['file']} is blank (std {smp.get('std')})", smp["scene_id"], f"blank:{smp['file']}", {"std": smp.get("std")},
                "motion_generation", "look at the scene")
        good_all.append(good and not smp.get("blank"))
    sampled = {smp["scene_id"] for smp in samples}
    for s in x.scenes():
        v.check(S, "preview.scene_sampled", sid_of(s["id"]) in sampled, "warning", f"{sid_of(s['id'])}: no preview frame was made for it", sid_of(s["id"]), "sampled", {}, "motion_generation", "generate the preview again")
    revs = [r for r in man.get("reviews", []) if r.get("composition_sha") == gen_sha]
    levels.update(evidence_generated=True, technical_checks_passed=bool(good_all) and all(good_all), samples=len(samples), scenes_sampled=len(sampled), reviews=revs,
                  stills_reviewed_by_person=any(r["level"] == "stills" for r in revs), motion_playback_reviewed=any(r["level"] == "playback" for r in revs))
    x.preview_samples = [{**smp, "human_reviewed": levels["stills_reviewed_by_person"]} for smp in samples]
