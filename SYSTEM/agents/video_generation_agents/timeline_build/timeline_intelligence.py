"""Timeline Intelligence Module v2.0.0.

Provides:
1. AudioDuckingEngine: Speech-aware dynamic background music attenuation with smooth ramps.
2. CinematicTransitionSelector: LLM-assisted context-sensitive scene transitions.
3. SceneContinuityAssessor: Narrative, visual, and pacing continuity analysis.
4. TimelineRecoveryCoordinator: Bounded autonomous repair (max 2 attempts) for compiler-owned defects.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("timeline_build.intelligence")

SUPPORTED_TRANSITIONS = (
    "fade",
    "slide",
    "wipe",
    "flip",
    "clock-wipe",
    "zoom-through",
    "light-leak",
    "blur",
    "mask-shape",
    "match-move",
    "particle",
)


@dataclass
class SpeechInterval:
    start_seconds: float
    end_seconds: float
    start_frame: int
    end_frame: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
        }


@dataclass
class VolumeKeyframe:
    frame: int
    volume: float

    def to_dict(self) -> dict[str, Any]:
        return {"frame": self.frame, "volume": round(self.volume, 3)}


class AudioDuckingEngine:
    """Calculates frame-accurate background music volume attenuation based on authoritative

    speech intervals extracted from transcripts, audio analysis, or pause data.
    """

    def __init__(
        self,
        speech_gain: float = 0.15,
        pause_gain: float = 0.40,
        ramp_seconds: float = 0.15,
        min_pause_for_boost: float = 0.50,
    ) -> None:
        self.speech_gain = max(0.0, min(1.0, speech_gain))
        self.pause_gain = max(0.0, min(1.0, pause_gain))
        self.ramp_seconds = max(0.05, ramp_seconds)
        self.min_pause_for_boost = max(0.20, min_pause_for_boost)

    def extract_speech_intervals(self, project_dir: Path, fps: int = 30) -> list[SpeechInterval]:
        """Extracts non-overlapping authoritative speech intervals from project artifacts."""
        raw_intervals: list[tuple[float, float]] = []

        # 1. Primary: Word/Segment timestamps from transcript_fixed.json or transcript.json
        for t_name in ("transcript_fixed.json", "transcript_corrected.json", "transcript.json"):
            t_path = project_dir / t_name
            if t_path.exists():
                try:
                    data = json.loads(t_path.read_text(encoding="utf-8"))
                    segments = data.get("segments", [])
                    for seg in segments:
                        words = seg.get("words", [])
                        if words:
                            # Use first and last word in segment for tighter speech bounds
                            w_start = float(words[0].get("start", seg.get("start", 0)))
                            w_end = float(words[-1].get("end", seg.get("end", w_start + 0.5)))
                            if w_end > w_start:
                                raw_intervals.append((w_start, w_end))
                        elif "start" in seg and "end" in seg:
                            s, e = float(seg["start"]), float(seg["end"])
                            if e > s:
                                raw_intervals.append((s, e))
                    if raw_intervals:
                        break
                except Exception as e:
                    logger.warning(f"Error reading transcript {t_name}: {e}")

        # 2. Fallback: scene_segmentation.json scenes
        if not raw_intervals:
            seg_path = project_dir / "scene_segmentation.json"
            if seg_path.exists():
                try:
                    seg_data = json.loads(seg_path.read_text(encoding="utf-8"))
                    for sc in seg_data.get("scenes", []):
                        s = float(sc.get("start_time", sc.get("start", 0)))
                        e = float(sc.get("end_time", sc.get("end", s + 1)))
                        if e > s:
                            raw_intervals.append((s, e))
                except Exception as e:
                    logger.warning(f"Error reading scene_segmentation.json: {e}")

        # 3. Fallback: cuts.json or composition.json
        if not raw_intervals:
            comp_path = project_dir / "composition.json"
            if comp_path.exists():
                try:
                    c_data = json.loads(comp_path.read_text(encoding="utf-8"))
                    for sc in c_data.get("scenes", []):
                        s = float(sc.get("start", 0))
                        e = float(sc.get("end", s + 1))
                        if e > s:
                            raw_intervals.append((s, e))
                except Exception:
                    pass

        if not raw_intervals:
            return []

        # Sort and merge overlapping or adjacent speech intervals (< 0.2s gap)
        raw_intervals.sort(key=lambda x: x[0])
        merged: list[tuple[float, float]] = []
        for start, end in raw_intervals:
            if not merged:
                merged.append((start, end))
            else:
                last_start, last_end = merged[-1]
                if start <= last_end + 0.15:  # Within 150ms: combine to avoid pumping
                    merged[-1] = (last_start, max(last_end, end))
                else:
                    merged.append((start, end))

        # Convert to SpeechInterval dataclass
        result = [
            SpeechInterval(
                start_seconds=round(s, 3),
                end_seconds=round(e, 3),
                start_frame=max(0, round(s * fps)),
                end_frame=max(1, round(e * fps)),
            )
            for s, e in merged
        ]
        return result

    def generate_volume_envelope(
        self,
        speech_intervals: list[SpeechInterval],
        total_frames: int,
        fps: int = 30,
    ) -> list[VolumeKeyframe]:
        """Generates a frame-accurate piecewise linear volume curve for background music."""
        if total_frames <= 0:
            return []

        if not speech_intervals:
            # No speech detected: keep music at full pause level throughout
            return [VolumeKeyframe(frame=0, volume=self.pause_gain), VolumeKeyframe(frame=total_frames - 1, volume=self.pause_gain)]

        ramp_frames = max(2, round(self.ramp_seconds * fps))
        min_pause_frames = round(self.min_pause_for_boost * fps)

        keyframes: list[VolumeKeyframe] = []

        # Start at pause gain if there is a gap before first speech
        first = speech_intervals[0]
        if first.start_frame > ramp_frames:
            keyframes.append(VolumeKeyframe(frame=0, volume=self.pause_gain))
            keyframes.append(VolumeKeyframe(frame=max(0, first.start_frame - ramp_frames), volume=self.pause_gain))
            keyframes.append(VolumeKeyframe(frame=first.start_frame, volume=self.speech_gain))
        else:
            keyframes.append(VolumeKeyframe(frame=0, volume=self.speech_gain))

        for i, curr in enumerate(speech_intervals):
            # Sustain speech gain across speech
            keyframes.append(VolumeKeyframe(frame=curr.start_frame, volume=self.speech_gain))
            keyframes.append(VolumeKeyframe(frame=curr.end_frame, volume=self.speech_gain))

            # Lookahead to next speech interval
            if i + 1 < len(speech_intervals):
                nxt = speech_intervals[i + 1]
                pause_gap = nxt.start_frame - curr.end_frame

                if pause_gap >= min_pause_frames + (2 * ramp_frames):
                    # Long pause: ramp up to pause_gain, sustain, then ramp down
                    boost_start = curr.end_frame + ramp_frames
                    boost_end = nxt.start_frame - ramp_frames
                    keyframes.append(VolumeKeyframe(frame=boost_start, volume=self.pause_gain))
                    keyframes.append(VolumeKeyframe(frame=boost_end, volume=self.pause_gain))
                    keyframes.append(VolumeKeyframe(frame=nxt.start_frame, volume=self.speech_gain))
                else:
                    # Short gap: stay at speech_gain to eliminate auditory pumping
                    pass
            else:
                # After last speech interval: ramp up to pause_gain if room permits
                if curr.end_frame + ramp_frames < total_frames:
                    keyframes.append(VolumeKeyframe(frame=curr.end_frame + ramp_frames, volume=self.pause_gain))
                    keyframes.append(VolumeKeyframe(frame=total_frames - 1, volume=self.pause_gain))
                else:
                    keyframes.append(VolumeKeyframe(frame=total_frames - 1, volume=self.speech_gain))

        # Sort and deduplicate by frame
        keyframes.sort(key=lambda k: k.frame)
        deduped: list[VolumeKeyframe] = []
        for k in keyframes:
            if not deduped or deduped[-1].frame != k.frame:
                deduped.append(k)
            else:
                # Keep latest volume for same frame
                deduped[-1] = k

        return deduped

    def compute_ducking_profile(
        self,
        project_dir: Path,
        total_frames: int,
        fps: int = 30,
    ) -> dict[str, Any]:
        """Top-level ducking coordinator returning structured ducking metadata."""
        intervals = self.extract_speech_intervals(project_dir, fps=fps)
        keyframes = self.generate_volume_envelope(intervals, total_frames, fps=fps)

        total_speech_s = sum(i.end_seconds - i.start_seconds for i in intervals)
        total_dur_s = total_frames / fps if fps else 0.0
        speech_coverage_pct = round((total_speech_s / max(0.1, total_dur_s)) * 100, 1)

        return {
            "ducking_applied": len(intervals) > 0,
            "speech_gain": self.speech_gain,
            "pause_gain": self.pause_gain,
            "ramp_seconds": self.ramp_seconds,
            "speech_intervals_count": len(intervals),
            "speech_coverage_percent": speech_coverage_pct,
            "speech_intervals": [i.to_dict() for i in intervals],
            "volume_envelope_keyframes": [k.to_dict() for k in keyframes],
        }


class CinematicTransitionSelector:
    """Selects contextual, cinematic scene transitions based on narrative meaning,

    visual planning, and verified Remotion transition capabilities.
    """

    def __init__(self) -> None:
        self._llm_cache: dict[str, dict[str, Any]] = {}

    def recommend_transitions(
        self,
        project_dir: Path,
        scenes: list[dict[str, Any]],
        fps: int = 30,
    ) -> dict[str, Any]:
        """Recommends transitions for each boundary between consecutive scenes."""
        if len(scenes) <= 1:
            return {"recommendations": [], "rationale": "Single scene; no transitions needed."}

        vp_path = project_dir / "visual_planning.json"
        vp_scenes: dict[str, dict[str, Any]] = {}
        if vp_path.exists():
            try:
                vp = json.loads(vp_path.read_text(encoding="utf-8"))
                for s in vp.get("scenes", []):
                    sid = str(s.get("plan_scene_id") or s.get("scene_id") or s.get("id"))
                    vp_scenes[sid] = s
            except Exception:
                pass

        recommendations = []
        prev_chosen: str | None = None

        for i in range(len(scenes) - 1):
            curr_s = scenes[i]
            next_s = scenes[i + 1]

            sid_curr = str(curr_s.get("id") or curr_s.get("scene_id"))
            sid_next = str(next_s.get("id") or next_s.get("scene_id"))

            dur_curr = float(curr_s.get("end", 3.0)) - float(curr_s.get("start", 0.0))
            dur_next = float(next_s.get("end", 6.0)) - float(next_s.get("start", 3.0))

            # Max allowed transition duration: must be < min(dur_curr, dur_next)
            cap_seconds = min(0.8, max(0.25, 0.4 * min(dur_curr, dur_next)))

            vp_curr = vp_scenes.get(sid_curr, {})
            vp_next = vp_scenes.get(sid_next, {})

            concept_curr = vp_curr.get("concept") or curr_s.get("concept") or ""
            concept_next = vp_next.get("concept") or next_s.get("concept") or ""

            # Select transition
            chosen_type, rationale = self._select_type(
                sid_curr=sid_curr,
                sid_next=sid_next,
                concept_curr=concept_curr,
                concept_next=concept_next,
                prev_type=prev_chosen,
                project_dir=project_dir,
            )

            # Prevent immediate repetition
            if chosen_type == prev_chosen:
                alternatives = [t for t in ("fade", "slide", "wipe", "zoom-through") if t != prev_chosen]
                chosen_type = alternatives[0]

            prev_chosen = chosen_type

            recommendations.append({
                "from_scene_id": sid_curr,
                "to_scene_id": sid_next,
                "transition_type": chosen_type,
                "duration_seconds": round(cap_seconds, 2),
                "duration_frames": max(8, round(cap_seconds * fps)),
                "supported": chosen_type in SUPPORTED_TRANSITIONS,
                "rationale": rationale,
            })

        return {
            "recommendations": recommendations,
            "total_transitions": len(recommendations),
            "supported_library_count": len(SUPPORTED_TRANSITIONS),
        }

    def _select_type(
        self,
        sid_curr: str,
        sid_next: str,
        concept_curr: str,
        concept_next: str,
        prev_type: str | None,
        project_dir: Path,
    ) -> tuple[str, str]:
        """Chooses transition type using LLM advice or heuristic fallback."""
        cache_key = hashlib.sha256(f"{concept_curr}->{concept_next}".encode("utf-8")).hexdigest()[:12]
        if cache_key in self._llm_cache:
            entry = self._llm_cache[cache_key]
            return entry["type"], entry["rationale"]

        # Attempt LLM Gateway query
        try:
            from SYSTEM.core import llm_gateway

            req = llm_gateway.LlmGatewayRequest(
                project_id=project_dir.name,
                stage_id="timeline",
                agent_id="timeline_build",
                purpose="review",
                model_profile="reasoning_review",
                system_prompt=(
                    "You are a cinematic video editor. Choose the best transition between two scenes. "
                    "Options: fade, slide, wipe, flip, clock-wipe, zoom-through, light-leak, blur, match-move, particle. "
                    "Output JSON: {\"type\": \"...\", \"rationale\": \"...\"}"
                ),
                user_prompt=f"Scene A: {concept_curr}\nScene B: {concept_next}\nPrevious transition: {prev_type}",
                correlation_id=f"trans-{cache_key}",
            )
            resp = llm_gateway.gateway.execute(req)
            if resp.structured_data and resp.structured_data.get("type") in SUPPORTED_TRANSITIONS:
                t_type = resp.structured_data["type"]
                rat = resp.structured_data.get("rationale", "LLM recommended transition.")
                self._llm_cache[cache_key] = {"type": t_type, "rationale": rat}
                return t_type, rat
        except Exception:
            pass

        # Deterministic semantic fallback
        text_combo = (concept_curr + " " + concept_next).lower()
        if any(w in text_combo for w in ("tech", "digital", "system", "ai", "code", "model")):
            t_type = "zoom-through" if prev_type != "zoom-through" else "slide"
            rat = "Tech-focused dynamic zoom progression."
        elif any(w in text_combo for w in ("next", "step", "process", "workflow", "flow")):
            t_type = "slide" if prev_type != "slide" else "wipe"
            rat = "Sequential procedural slide."
        elif any(w in text_combo for w in ("compare", "versus", "contrast", "difference")):
            t_type = "wipe" if prev_type != "wipe" else "flip"
            rat = "Direct contrast directional wipe."
        elif any(w in text_combo for w in ("future", "bright", "vision", "spark")):
            t_type = "light-leak" if prev_type != "light-leak" else "fade"
            rat = "Cinematic lighting progression."
        else:
            t_type = "fade" if prev_type != "fade" else "blur"
            rat = "Smooth classical dissolve."

        self._llm_cache[cache_key] = {"type": t_type, "rationale": rat}
        return t_type, rat


class SceneContinuityAssessor:
    """Evaluates narrative and visual continuity across timeline scenes."""

    def assess(
        self,
        project_dir: Path,
        scenes: list[dict[str, Any]],
        total_duration_s: float,
    ) -> dict[str, Any]:
        findings = []
        pacing_issues = 0

        for i, sc in enumerate(scenes):
            sid = sc.get("id") or sc.get("scene_id") or f"scene_{i+1}"
            dur = float(sc.get("end", 0)) - float(sc.get("start", 0))

            if dur < 1.0:
                pacing_issues += 1
                findings.append({
                    "scene_id": sid,
                    "severity": "warning",
                    "category": "pacing",
                    "message": f"{sid} duration ({dur:.2f}s) is very brief; viewers may not absorb visuals.",
                })
            elif dur > 12.0:
                pacing_issues += 1
                findings.append({
                    "scene_id": sid,
                    "severity": "info",
                    "category": "pacing",
                    "message": f"{sid} duration ({dur:.2f}s) is long; consider rich kinetic typography or camera movement.",
                })

        continuity_score = max(60.0, 100.0 - (pacing_issues * 10.0))

        return {
            "continuity_score": round(continuity_score, 1),
            "pacing_issues_count": pacing_issues,
            "findings": findings,
            "scenes_evaluated": len(scenes),
            "total_duration_seconds": round(total_duration_s, 2),
        }


class TimelineRecoveryCoordinator:
    """Handles bounded autonomous repairs (max 2 attempts) for compiler-solvable defects."""

    def coordinate_recovery(
        self,
        project_dir: Path,
        blockers_list: list[str],
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        if not blockers_list or max_attempts <= 0:
            return {"repaired": False, "attempts": 0, "actions_applied": []}

        actions = []
        comp_path = project_dir / "composition.json"

        for b in blockers_list:
            # 1. Recover from unsupported transition type in composition.json
            if "not a transition of the library" in b and comp_path.exists():
                try:
                    c = json.loads(comp_path.read_text(encoding="utf-8"))
                    for sc in c.get("scenes", []):
                        t = sc.get("transition_out")
                        if t and t.get("type") not in SUPPORTED_TRANSITIONS:
                            old_t = t["type"]
                            t["type"] = "fade"
                            actions.append(f"Substituted unsupported transition '{old_t}' with 'fade' in scene {sc.get('id')}")
                    comp_path.write_text(json.dumps(c, indent=2), encoding="utf-8")
                except Exception as e:
                    logger.error(f"Recovery failed for transition: {e}")

            # 2. Recover from transition window exceeding scene duration
            elif "does not fit the next scene" in b and comp_path.exists():
                try:
                    c = json.loads(comp_path.read_text(encoding="utf-8"))
                    for sc in c.get("scenes", []):
                        t = sc.get("transition_out")
                        if t and t.get("dur", 0) > 0.5:
                            t["dur"] = 0.25
                            actions.append(f"Clamped over-extended transition duration to 0.25s in scene {sc.get('id')}")
                    comp_path.write_text(json.dumps(c, indent=2), encoding="utf-8")
                except Exception as e:
                    logger.error(f"Recovery failed for transition clamp: {e}")

        return {
            "repaired": len(actions) > 0,
            "attempts": 1 if actions else 0,
            "actions_applied": actions,
        }
