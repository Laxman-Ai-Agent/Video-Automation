"""Timeline Build (roadmap improvements/Timeline_Build_Complete_Roadmap), Stage 11 of the pipeline: it builds ONE inspectable timeline snapshot (`timeline[_9x16].json`) from the current, validated
upstream artifacts and validates that built object (not the plan it came from). It is not Motion Planning / Generation, not Timeline Approval and not a render: no video is encoded, nothing is
approved, no upstream artifact is changed, no Claude call is made.

The 12 internal stages (checks of one module, shown on the Timeline Build page; not 12 agents):
  1 Request & Lock   2 Input Discovery   3 Freshness & Readiness Gate   4 Project Settings   5 Scene Mapping   6 Frame Timing   7 Video Track   8 Audio Track
  9 Transitions & Gaps   10 Timeline Assembly   11 Post-Build Validation   12 Persist, Read Back & Publish
Rules that make it honest:
  - ONE time-to-frame rule: `motion_planning.fr` = floor(seconds x fps + 0.5) (= the renderer's Math.round); intervals are half-open [start_frame, end_frame).
  - The duration is what the renderer will really produce (Math.round(meta.duration x fps)); an audio tail the renderer cuts off is reported, never hidden.
  - A gap keeps its source seconds; the visual policy is `hold_previous_scene` (Motion Planning holds a scene through the pause after it) and is recorded; a gap nothing covers is a blocker.
  - A transition is an explicit entry with its window; the renderer clamps an over-long one and falls back to `fade` for an unknown type: both are findings here, not silent.
  - Publish: assemble -> validate -> temp write -> read back -> same canonical digest -> inputs fingerprinted again -> backup of the last good pair -> atomic replace. A blocked or failed
    attempt never replaces the published timeline; it is recorded in `timeline_build_attempt[_9x16].json`. Approval is `not_approved` here, always."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

from . import config, motion_planning as mp, motion_validation as mv, resource_library as rl, store

SCHEMA = "1.0"
VERSION = 1                                       # the builder (structure of the timeline and the report)
RULE_SET = "1.0"                                  # bump when the meaning of a rule changes (part of the fingerprint)
POLICY = {"frame_timing_version": "1", "gap_policy_version": "1", "transition_policy_version": "1"}
OK = ("completed", "completed_with_warnings")
STAGES = (
    ("request_lock", "Build Request", "Build Request & Lock"),
    ("input_discovery", "Input Discovery", "Input Artifact Discovery"),
    ("freshness_gate", "Freshness Gate", "Source Freshness & Readiness Gate"),
    ("settings", "Project Settings", "Project Settings Normalization"),
    ("scene_mapping", "Scene Mapping", "Scene Mapping"),
    ("frame_timing", "Frame Timing", "Frame Timing Normalization"),
    ("video_track", "Video Track", "Video / Composition Track Assembly"),
    ("audio_track", "Audio Track", "Audio & Narration Track Assembly"),
    ("transitions_gaps", "Transitions & Gaps", "Transition & Gap Policy Application"),
    ("assembly", "Assembly", "Timeline Assembly & Duration"),
    ("validation", "Validation", "Structural / Post-Build Validation"),
    ("persist", "Publish", "Persist, Read Back & Publish"),
)
SEVERITIES = ("blocker", "error", "warning", "info")
BLOCKING = ("blocker", "error")


class BuildError(Exception):
    """The build could not be done reliably (a message for the user)."""


def names(aspect: str) -> dict[str, str]:
    sfx = "_9x16" if aspect == "9:16" else ""
    return {"timeline": f"timeline{sfx}.json", "report": f"timeline_build_report{sfx}.json", "attempt": f"timeline_build_attempt{sfx}.json", "backup": f"timeline_backup{sfx}"}


canon, sha = mv.canon, mv.sha
_file_sha = mv._file_sha
_running: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def semantic_digest(timeline: dict) -> str:
    """The timeline without its audit block (timestamps): the same inputs always give the same digest."""
    return sha(canon({k: v for k, v in timeline.items() if k != "audit"}))


# ---------- the inputs and the fingerprint ----------
def input_files(pdir: Path, aspect: str) -> dict[str, Path]:
    return {**mv.input_files(pdir, aspect), "scene_plan": pdir / "scene_plan.json"}


def input_digests(pdir: Path, aspect: str) -> dict[str, str | None]:
    """Every material input by role: the Stage 10 verdict (fingerprint, readiness, accepted exceptions), the artifacts, the audio (name and size), the words, the renderer, the policies and this module."""
    d = {k: v for k, v in mv.input_digests(pdir, aspect).items() if k in ("project", "segmentation", "visual_plan", "scene_plan", "motion_plan", "motion_planning", "motion_generation", "composition", "audio", "words", "renderer", "resources")}
    rep = mv.load(pdir, aspect)
    d["stage10"] = None if rep is None else sha(canon([rep.get("source_fingerprint"), rep.get("readiness"), rep.get("phase_status"), sorted(r["exception_id"] for r in rep.get("exceptions", []) if not r.get("revoked_at"))]))
    d["policies"] = sha(canon([SCHEMA, VERSION, RULE_SET, POLICY, aspect]))
    d["builder"] = _file_sha(Path(__file__))
    return d


def fingerprint(pdir: Path, aspect: str, digests: dict | None = None) -> str:
    return sha(canon(digests if digests is not None else input_digests(pdir, aspect)))


# ---------- findings ----------
def finding_id(rule: str, scene: str | None, item: str | None) -> str:
    return mv.finding_id(rule, scene, item)


class Rec:
    """Checks passed / applicable per stage and one finding per failed rule and target."""

    def __init__(self) -> None:
        self.findings: dict[str, dict] = {}
        self.counts = {s[0]: {"passed": 0, "total": 0, "skipped": 0} for s in STAGES}

    def _add(self, stage, rule, severity, message, scene, item, evidence, owner, action) -> None:
        fid = finding_id(rule, scene, item)
        if fid in self.findings:
            self.findings[fid]["occurrences"] += 1
            return
        self.findings[fid] = {"finding_id": fid, "rule_id": rule, "stage_id": stage, "severity": severity, "status": "unresolved", "scene_id": scene, "item_id": item, "message": message,
                              "evidence": evidence or {}, "owner_stage": owner, "suggested_action": action, "blocks_build": severity in BLOCKING, "occurrences": 1}

    def check(self, stage: str, rule: str, ok: bool, severity: str, message: str, scene: str | None = None, item: str | None = None, evidence: dict | None = None,
              owner: str = "timeline_build", action: str = "") -> bool:
        c = self.counts[stage]
        c["total"] += 1
        if ok:
            c["passed"] += 1
        else:
            self._add(stage, rule, severity, message, scene, item, evidence, owner, action or f"fix it in {owner.replace('_', ' ')}, then build the timeline again")
        return ok

    def note(self, stage: str, rule: str, severity: str, message: str, scene: str | None = None, item: str | None = None, evidence: dict | None = None, owner: str = "motion_generation") -> None:
        """A disclosed fact that is not a check (an element that is not drawn, a stand-in): always visible, never counted as a pass."""
        self._add(stage, rule, severity, message, scene, item, evidence, owner, "")

    def skip(self, stage: str, rule: str, message: str, scene: str | None = None) -> None:
        self.counts[stage]["skipped"] += 1
        self._add(stage, rule, "info", message, scene, None, {}, "timeline_build", "")

    def of(self, stage: str) -> list[dict]:
        return [f for f in self.findings.values() if f["stage_id"] == stage]


# ---------- the builder ----------
def _sid(n: int) -> str:
    return f"scene_{n:03d}"


class Builder:
    def __init__(self, pdir: Path, aspect: str, rec: Rec) -> None:
        self.pdir, self.aspect, self.r = pdir, aspect, rec
        self.comp = self.seg = self.plan = self.gen = self.val = self.info = self.mplan = None
        self.fps = 30
        self.scenes: list[dict] = []                  # one row per canonical scene (the working data of the stages)
        self.T: dict = {}
        self.audio: Path | None = None
        self.audio_s = 0.0
        self.tail = 0.0
        self.width = self.height = 0
        self.motion_only = False
        self.words_n = 0
        self.fp = ""

    def _motion(self) -> bool:
        from . import motion_branch
        return motion_branch.required(self.pdir) or (self.pdir / mv.input_files(self.pdir, self.aspect)["motion_generation"].name).exists()

    # --- 2 ---
    def stage_input_discovery(self) -> None:
        S, r = "input_discovery", self.r
        files = input_files(self.pdir, self.aspect)
        required = ["composition", "project"]
        if self._motion():
            required += ["motion_plan", "motion_planning", "motion_generation"]
        root = self.pdir.resolve()
        data = {}
        for role in required:
            f = files[role]
            r.check(S, "input.exists", f.exists(), "blocker", f"{role} ({f.name}) is missing", None, role, {"file": f.name}, role, "run the stage that makes it")
            r.check(S, "input.inside_project", f.resolve().is_relative_to(root), "blocker", f"{role} is outside the project folder", None, role, {"file": f.name}, "project")
            try:
                data[role] = json.loads(f.read_text(encoding="utf-8"))
                r.check(S, "input.parses", isinstance(data[role], dict), "blocker", f"{f.name} is not a JSON object", None, role, {"file": f.name}, role)
            except (OSError, ValueError) as e:
                r.check(S, "input.parses", False, "blocker", f"{f.name} cannot be read: {e}"[:200], None, role, {"file": f.name}, role)
        self.info, self.comp = data.get("project"), data.get("composition")
        self.plan, self.gen, self.mplan = data.get("motion_planning"), data.get("motion_generation"), data.get("motion_plan")
        if self.comp is not None and not (isinstance(self.comp.get("meta"), dict) and isinstance(self.comp.get("scenes"), list) and self.comp["scenes"]):
            r.check(S, "input.composition_shape", False, "blocker", "the composition has no meta or no scenes", None, "composition", {}, "motion_generation")
            self.comp = None
        seg = mp._read(files["segmentation"])
        self.seg = seg if isinstance(seg, dict) and seg.get("scenes") else None
        if self.seg is None:
            r.note(S, "input.no_segmentation", "warning", "this project has no Scene Segmentation: the canonical times come from the motion plan (derived mode)", None, "segmentation", {}, "scene_segmentation")
        a = next(iter(sorted(self.pdir.glob("audio.*"))), None)
        self.audio = a
        r.check(S, "input.audio_exists", a is not None and a.is_file() and a.resolve().is_relative_to(root), "blocker", "the project audio is missing or outside the project", None, "audio", {}, "audio_input", "upload the audio again")

    # --- 3 ---
    def stage_freshness_gate(self) -> None:
        S, r = "freshness_gate", self.r
        from . import motion_gen_report
        if not self._motion():
            r.skip(S, "freshness.motion", "this project has no motion branch: the Stage 10 verdict and the motion gates do not apply")
            return
        why = mp.blockers(self.pdir, self.aspect)
        r.check(S, "freshness.motion_plan_current", not why, "blocker", f"Motion Planning is not current: {why}", None, "motion_planning", {"why": why}, "motion_planning", "run Motion Planning again")
        why = motion_gen_report.blockers(self.pdir, self.aspect)
        r.check(S, "freshness.motion_generation_current", not why, "blocker", f"Motion Generation is not current: {why}", None, "motion_generation", {"why": why}, "motion_generation", "run Motion Generation again")
        rep = mv.load(self.pdir, self.aspect)
        self.val = rep
        bl = mv.blockers(self.pdir, self.aspect)
        r.check(S, "freshness.stage10_ready", not bl, "blocker", bl[0] if bl else "", None, "stage10", {"readiness": rep and rep.get("readiness")}, "motion_validation", "run Motion & Timeline Validation and resolve its findings")
        if rep and rep.get("phase_status") == "completed" and not rep.get("stale"):
            s = rep["summary"]
            r.check(S, "freshness.required_visuals_drawn", s.get("required_not_drawn", 0) == 0 or s.get("accepted_exceptions", 0) > 0, "blocker", f"{s.get('required_not_drawn')} required element(s) are not drawn and no exception was recorded", None, "required_elements",
                    {"required_not_drawn": s.get("required_not_drawn")}, "motion_validation")
            for row in rep.get("elements", []):                    # what is not drawn stays visible here: accepted does not mean drawn
                if row["state"] == "approximate":                  # drawn, but as a stand-in for what the plan describes
                    r.note(S, "visual.approximate", "warning", f"{row['element_id']} ({row['type']}) is drawn as a stand-in for what the plan describes" + (f": {row['why']}" if row["why"] not in ("", "drawn") else ""), row["scene_id"], row["element_id"], {"state": row["state"], "required": row["required"]})
                elif row["state"] != "drawn":
                    r.note(S, "visual.not_drawn" if row["required"] else "visual.optional_not_drawn", "warning" if row["required"] else "info", f"{row['element_id']} ({row['type']}) is {row['state'].replace('_', ' ')}: {row['why']}",
                           row["scene_id"], row["element_id"], {"state": row["state"], "required": row["required"], "plan_status": row.get("plan_status")})

    # --- 4 ---
    def stage_settings(self) -> None:
        S, r, m = "settings", self.r, self.comp["meta"]
        self.fps = m.get("fps") if isinstance(m.get("fps"), int) else 0
        w, h = m.get("width"), m.get("height")
        r.check(S, "settings.valid", self.fps > 0 and isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0, "blocker", f"the composition has no valid size/fps ({w}x{h} at {m.get('fps')})", None, "meta", {"width": w, "height": h, "fps": m.get("fps")}, "motion_generation")
        if self.fps <= 0:
            self.fps = 30
        if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0):
            w = h = 1
        want = "9:16" if self.aspect == "9:16" else "16:9"
        r.check(S, "settings.aspect_matches", abs(w / h - (9 / 16 if want == "9:16" else 16 / 9)) < 0.01, "blocker", f"the composition is {w}x{h}, not {want}", None, "meta", {"width": w, "height": h, "aspect": want}, "motion_generation")
        proj = (self.plan or {}).get("project") or {}
        if proj:
            r.check(S, "settings.consistent_with_plan", (proj.get("width"), proj.get("height"), proj.get("fps")) == (w, h, self.fps), "blocker", "the motion plan and the composition disagree on width, height or fps", None, "meta",
                    {"plan": [proj.get("width"), proj.get("height"), proj.get("fps")], "composition": [w, h, self.fps]}, "motion_generation")
        r.check(S, "settings.mode_matches", bool(m.get("motionOnly")) == (not store.uses_images(self.pdir)), "blocker", "the composition was built for the other Use Images setting", None, "meta",
                {"motionOnly": m.get("motionOnly"), "use_images": store.uses_images(self.pdir)}, "motion_generation", "run Motion Generation again")
        self.width, self.height = w, h
        self.motion_only = bool(m.get("motionOnly"))

    # --- 5 ---
    def stage_scene_mapping(self) -> None:
        S, r = "scene_mapping", self.r
        cs = self.comp["scenes"]
        n = len(cs)
        ids = [s["id"] for s in cs]
        r.check(S, "scene.ids_sequential", ids == list(range(1, n + 1)), "blocker", f"the composition scene ids are not 1..{n} in order: {ids}", None, "scenes", {"ids": ids}, "motion_generation")
        if self.seg:
            rows = [{"id": s["scene_id"], "start": s["start_time"], "end": s["end_time"], "gap": s.get("pause_after_seconds"), "segments": s.get("source_segment_ids", []), "words": s.get("word_range")} for s in self.seg["scenes"]]
        else:
            rows = [{"id": _sid(i + 1), "start": p["timing"].get("canonical_start", p["timing"]["start"]), "end": p["timing"].get("canonical_end", p["timing"]["end"]), "gap": p["timing"].get("gap_after_seconds"), "segments": [], "words": None}
                    for i, p in enumerate((self.plan or {}).get("scenes", []))]
        src = "Scene Segmentation" if self.seg else "the motion plan"
        r.check(S, "scene.count_matches", len(rows) == n, "blocker", f"{src} has {len(rows)} scenes, the composition {n}", None, "scenes", {"canonical": len(rows), "composition": n}, "motion_generation")
        ps = {p["plan_scene_id"]: p for p in (self.plan or {}).get("scenes", [])}
        gs = {g["plan_scene_id"]: g for g in (self.gen or {}).get("scenes", [])}
        r.check(S, "scene.unique", len(set(ids)) == n and len({c["id"] for c in rows}) == len(rows), "blocker", "a scene appears twice", None, "scenes", {}, "motion_generation")
        for i, s in enumerate(cs[:len(rows)]):
            c = rows[i]
            if self._motion():
                r.check(S, "scene.in_motion_plan", s["id"] in ps, "blocker", f"{c['id']} is not in the motion plan", c["id"], "motion_plan", {}, "motion_planning")
                r.check(S, "scene.in_generation", s["id"] in gs, "blocker", f"{c['id']} is not in the Motion Generation report", c["id"], "motion_generation", {}, "motion_generation")
            self.scenes.append({"sid": c["id"], "comp": s, "canon": c, "plan": ps.get(s["id"]), "gen": gs.get(s["id"]), "key": f"scene_{s['id']:02d}", "i": i})
        if self.seg:
            for row in self.scenes:
                p = row["plan"]
                if p:
                    t = p["timing"]
                    r.check(S, "scene.canonical_times_agree", abs(t.get("canonical_start", -1) - row["canon"]["start"]) <= mp.EPS and abs(t.get("canonical_end", -1) - row["canon"]["end"]) <= mp.EPS, "blocker",
                            f"{row['sid']}: the motion plan's canonical times differ from Scene Segmentation", row["sid"], "timing", {"plan": [t.get("canonical_start"), t.get("canonical_end")], "segmentation": [row["canon"]["start"], row["canon"]["end"]]}, "motion_planning")

    # --- 6 ---
    def stage_frame_timing(self) -> None:
        S, r, fps = "frame_timing", self.r, self.fps
        for row in self.scenes:
            s, c, sid = row["comp"], row["canon"], row["sid"]
            row["sf"], row["ef"] = mp.fr(s["start"], fps), mp.fr(s["end"], fps)
            row["nsf"], row["nef"] = mp.fr(c["start"], fps), mp.fr(c["end"], fps)
            r.check(S, "time.positive_duration", row["ef"] > row["sf"], "blocker", f"{sid}: its interval is empty after rounding to frames", sid, "interval", {"start_frame": row["sf"], "end_frame": row["ef"]}, "motion_planning")
            r.check(S, "time.narration_inside_clip", s["start"] - mp.EPS <= c["start"] and c["end"] <= s["end"] + mp.EPS, "blocker", f"{sid}: the narration lies outside the scene's timeline interval", sid, "interval",
                    {"clip": [s["start"], s["end"]], "narration": [c["start"], c["end"]]}, "motion_planning")
            if row["plan"]:
                t = row["plan"]["timing"]
                r.check(S, "time.frames_match_plan", (t["start_frame"], t["end_frame"]) == (row["sf"], row["ef"]), "blocker", f"{sid}: the frames of the plan and the one rule differ", sid, "interval", {"plan": [t["start_frame"], t["end_frame"]], "rule": [row["sf"], row["ef"]]}, "motion_planning")
            if row["gen"]:
                t = row["gen"]["timing"]
                r.check(S, "time.frames_match_generation", (t["start_frame"], t["end_frame"]) == (row["sf"], row["ef"]), "blocker", f"{sid}: the frames of Motion Generation and the one rule differ", sid, "interval", {"generation": [t["start_frame"], t["end_frame"]], "rule": [row["sf"], row["ef"]]}, "motion_generation")
        self.dur_s = self.comp["meta"].get("duration", 0)
        self.dur_f = mp.fr(self.dur_s, fps)
        r.check(S, "time.duration_positive", self.dur_f > 0, "blocker", "the composition has no duration", None, "duration", {"duration": self.dur_s}, "motion_generation")
        if self.audio:
            from . import audio_utils
            try:
                self.audio_s = audio_utils.duration(self.audio)
            except Exception as e:
                r.check(S, "audio.readable", False, "blocker", f"the audio cannot be read: {e}"[:200], None, "audio", {"file": self.audio.name}, "audio_input")
        # an audio shorter than the video is silence at the end (disclosed; Stage 10 already asked for a decision); an audio LONGER than the video is cut off and is a blocker below
        r.check(S, "audio.matches_composition", abs(self.audio_s - self.dur_s) <= 1 / fps, "warning", f"the audio is {self.audio_s:.3f} s, the composition {self.dur_s:.3f} s", None, "audio",
                {"audio_seconds": self.audio_s, "composition_seconds": self.dur_s}, "motion_generation", "check the audio file; build Motion Generation again if it was replaced")
        tail = self.audio_s - self.dur_f / fps
        self.tail = round(tail, 4)
        r.check(S, "audio.not_truncated", tail <= 1 / fps, "blocker", f"the renderer would cut {tail:.3f} s of the audio (more than one frame)", None, "audio", {"tail_seconds": self.tail}, "motion_generation")
        r.check(S, "audio.tail_quantization", tail <= 1e-3, "warning",
                f"the renderer's frame count ({self.dur_f} frames = {self.dur_f / fps:.3f} s) is {self.tail:.3f} s shorter than the audio ({self.audio_s:.3f} s): less than one frame is cut off the end of the audio",
                None, "audio", {"tail_seconds": self.tail, "frame_seconds": round(1 / fps, 4), "renderer_frames": self.dur_f}, "render", "within one frame: permitted by policy, disclosed here")

    # --- 7 ---
    def stage_video_track(self) -> None:
        S, r, fps = "video_track", self.r, self.fps
        items = []
        files = input_files(self.pdir, self.aspect)
        if self._motion():
            from . import motion_generation as mg
            val = mg.validate_composition(files["composition"])
        else:
            val = {"unknown": []}
        r.check(S, "layer.types_registered", not val.get("unknown"), "blocker", f"the renderer has no component for the layer type(s) {val.get('unknown')}", None, "layer_types", {"unknown": val.get("unknown")}, "motion_generation")
        pub = (config.REMOTION_DIR / "public").resolve()
        for row in self.scenes:
            s, sid = row["comp"], row["sid"]
            layers = []
            for j, l in enumerate(s["layers"]):
                at = l.get("at")
                lid = f"{row['key']}_L{j + 1:02d}"
                inside = not isinstance(at, (int, float)) or row["sf"] <= mp.fr(at, fps) < row["ef"]
                r.check(S, "layer.starts_inside_scene", inside, "blocker", f"{lid}: it starts at {at} s, outside {sid}", sid, lid, {"at": at, "scene": [s["start"], s["end"]]}, "motion_generation")
                start = mp.fr(at, fps) if isinstance(at, (int, float)) and inside else row["sf"]
                layers.append({"layer_id": lid, "type": l["type"], "z": l.get("z", 0), "preset": l.get("preset"), "start_frame": start, "end_frame": row["ef"]})
                f = l.get("file")
                if f:
                    ref = (pub / f).resolve()
                    r.check(S, "asset.inside_public", ref.is_relative_to(pub), "blocker", f"{lid}: the picture path leaves the public folder", sid, lid, {"file": f}, "image_generation")
                    r.check(S, "asset.exists", ref.is_file(), "blocker", f"{lid}: the picture {f} does not exist", sid, lid, {"file": f}, "image_generation")
            if self.motion_only:
                r.check(S, "mode.no_pictures", not any(l.get("file") for l in s["layers"]), "blocker", f"{sid}: a picture layer in a motion-only timeline", sid, "layers", {}, "motion_generation")
            descs = [d["descriptor_id"] for d in (row["gen"] or {}).get("descriptors", [])]
            if row["gen"]:
                bad = [d["descriptor_id"] for d in row["gen"]["descriptors"] if not (row["sf"] <= d["start_frame"] < d["end_frame"] <= row["ef"])]
                r.check(S, "layer.descriptors_inside_scene", not bad, "blocker", f"{sid}: {len(bad)} descriptor(s) lie outside the scene's frames", sid, "descriptors", {"descriptors": bad[:5]}, "motion_generation")
            row["layers"], row["descriptors"] = layers, descs
            items.append({"item_id": f"scene_clip_{sid[6:]}", "scene_id": sid, "composition_ref": f"{files['composition'].name}#scenes[{row['i']}]", "composition_scene_id": s["id"], "pattern": s.get("pattern"),
                          "start_frame": row["sf"], "end_frame": row["ef"], "source_start_seconds": s["start"], "source_end_seconds": s["end"],
                          "narration_start_frame": row["nsf"], "narration_end_frame": row["nef"], "narration_start_seconds": row["canon"]["start"], "narration_end_seconds": row["canon"]["end"],
                          "camera": (s.get("camera") or {}).get("move"), "layers": layers, "layer_refs": [x["layer_id"] for x in layers], "descriptor_refs": descs})
        self.video_items = items

    # --- 8 ---
    def stage_audio_track(self) -> None:
        S, r = "audio_track", self.r
        self.audio_item = {"item_id": "audio_clip", "source_ref": self.audio.name if self.audio else None, "start_frame": 0, "end_frame": min(self.dur_f, mp.fr(self.audio_s, self.fps)), "source_duration_seconds": round(self.audio_s, 3),
                           "playback_rate": 1.0, "offset_seconds": 0.0, "trimmed_tail_seconds": max(0.0, self.tail), "required": True}
        r.check(S, "audio.single_clip", self.audio is not None, "blocker", "there is no audio clip", None, "audio_clip", {}, "audio_input")
        ref = self.comp["meta"].get("audio")
        r.check(S, "audio.composition_reference", self.audio is not None and ref == self.audio.name, "blocker", f"the composition names the audio {ref!r}, the project audio is {self.audio.name if self.audio else None!r}", None, "audio_clip",
                {"composition": ref}, "motion_generation", "run Motion Generation again")
        words = self.comp.get("words", [])
        out = [w for w in words if not (0 <= w["start"] < w["end"] <= self.dur_s + 1e-6)]
        r.check(S, "narration.words_inside_audio", not out, "blocker", f"{len(out)} word timing(s) lie outside the audio", None, "words", {"first": out[:2]}, "audio_analyzer")
        self.words_n = len(words)

    # --- 9 ---
    def stage_transitions_gaps(self) -> None:
        S, r, fps = "transitions_gaps", self.r, self.fps
        sup = mp.transitions()
        gaps, trans, prev = [], [], None
        n = len(self.scenes)
        if self.scenes:
            first = self.scenes[0]
            r.check(S, "gap.starts_at_zero", first["sf"] == 0, "blocker", f"the first scene starts at frame {first['sf']}, not 0: the start of the video is uncovered", first["sid"], "start", {"start_frame": first["sf"]}, "motion_planning")
        for i, row in enumerate(self.scenes):
            s, nxt = row["comp"], self.scenes[i + 1] if i + 1 < n else None
            if nxt:
                gap_s = nxt["canon"]["start"] - row["canon"]["end"]
                if row["canon"]["gap"] is not None:
                    r.check(S, "gap.matches_source", abs(gap_s - row["canon"]["gap"]) <= 0.011, "blocker", f"{row['sid']}: the pause after it is {gap_s:.3f} s but the source says {row['canon']['gap']}", row["sid"], "gap",
                            {"computed": gap_s, "source": row["canon"]["gap"]}, "scene_segmentation")
                r.check(S, "gap.scenes_adjacent", s["end"] == nxt["comp"]["start"], "blocker", f"{row['sid']} ends at {s['end']} s but the next scene starts at {nxt['comp']['start']} s: the video has a hole or an overlap", row["sid"], "gap",
                        {"end": s["end"], "next_start": nxt["comp"]["start"]}, "motion_planning")
                if gap_s > 1e-6:
                    g0, g1 = mp.fr(row["canon"]["end"], fps), mp.fr(nxt["canon"]["start"], fps)
                    r.check(S, "gap.covered_by_policy", row["sf"] <= g0 and row["ef"] >= g1, "blocker", f"{row['sid']}: the pause after it is not covered by the hold of the scene", row["sid"], "gap", {"gap_frames": [g0, g1], "clip_frames": [row["sf"], row["ef"]]}, "motion_planning")
                    gaps.append({"gap_id": f"gap_{row['sid'][6:]}_{nxt['sid'][6:]}", "after_scene": row["sid"], "before_scene": nxt["sid"], "source_start_seconds": row["canon"]["end"], "source_end_seconds": nxt["canon"]["start"],
                                 "source_gap_seconds": round(gap_s, 3), "start_frame": g0, "end_frame": g1, "frames": g1 - g0, "policy": "hold_previous_scene", "filler_item": f"scene_clip_{row['sid'][6:]}", "mutates_source_interval": False})
            else:
                tail = self.dur_f - row["ef"]
                r.check(S, "gap.last_scene_reaches_end", tail == 0, "blocker", f"the last scene ends {tail} frame(s) before the end of the video", row["sid"], "tail", {"scene_end_frame": row["ef"], "duration_frames": self.dur_f}, "motion_planning")
                t0 = mp.fr(row["canon"]["end"], fps)
                if self.dur_f > t0:
                    gaps.append({"gap_id": f"gap_{row['sid'][6:]}_end", "after_scene": row["sid"], "before_scene": None, "source_start_seconds": row["canon"]["end"], "source_end_seconds": round(self.dur_s, 3),
                                 "source_gap_seconds": round(self.dur_s - row["canon"]["end"], 3), "start_frame": t0, "end_frame": self.dur_f, "frames": self.dur_f - t0, "policy": "hold_previous_scene",
                                 "filler_item": f"scene_clip_{row['sid'][6:]}", "mutates_source_interval": False})
            t = s.get("transition_out")
            if t and not nxt:
                r.note(S, "transition.on_last_scene", "info", f"{row['sid']} has a transition out but no scene follows: the renderer ignores it", row["sid"], "transition", {"type": t["type"]}, "motion_planning")
            if t and nxt:
                req = mp.fr(t["dur"], fps)
                base_a, base_b = row["ef"] - row["sf"], nxt["ef"] - nxt["sf"]
                applied = max(0, min(req, base_a - 1))
                tid = f"transition_{row['sid'][6:]}_{nxt['sid'][6:]}"
                r.check(S, "transition.supported", t["type"] in sup, "blocker", f"{tid}: '{t['type']}' is not a transition of the library (the renderer would draw a fade)", row["sid"], tid, {"type": t["type"], "supported": sorted(sup)}, "motion_planning")
                r.check(S, "transition.positive", req >= 1, "blocker", f"{tid}: its duration {t['dur']} s is less than one frame", row["sid"], tid, {"dur": t["dur"], "frames": req}, "motion_planning")
                r.check(S, "transition.not_clamped", applied == req, "warning", f"{tid}: the renderer shortens it from {req} to {applied} frames (the scene is only {base_a} frames long)", row["sid"], tid,
                        {"requested_frames": req, "applied_frames": applied}, "motion_planning")
                r.check(S, "transition.fits_next_scene", applied < base_b, "blocker", f"{tid}: its window of {applied} frames does not fit the next scene ({base_b} frames)", row["sid"], tid, {"applied_frames": applied, "next_scene_frames": base_b}, "motion_planning")
                r.check(S, "transition.inside_audio", nxt["sf"] + applied <= self.dur_f, "blocker", f"{tid}: its window ends after the end of the video", row["sid"], tid, {}, "motion_planning")
                if prev:
                    r.check(S, "transition.not_repeated", prev != t["type"], "warning", f"{tid}: the same transition ('{t['type']}') as the previous boundary", row["sid"], tid, {"type": t["type"]}, "motion_planning")
                prev = t["type"]
                trans.append({"transition_id": tid, "type": t["type"], "from_scene": row["sid"], "to_scene": nxt["sid"], "boundary_frame": nxt["sf"], "start_frame": nxt["sf"], "end_frame": nxt["sf"] + applied,
                              "requested_frames": req, "applied_frames": applied, "requested_seconds": t["dur"], "supported": t["type"] in sup, "moves_scene_boundaries": False})
        self.gaps, self.transitions = gaps, trans

    # --- 10 ---
    def stage_assembly(self) -> None:
        S, r = "assembly", self.r
        ducking_profile = {}
        try:
            from SYSTEM.agents.video_generation_agents.timeline_build.timeline_intelligence import AudioDuckingEngine
            duck_engine = AudioDuckingEngine()
            ducking_profile = duck_engine.compute_ducking_profile(self.pdir, self.dur_f, self.fps)
        except Exception:
            ducking_profile = {"ducking_applied": False, "speech_intervals_count": 0}
        self.ducking_profile = ducking_profile

        self.T = {
            "schema_version": SCHEMA, "timeline_id": "", "project_id": self.pdir.name, "status": "built", "source_fingerprint": "", "builder": {"version": VERSION, "rule_set": RULE_SET},
            "profile": {"width": self.width, "height": self.height, "fps": self.fps, "aspect_ratio": self.aspect, "duration_frames": self.dur_f, "duration_seconds_source": round(self.audio_s, 3),
                        "composition_duration_seconds": self.dur_s, "mode": "motion_only" if self.motion_only else "with_pictures", "scene_count": len(self.scenes)},
            "timing": {"interval_convention": "half_open", "frame_rounding": "floor(seconds x fps + 0.5) (backend/motion_planning.fr, the renderer's Math.round)", "duration_policy": "renderer: round(composition duration x fps)",
                       "audio_tail_seconds_not_rendered": max(0.0, self.tail), "frame_seconds": round(1 / self.fps, 6)},
            "policies": {**POLICY, "gap_policy": "hold_previous_scene", "transition_policy": "explicit_from_motion_plan; window = [next scene start, + applied frames)"},
            "tracks": [{"track_id": "audio_main", "track_type": "audio", "items": [self.audio_item]},
                       {"track_id": "video_scenes", "track_type": "composition", "items": self.video_items}],
            "audio_ducking": ducking_profile,
            "gap_intervals": self.gaps, "transitions": self.transitions,
            "source_map": [{"scene_id": row["sid"], "timeline_item": f"scene_clip_{row['sid'][6:]}", "segmentation_scene": row["sid"] if self.seg else None, "motion_scene": row["key"], "composition_scene_id": row["comp"]["id"],
                            "source_segment_ids": row["canon"]["segments"], "word_range": row["canon"]["words"]} for row in self.scenes],
            "overlays": {"captions": bool(self.comp["meta"].get("subtitles")), "words": self.words_n},
            "resources": [{k: u[k] for k in ("resource_id", "category", "registry_sha256", "license_id", "status")} for u in rl.used_resources(self.comp)],      # only what this timeline uses (Resource Library)
            "disclosures": self._disclosures(), "build_report_ref": names(self.aspect)["report"], "approval": {"status": "not_approved", "approved_fingerprint": None},
            "audit": {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
        }
        ids = [i["item_id"] for t in self.T["tracks"] for i in t["items"]]
        r.check(S, "assembly.ids_unique", len(ids) == len(set(ids)) and len({t["track_id"] for t in self.T["tracks"]}) == len(self.T["tracks"]), "blocker", "a track or item id appears twice", None, "ids", {}, "timeline_build")

    def _disclosures(self) -> dict:
        s = (self.val or {}).get("summary", {})
        return {"required_not_drawn": s.get("required_not_drawn", 0), "optional_not_drawn": s.get("optional_not_drawn", 0), "approximate": s.get("approximate", 0), "accepted_exceptions": s.get("accepted_exceptions", 0),
                "note": "accepted does not mean drawn: see the findings of the build report"}

    # --- 11 ---
    def stage_validation(self) -> None:
        """Validates the assembled object (T): every value is recomputed from the sources, nothing is trusted because the builder wrote it."""
        S, r, T = "validation", self.r, self.T
        fps = T["profile"]["fps"]
        r.check(S, "prov.project", T["project_id"] == self.pdir.name, "blocker", "the timeline names another project", None, "project", {}, "timeline_build")
        r.check(S, "prov.fingerprint_current", T["source_fingerprint"] == fingerprint(self.pdir, self.aspect), "blocker", "an input changed while the timeline was built", None, "fingerprint", {}, "timeline_build", "build again")
        r.check(S, "prov.manifest", all(k in T["policies"] for k in POLICY) and T["builder"]["version"] == VERSION and T["schema_version"] == SCHEMA, "blocker", "the timeline does not name its policy / builder versions", None, "manifest", {}, "timeline_build")
        clips = T["tracks"][1]["items"]
        canon_ids = [row["sid"] for row in self.scenes]
        r.check(S, "cover.every_scene_once", [c["scene_id"] for c in clips] == canon_ids and len(set(canon_ids)) == len(canon_ids), "blocker", "a scene is dropped, duplicated or out of order", None, "scenes",
                {"timeline": [c["scene_id"] for c in clips], "canonical": canon_ids}, "timeline_build")
        r.check(S, "cover.source_times", all(abs(c["narration_start_seconds"] - row["canon"]["start"]) <= mp.EPS and abs(c["narration_end_seconds"] - row["canon"]["end"]) <= mp.EPS for c, row in zip(clips, self.scenes)), "blocker",
                "a scene's source times differ from the approved input", None, "scenes", {}, "timeline_build")
        r.check(S, "cover.source_map", [m["scene_id"] for m in T["source_map"]] == canon_ids, "blocker", "the source map does not follow the scenes", None, "source_map", {}, "timeline_build")
        D = T["profile"]["duration_frames"]
        ints = all(isinstance(i[k], int) for t in T["tracks"] for i in t["items"] for k in ("start_frame", "end_frame"))
        r.check(S, "time.integer_frames", ints, "blocker", "a frame value is not an integer", None, "frames", {}, "timeline_build")
        for c in clips:
            r.check(S, "time.interval_valid", 0 <= c["start_frame"] < c["end_frame"] <= D, "blocker", f"{c['scene_id']}: [{c['start_frame']}, {c['end_frame']}) is not inside [0, {D})", c["scene_id"], c["item_id"],
                    {"interval": [c["start_frame"], c["end_frame"]], "duration": D}, "timeline_build")
            r.check(S, "time.frames_from_seconds", (c["start_frame"], c["end_frame"]) == (mp.fr(c["source_start_seconds"], fps), mp.fr(c["source_end_seconds"], fps)), "blocker", f"{c['scene_id']}: the frames are not the ones of the shared rule", c["scene_id"], c["item_id"], {}, "timeline_build")
            r.check(S, "time.layers_inside_clip", all(c["start_frame"] <= l["start_frame"] < l["end_frame"] <= c["end_frame"] for l in c["layers"]), "blocker", f"{c['scene_id']}: a layer lies outside its scene", c["scene_id"], c["item_id"], {}, "timeline_build")
        r.check(S, "time.contiguous_no_overlap", all(a["end_frame"] == b["start_frame"] for a, b in zip(clips, clips[1:])) and (not clips or (clips[0]["start_frame"] == 0 and clips[-1]["end_frame"] == D)), "blocker",
                "the scene clips overlap, leave a hole or do not cover the video", None, "scenes", {}, "timeline_build")
        r.check(S, "time.gaps_preserved", all(g["policy"] == "hold_previous_scene" and g["mutates_source_interval"] is False and g["end_frame"] >= g["start_frame"] for g in T["gap_intervals"]), "blocker", "a gap lost its policy or moved a source interval", None, "gaps", {}, "timeline_build")
        au = T["tracks"][0]["items"][0]
        r.check(S, "audio.covers_video", au["start_frame"] == 0 and au["end_frame"] == min(D, mp.fr(T["profile"]["duration_seconds_source"], fps)) and au["playback_rate"] == 1.0, "blocker", "the audio clip does not cover the audio's own length at normal speed", None, "audio_clip", {}, "timeline_build")
        r.check(S, "audio.not_duplicated", len(T["tracks"][0]["items"]) == 1, "blocker", "the audio is placed more than once", None, "audio_clip", {}, "timeline_build")
        lids = [l["layer_id"] for c in clips for l in c["layers"]]
        r.check(S, "ref.layer_ids_unique", len(lids) == len(set(lids)), "blocker", "a layer id appears twice", None, "layers", {}, "timeline_build")
        r.check(S, "ref.composition_scene_resolves", all(self.comp["scenes"][c["composition_scene_id"] - 1]["id"] == c["composition_scene_id"] and c["layer_refs"] == [l["layer_id"] for l in c["layers"]] for c in clips), "blocker",
                "a composition reference does not resolve", None, "scenes", {}, "timeline_build")
        r.check(S, "ref.layer_counts", all(len(c["layers"]) == len(self.comp["scenes"][c["composition_scene_id"] - 1]["layers"]) for c in clips), "blocker", "a scene lost or gained a layer", None, "layers", {}, "timeline_build")
        if self._motion():
            r.check(S, "ref.descriptors_resolve", all(c["descriptor_refs"] and len(set(c["descriptor_refs"])) == len(c["descriptor_refs"]) for c in clips), "blocker", "a scene has no or duplicated Motion Generation descriptors", None, "descriptors", {}, "timeline_build")
        ref = au["source_ref"]
        r.check(S, "ref.audio_resolves", bool(ref) and (self.pdir / ref).resolve().is_relative_to(self.pdir.resolve()) and (self.pdir / ref).is_file(), "blocker", "the audio reference does not resolve inside the project", None, "audio_clip", {}, "timeline_build")
        by_pair: dict[int, list] = {}
        for t in T["transitions"]:
            by_pair.setdefault(t["boundary_frame"], []).append(t["transition_id"])
        r.check(S, "trans.one_per_boundary", all(len(v) == 1 for v in by_pair.values()), "blocker", "two transitions at one boundary", None, "transitions", {}, "timeline_build")
        r.check(S, "trans.window_valid", all(t["supported"] and t["start_frame"] == t["boundary_frame"] and 1 <= t["applied_frames"] <= t["requested_frames"] and t["end_frame"] <= D and t["moves_scene_boundaries"] is False for t in T["transitions"]),
                "blocker", "a transition window is invalid", None, "transitions", {}, "timeline_build")
        r.check(S, "trans.scene_times_unchanged", all(next(c for c in clips if c["scene_id"] == t["to_scene"])["start_frame"] == t["boundary_frame"] for t in T["transitions"]), "blocker", "a transition moves a scene boundary", None, "transitions", {}, "timeline_build")
        r.check(S, "mode.respected", (T["profile"]["mode"] == "motion_only") == (not store.uses_images(self.pdir)), "blocker", "the timeline's visual mode is not the project's", None, "mode", {}, "timeline_build")
        dis = T["disclosures"]
        r.check(S, "visual.required_not_hidden", dis["required_not_drawn"] == 0 or dis["accepted_exceptions"] > 0, "blocker", "a required visual is not drawn and no exception exists", None, "disclosures", dis, "motion_generation")

    # --- run ---
    def run(self, say) -> tuple[list[dict], dict]:
        order = ["input_discovery", "freshness_gate", "settings", "scene_mapping", "frame_timing", "video_track", "audio_track", "transitions_gaps", "assembly", "validation"]
        halted, recs = None, [self._record("request_lock", 0, None)]
        self.fp = fingerprint(self.pdir, self.aspect)
        for k, sid in enumerate(order):
            say(8 + 78 * k / len(order))
            if halted and sid != "freshness_gate":
                recs.append(self._record(sid, 0, halted))
                continue
            t0 = time.perf_counter()
            if sid == "validation":
                self.T["source_fingerprint"], self.T["timeline_id"] = self.fp, f"timeline_{self.fp[:12]}"
            getattr(self, "stage_" + sid)()
            rec = self._record(sid, round((time.perf_counter() - t0) * 1000), None)
            recs.append(rec)
            if rec["status"] == "blocked" and sid in ("input_discovery", "freshness_gate", "settings", "scene_mapping", "frame_timing"):
                halted = f"{rec['label']} found a blocker: fix it in its owner stage first"
        return recs, self.T

    def _record(self, sid: str, ms: int, halted: str | None) -> dict:
        n = next(i for i, s in enumerate(STAGES) if s[0] == sid)
        c, fs = self.r.counts[sid], self.r.of(sid)
        if halted:
            status = "skipped_due_to_dependency"
        else:
            status = "blocked" if any(f["severity"] in BLOCKING for f in fs) else "warning" if (c["skipped"] or any(f["severity"] == "warning" for f in fs)) else "completed"
        return {"n": n + 1, "stage_id": sid, "name": STAGES[n][2], "label": STAGES[n][1], "status": status, "checks_passed": c["passed"], "checks_total": c["total"], "checks_skipped": c["skipped"],
                "finding_ids": [f["finding_id"] for f in fs], "duration_ms": ms, **({"detail": halted} if halted else {})}


# ---------- run, persist, publish ----------
def run(pdir: Path, aspect: str, progress=None) -> dict:
    """Build, validate, write the attempt and (only when it passes) publish the timeline and its report. Returns the report. A blocked build returns a `blocked` report and publishes nothing."""
    say = progress or (lambda p, eta=None: None)
    key = str(pdir.resolve())
    with _guard:
        lock = _running.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        raise BuildError("a timeline build is already running for this project")
    try:
        return _run_locked(pdir, aspect, say)
    finally:
        lock.release()


def _run_locked(pdir: Path, aspect: str, say) -> dict:
    t0 = time.perf_counter()
    digests = input_digests(pdir, aspect)
    fp = fingerprint(pdir, aspect, digests)
    cur = load(pdir, aspect)
    if cur and cur["current"]:                                                # the same inputs already have a published, valid timeline: reuse it
        return {**cur["report"], "reused": True}
    rec = Rec()
    b = Builder(pdir, aspect, rec)
    try:
        recs, T = b.run(say)
    except Exception as e:                                                    # a builder that crashed never publishes
        rep = _report(pdir, aspect, rec, [], {}, digests, fp, "failed", t0)
        rep["error"] = f"{type(e).__name__}: {e}"[:400]
        _write_attempt(pdir, aspect, rep)
        raise
    say(88)
    rep = _report(pdir, aspect, rec, recs, T, digests, fp, None, t0)
    if rep["status"] in OK:
        _publish(pdir, aspect, T, rep, fp)
    else:
        rep["stages"].append(_persist_record("blocked", "not published: the last good timeline is kept", 0))
        _write_attempt(pdir, aspect, rep)
    say(100)
    return rep


def _report(pdir: Path, aspect: str, rec: Rec, recs: list[dict], T: dict, digests: dict, fp: str, forced: str | None, t0: float) -> dict:
    findings = sorted(rec.findings.values(), key=lambda f: (SEVERITIES.index(f["severity"]), f["scene_id"] or "", f["finding_id"]))
    n = lambda sev: sum(1 for f in findings if f["severity"] == sev)
    passed, total, skipped = (sum(s[k] for s in recs) for k in ("checks_passed", "checks_total", "checks_skipped"))
    d = (T or {}).get("disclosures", {})
    disclosed = d.get("optional_not_drawn", 0) + d.get("approximate", 0) + d.get("accepted_exceptions", 0) + d.get("required_not_drawn", 0)
    if forced:
        status = forced
    elif n("blocker") or n("error") or any(s["status"] in ("blocked", "skipped_due_to_dependency") for s in recs):
        status = "blocked"
    elif n("warning") or disclosed or skipped:
        status = "completed_with_warnings"
    else:
        status = "completed"
    tl = (T or {}).get("tracks")
    clips = tl[1]["items"] if tl else []
    nxt = {"completed": "review_then_approve_when_you_choose", "completed_with_warnings": "review_the_warnings_then_approve_when_you_choose", "blocked": "resolve_blockers_in_the_owner_stage", "failed": "see_error_and_build_again"}
    return {"schema_version": SCHEMA, "phase": "timeline_build", "project_id": pdir.name, "aspect": aspect, "status": status,
            "readiness": {"completed": "ready", "completed_with_warnings": "ready_with_warnings"}.get(status, status), "source_fingerprint": fp,
            "timeline_fingerprint": semantic_digest(T) if T and status in OK else None, "builder": {"version": VERSION, "rule_set": RULE_SET}, "policies": POLICY,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "inputs": digests, "stages": recs,
            "counts": {"scenes": len(clips), "tracks": len(tl or []), "items": sum(len(t["items"]) for t in tl or []), "layers": sum(len(c["layers"]) for c in clips), "transitions": len((T or {}).get("transitions", [])),
                       "gaps": len((T or {}).get("gap_intervals", [])), "duration_frames": (T or {}).get("profile", {}).get("duration_frames"), "fps": (T or {}).get("profile", {}).get("fps")},
            # a check that does not pass is `failed` only when its finding blocks (blocker/error); a policy-permitted warning is `warned`: passed + failed + warned + info = total
            "checks": {"passed": passed, "failed": sum(f["occurrences"] for f in findings if f["severity"] in BLOCKING), "warned": sum(f["occurrences"] for f in findings if f["severity"] == "warning"),
                       "info": sum(f["occurrences"] for f in findings if f["severity"] == "info"), "warnings": n("warning"), "skipped": skipped, "total": total},
            "summary": {"blockers": n("blocker"), "errors": n("error"), "warnings": n("warning"), "info": n("info"), "disclosed_not_drawn_or_approximate": disclosed},
            "findings": findings, "disclosures": d, "audio_ducking": (T or {}).get("audio_ducking", {}), "persistence": {"published": False, "written": False, "read_back_ok": False, "digest_equal": False, "inputs_rechecked": False},
            "approval": {"status": "not_approved", "approved_fingerprint": None}, "timings_seconds": {"build": round(time.perf_counter() - t0, 3)}, "error": None, "next_action": nxt.get(status, "build_again"),
            "note": "structural validation only: no video was rendered and the playback was not watched; Timeline Approval is a separate, explicit step"}


def _persist_record(status: str, detail: str, ms: int) -> dict:
    return {"n": 12, "stage_id": "persist", "name": STAGES[11][2], "label": STAGES[11][1], "status": status, "checks_passed": 0, "checks_total": 0, "checks_skipped": 0, "finding_ids": [], "duration_ms": ms, "detail": detail}


def _write_attempt(pdir: Path, aspect: str, rep: dict) -> None:
    f = pdir / names(aspect)["attempt"]
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    with store._info_lock(pdir):                                                 # the store's own per-project lock: a reader never meets os.replace on Windows
        os.replace(tmp, f)


def _publish(pdir: Path, aspect: str, T: dict, rep: dict, fp: str) -> None:
    """temp write -> read back -> same canonical digest -> inputs again -> backup of the last good pair -> atomic replace -> read back the pair. Any failure keeps the last good pair."""
    t0 = time.perf_counter()
    nm = names(aspect)
    tl_f, rp_f = pdir / nm["timeline"], pdir / nm["report"]
    tl_tmp, rp_tmp = tl_f.with_name(tl_f.name + ".tmp"), rp_f.with_name(rp_f.name + ".tmp")
    p = rep["persistence"]
    try:
        tl_tmp.write_text(json.dumps(T, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        back = json.loads(tl_tmp.read_text(encoding="utf-8"))
        p.update(written=True, read_back_ok=isinstance(back, dict) and back.get("schema_version") == SCHEMA, digest_equal=semantic_digest(back) == semantic_digest(T) == rep["timeline_fingerprint"])
        p["inputs_rechecked"] = fingerprint(pdir, aspect) == fp
        if not (p["read_back_ok"] and p["digest_equal"] and p["inputs_rechecked"]):
            stale = not p["inputs_rechecked"]
            why = "an input changed while the timeline was built: build again" if stale else "the timeline read back from disk is not what was built"
            rep.update(status="blocked" if stale else "failed", readiness="stale" if stale else "failed", error=why, timeline_fingerprint=None)
            rep["stages"].append(_persist_record("blocked", why, round((time.perf_counter() - t0) * 1000)))
            _write_attempt(pdir, aspect, rep)
            tl_tmp.unlink(missing_ok=True)
            return
        if tl_f.exists() and rp_f.exists():                                       # the last good pair is kept before it is replaced
            old = mp._read(rp_f) or {}
            dest = pdir / nm["backup"] / f"{time.strftime('%Y%m%d-%H%M%S')}_{str(old.get('source_fingerprint', 'unknown'))[:8]}"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tl_f, dest / tl_f.name)
            shutil.copy2(rp_f, dest / rp_f.name)
        p["published"] = True
        rep["stages"].append(_persist_record("completed", "written, read back, digest equal, inputs unchanged, last good pair backed up, published", round((time.perf_counter() - t0) * 1000)))
        rp_tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        with store._info_lock(pdir):
            os.replace(tl_tmp, tl_f)
            os.replace(rp_tmp, rp_f)
        cur = load(pdir, aspect)                                                   # the status is the persisted pair's, not the in-memory object's
        if not cur or not cur["coherent"] or cur["status"] not in OK:
            raise BuildError("the published timeline and report read back do not match")
        _write_attempt(pdir, aspect, rep)
    except Exception as e:
        p["published"] = False
        rep.update(status="failed", readiness="failed", error=f"{type(e).__name__}: {e}"[:300])
        _write_attempt(pdir, aspect, rep)
        for f in (tl_tmp, rp_tmp):
            f.unlink(missing_ok=True)
        raise


# ---------- reading ----------
def _read_locked(f: Path):
    with store._info_lock(f.parent):
        return mp._read(f)


def load(pdir: Path, aspect: str) -> dict | None:
    """The state of Stage 11 from what is on disk: {status, current, stale, coherent, report, attempt, published, timeline_available}. `status` is the published pair's (completed / completed_with_warnings) only while its
    source fingerprint is the current one; otherwise `stale`; a newer blocked / failed attempt on the CURRENT inputs wins. None when nothing was ever built or attempted."""
    nm = names(aspect)
    rep, T, attempt = _read_locked(pdir / nm["report"]), _read_locked(pdir / nm["timeline"]), _read_locked(pdir / nm["attempt"])
    if not isinstance(rep, dict) and not isinstance(attempt, dict):
        return None
    try:
        cur = fingerprint(pdir, aspect)
    except OSError:
        cur = None
    coherent = isinstance(rep, dict) and isinstance(T, dict) and rep.get("timeline_fingerprint") == semantic_digest(T) and T.get("source_fingerprint") == rep.get("source_fingerprint")
    pair_current = coherent and rep.get("source_fingerprint") == cur
    if isinstance(attempt, dict) and attempt.get("source_fingerprint") == cur and attempt.get("status") in ("blocked", "failed"):
        status, report = attempt["status"], attempt
    elif pair_current:
        status, report = rep["status"], rep
    elif isinstance(rep, dict):
        status, report = "stale", rep
    else:
        status, report = ("stale" if attempt.get("source_fingerprint") != cur else attempt["status"]), attempt
    return {"status": status, "current": pair_current and status in OK, "stale": status == "stale", "coherent": coherent, "report": report, "attempt": attempt, "published": rep if isinstance(rep, dict) else None,
            "timeline_available": isinstance(T, dict), "current_fingerprint": cur}


def timeline(pdir: Path, aspect: str) -> dict | None:
    t = _read_locked(pdir / names(aspect)["timeline"])
    return t if isinstance(t, dict) else None


def blockers(pdir: Path, aspect: str) -> list[str]:
    """Why Stage 12 (Timeline Approval) and Render Video must not treat the timeline as current (empty = a valid, current built timeline exists). Read now, nothing is started."""
    st = load(pdir, aspect)
    if st is None:
        return ["the timeline has not been built yet: run Timeline Build"]
    if st["current"]:
        return []
    if st["status"] == "stale":
        return ["the timeline was built from inputs that changed since: build it again"]
    first = next((f for f in st["report"].get("findings", []) if f["severity"] in BLOCKING), None)
    return [f"Timeline Build is {st['status']}" + (f": {first['message']}" if first else "")]
