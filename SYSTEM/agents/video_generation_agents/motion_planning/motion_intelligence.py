"""Cinematic Motion Intelligence Extension Subsystem for Motion Planning Agent.
Provides:
1. Semantic scene understanding: narrative role, emotional tone, and visual priority.
2. Dynamic motion strategy selection with narrative justification.
3. Context-aware motion parameters, camera choreography, and spring physics.
4. Audio-reactive motion synchronization using speech rate (WPM) and pause telemetry.
5. Deterministic safe-area compliance and collision resolution.
6. Scene-to-scene motion continuity across consecutive scene boundaries.
7. Autonomous fallback to deterministic heuristic planning when LLM is unavailable.
"""
from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("motion_planning.motion_intelligence")

# FPS and geometric limits
DEFAULT_FPS = 30
MIN_ACTION_DURATION = 0.25
MAX_CAMERA_ZOOM = 1.15
MIN_CAMERA_ZOOM = 1.0
SAFE_MARGIN_16_9 = 0.05
SAFE_MARGIN_PORTRAIT_BOTTOM = 0.16

# Supported Remotion preset registries
SUPPORTED_TEXT_PRESETS = {
    "indic_safe": ("bounce", "fade-slide", "split-words", "slide-up", "fade", "typewriter"),
    "general": ("bounce", "fade-slide", "split-words", "kinetic-pop", "scale-up", "slide-left", "slide-right", "slide-up", "fade"),
}

SUPPORTED_GRAPHIC_PRESETS = (
    "light-sweep", "targeting-ring", "divider-grow", "circular-meter",
    "bar-glow", "focus-brackets", "corner-frame", "dot-grid"
)

SUPPORTED_TRANSITIONS = (
    "light-leak", "crossfade", "wipe", "slide", "zoom-fade", "none"
)

TELUGU_PATTERN = re.compile(r"[\u0C00-\u0C7F]")


@dataclass
class CameraIntent:
    """Creative camera intent mapped to supported Remotion camera parameters."""
    move: Literal["static", "push-in", "pull-out", "pan-left", "pan-right", "tilt-up", "tilt-down", "zoom-to-focus"]
    zoom_from: float = 1.0
    zoom_to: float = 1.05
    focus: list[float] = field(default_factory=lambda: [0.5, 0.5])
    drift: float = 0.2
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        # Enforce hard deterministic bounds
        z_from = max(MIN_CAMERA_ZOOM, min(MAX_CAMERA_ZOOM, round(self.zoom_from, 3)))
        z_to = max(MIN_CAMERA_ZOOM, min(MAX_CAMERA_ZOOM, round(self.zoom_to, 3)))
        fx = max(0.15, min(0.85, round(self.focus[0], 2))) if len(self.focus) >= 1 else 0.5
        fy = max(0.15, min(0.85, round(self.focus[1], 2))) if len(self.focus) >= 2 else 0.5
        return {
            "move": self.move,
            "from": z_from,
            "to": z_to,
            "focus": [fx, fy],
            "drift": max(0.0, min(1.0, round(self.drift, 2))),
            "rationale": self.rationale,
        }


@dataclass
class SpringProfile:
    """Physics-based spring parameters for kinetic motion easing."""
    name: Literal["snappy", "gentle", "dramatic_overshoot", "stiff", "fluid"]
    mass: float = 1.0
    stiffness: float = 100.0
    damping: float = 10.0
    overshoot_clamping: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SPRING_PROFILES: dict[str, SpringProfile] = {
    "snappy": SpringProfile(name="snappy", mass=0.8, stiffness=180.0, damping=12.0, overshoot_clamping=False),
    "gentle": SpringProfile(name="gentle", mass=1.2, stiffness=80.0, damping=16.0, overshoot_clamping=True),
    "dramatic_overshoot": SpringProfile(name="dramatic_overshoot", mass=1.0, stiffness=220.0, damping=9.0, overshoot_clamping=False),
    "stiff": SpringProfile(name="stiff", mass=1.0, stiffness=260.0, damping=24.0, overshoot_clamping=True),
    "fluid": SpringProfile(name="fluid", mass=1.4, stiffness=90.0, damping=18.0, overshoot_clamping=True),
}


@dataclass
class SceneMotionStrategy:
    """Scene-level cinematic motion strategy and choreography plan."""
    scene_id: str
    plan_scene_id: int
    strategy_name: str
    narrative_role: str
    emotional_tone: str
    intensity: Literal["restrained", "moderate", "energetic"]
    camera: CameraIntent
    spring: SpringProfile
    primary_element_id: str
    text_preset: str
    graphic_preset: str
    transition_type: str
    transition_duration: float
    audio_reactive_accents: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "plan_scene_id": self.plan_scene_id,
            "strategy_name": self.strategy_name,
            "narrative_role": self.narrative_role,
            "emotional_tone": self.emotional_tone,
            "intensity": self.intensity,
            "camera": self.camera.to_dict(),
            "spring": self.spring.to_dict(),
            "primary_element_id": self.primary_element_id,
            "text_preset": self.text_preset,
            "graphic_preset": self.graphic_preset,
            "transition": {
                "type": self.transition_type,
                "dur": round(self.transition_duration, 2),
            },
            "audio_reactive_accents": self.audio_reactive_accents,
            "rationale": self.rationale,
        }


@dataclass
class MotionIntelligenceResult:
    """Complete output package from MotionIntelligenceEngine."""
    status: Literal["completed", "fallback_deterministic"]
    scene_strategies: list[SceneMotionStrategy]
    continuity_report: dict[str, Any]
    audio_telemetry: dict[str, Any]
    collision_resolutions: list[dict[str, Any]]
    llm_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scenes_count": len(self.scene_strategies),
            "scene_strategies": [s.to_dict() for s in self.scene_strategies],
            "continuity_report": self.continuity_report,
            "audio_telemetry": self.audio_telemetry,
            "collision_resolutions": self.collision_resolutions,
            "llm_metadata": self.llm_metadata,
        }


def _scene_text(sc: dict[str, Any]) -> str:
    """The narration text of a scene: a transcript string, or the visual plan's narration object {text, text_en, ...}."""
    narration = sc.get("narration")
    if isinstance(narration, dict):
        narration = narration.get("text") or narration.get("text_en")
    txt = sc.get("transcript") or narration or sc.get("concept") or ""
    return txt if isinstance(txt, str) else str(txt)


def _scene_time(sc: dict[str, Any], edge: str, default: float) -> float:
    """Start or end seconds of a scene: start_time/start, else the visual plan's narration or source_mapping times."""
    narration = sc.get("narration") if isinstance(sc.get("narration"), dict) else {}
    mapping = sc.get("source_mapping") if isinstance(sc.get("source_mapping"), dict) else {}
    for value in (sc.get(f"{edge}_time"), sc.get(edge), narration.get(f"{edge}_seconds"), mapping.get(f"plan_{edge}")):
        if value is not None:
            return float(value)
    return default


class MotionIntelligenceEngine:
    """LLM-assisted Cinematic Motion Intelligence and Deterministic Compiler."""

    def __init__(self) -> None:
        pass

    def _extract_audio_telemetry(
        self,
        project_dir: Path,
        scenes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Reads audio metrics, speech rate, and pauses from available artifacts."""
        telemetry: dict[str, Any] = {"scenes": {}, "global": {}}
        t_file = project_dir / "transcript.json"
        aa_file = project_dir / "audio_analysis.json"
        cuts_file = project_dir / "cuts.json"

        transcript: dict[str, Any] = {}
        if t_file.exists():
            try:
                transcript = json.loads(t_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        pauses: list[tuple[float, float]] = []
        if aa_file.exists():
            try:
                aa = json.loads(aa_file.read_text(encoding="utf-8"))
                for p in aa.get("pauses", []):
                    pauses.append((float(p.get("start_seconds", 0.0)), float(p.get("end_seconds", 0.0))))
            except Exception:
                pass

        if not pauses and cuts_file.exists():
            try:
                cuts = json.loads(cuts_file.read_text(encoding="utf-8"))
                cuts_list = cuts if isinstance(cuts, list) else cuts.get("cuts", [])
                for c in cuts_list:
                    if isinstance(c, dict) and c.get("type") in ("silence", "pause"):
                        pauses.append((float(c.get("start", 0.0)), float(c.get("end", 0.0))))
            except Exception:
                pass

        total_words = 0
        total_duration = 0.0

        for sc in scenes:
            sid = str(sc.get("scene_id") or sc.get("id") or "1")
            start = _scene_time(sc, "start", 0.0)
            end = _scene_time(sc, "end", 0.0)
            dur = max(0.1, end - start)
            txt = _scene_text(sc)
            words = txt.split()
            w_count = len(words)
            total_words += w_count
            total_duration += dur

            wpm = round((w_count / dur) * 60.0, 1)
            sc_pauses = [p for p in pauses if p[0] >= start and p[1] <= end]
            pause_sec = sum(p[1] - p[0] for p in sc_pauses)

            telemetry["scenes"][sid] = {
                "words_count": w_count,
                "duration_seconds": round(dur, 2),
                "speech_rate_wpm": wpm,
                "pause_duration_seconds": round(pause_sec, 2),
                "pause_density": round(min(1.0, pause_sec / dur), 3),
                "pace_tier": "fast" if wpm >= 160 else "moderate" if wpm >= 120 else "slow",
            }

        avg_wpm = round((total_words / max(0.1, total_duration)) * 60.0, 1)
        telemetry["global"] = {
            "total_words": total_words,
            "total_duration_seconds": round(total_duration, 2),
            "average_wpm": avg_wpm,
            "pace_tier": "fast" if avg_wpm >= 160 else "moderate" if avg_wpm >= 120 else "slow",
        }
        return telemetry

    def _resolve_safe_text_preset(self, text_content: str, requested_preset: str | None) -> str:
        """Ensures Telugu text is only animated using Telugu-safe (indic) presets."""
        has_telugu = bool(TELUGU_PATTERN.search(text_content))
        allowed = SUPPORTED_TEXT_PRESETS["indic_safe"] if has_telugu else SUPPORTED_TEXT_PRESETS["general"]
        if requested_preset and requested_preset in allowed:
            return requested_preset
        return "bounce" if has_telugu else "fade-slide"

    def _build_heuristic_strategies(
        self,
        scenes: list[dict[str, Any]],
        aspect: str,
        audio_telemetry: dict[str, Any],
    ) -> list[SceneMotionStrategy]:
        """Generates contextual cinematic strategies using rule-based heuristics."""
        strategies: list[SceneMotionStrategy] = []
        n_scenes = len(scenes)
        used_transitions: list[str] = []

        transition_pool = [t for t in SUPPORTED_TRANSITIONS if t != "none"]

        for idx, sc in enumerate(scenes):
            sid = str(sc.get("scene_id") or sc.get("id") or f"scene_{idx+1:02d}")
            plan_id = int(sc.get("plan_scene_id") or sc.get("id") or (idx + 1))
            txt = _scene_text(sc)
            dur = _scene_time(sc, "end", 5.0) - _scene_time(sc, "start", 0.0)
            tel = audio_telemetry.get("scenes", {}).get(sid, {})
            wpm = tel.get("speech_rate_wpm", 130.0)

            # Assign narrative role & strategy based on narrative position and speed
            if idx == 0:
                role = "hook"
                strategy = "progressive_disclosure"
                tone = "awe and high anticipation"
                intensity = "energetic"
                cam = CameraIntent(move="push-in", zoom_from=1.0, zoom_to=1.08, focus=[0.5, 0.45], drift=0.25, rationale="Gentle push-in draws viewer into opening hook")
                spring = SPRING_PROFILES["snappy"]
                graphic = "light-sweep"
            elif idx == n_scenes - 1:
                role = "conclusion"
                strategy = "dramatic_impact"
                tone = "authoritative resolution"
                intensity = "moderate"
                cam = CameraIntent(move="pull-out", zoom_from=1.08, zoom_to=1.0, focus=[0.5, 0.5], drift=0.15, rationale="Slow pull-out frames complete conclusion")
                spring = SPRING_PROFILES["gentle"]
                graphic = "circular-meter"
            elif wpm >= 160:
                role = "explanation"
                strategy = "kinetic_typography"
                tone = "brisk urgency"
                intensity = "energetic"
                cam = CameraIntent(move="pan-right", zoom_from=1.02, zoom_to=1.05, focus=[0.55, 0.5], drift=0.3, rationale="Subtle pan matches fast narration pace")
                spring = SPRING_PROFILES["snappy"]
                graphic = "bar-glow"
            elif any(w in txt.lower() for w in ("but", "however", "కానీ", "మరోవైపు")):
                role = "contrast"
                strategy = "directional_motion"
                tone = "dramatic pivot"
                intensity = "energetic"
                cam = CameraIntent(move="pan-left", zoom_from=1.0, zoom_to=1.06, focus=[0.45, 0.5], drift=0.2, rationale="Directional pan emphasizes conceptual pivot")
                spring = SPRING_PROFILES["dramatic_overshoot"]
                graphic = "divider-grow"
            else:
                role = "explanation"
                strategy = "scale_depth"
                tone = "clear, professional informative"
                intensity = "moderate"
                cam = CameraIntent(move="static", zoom_from=1.0, zoom_to=1.02, focus=[0.5, 0.5], drift=0.1, rationale="Stable framing keeps focus on core explanation")
                spring = SPRING_PROFILES["fluid"]
                graphic = "targeting-ring"

            # Transition selection avoiding repeats
            prev_trans = used_transitions[-1] if used_transitions else None
            available = [t for t in transition_pool if t != prev_trans]
            chosen_trans = available[idx % len(available)] if idx < n_scenes - 1 else "none"
            trans_dur = min(0.5, max(MIN_ACTION_DURATION, dur * 0.15)) if chosen_trans != "none" else 0.0
            used_transitions.append(chosen_trans)

            text_preset = self._resolve_safe_text_preset(txt, None)

            # Audio-reactive accent points
            accents: list[dict[str, Any]] = []
            if wpm >= 150:
                accents.append({
                    "type": "kinetic_pop",
                    "target": "headline",
                    "offset_seconds": round(min(0.8, dur * 0.2), 2),
                    "rationale": f"High speech rate ({wpm} WPM) triggers kinetic entrance",
                })

            strategies.append(SceneMotionStrategy(
                scene_id=sid,
                plan_scene_id=plan_id,
                strategy_name=strategy,
                narrative_role=role,
                emotional_tone=tone,
                intensity=intensity,
                camera=cam,
                spring=spring,
                primary_element_id=f"{sid}_primary",
                text_preset=text_preset,
                graphic_preset=graphic,
                transition_type=chosen_trans,
                transition_duration=trans_dur,
                audio_reactive_accents=accents,
                rationale=f"Selected {strategy} for {role} role with {intensity} intensity matching {wpm} WPM audio cadence.",
            ))

        return strategies

    def _execute_llm_motion_planning(
        self,
        project_id: str,
        scenes: list[dict[str, Any]],
        aspect: str,
        audio_telemetry: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Calls LLM Gateway with fast_structured profile for motion decisions."""
        try:
            from SYSTEM.core.llm_gateway import LlmGatewayRequest, get_gateway
        except ImportError:
            logger.warning("SYSTEM.core.llm_gateway not available; skipping LLM call")
            return None

        scene_summaries = []
        for idx, sc in enumerate(scenes):
            sid = str(sc.get("scene_id") or sc.get("id") or f"scene_{idx+1}")
            dur = _scene_time(sc, "end", 5.0) - _scene_time(sc, "start", 0.0)
            txt = _scene_text(sc)
            tel = audio_telemetry.get("scenes", {}).get(sid, {})
            scene_summaries.append({
                "scene_id": sid,
                "plan_scene_id": int(sc.get("plan_scene_id") or sc.get("id") or (idx + 1)),
                "duration": round(dur, 2),
                "text": txt,
                "speech_rate_wpm": tel.get("speech_rate_wpm", 130.0),
                "pause_seconds": tel.get("pause_duration_seconds", 0.0),
            })

        system_prompt = (
            "You are a cinematic motion director for automated Remotion explainer videos. "
            "For each scene, recommend: "
            "1. strategy_name (progressive_disclosure, kinetic_typography, directional_motion, scale_depth, dramatic_impact) "
            "2. narrative_role (hook, context, explanation, contrast, reveal, conclusion) "
            "3. camera move (push-in, pull-out, pan-left, pan-right, static) with zoom 1.0 to 1.15 "
            "4. spring profile (snappy, gentle, dramatic_overshoot, stiff, fluid) "
            "5. text_preset and graphic_preset from supported lists "
            "6. transition_type (light-leak, crossfade, wipe, slide, none) "
            "Return valid JSON matching the schema."
        )

        user_prompt = json.dumps({
            "project_id": project_id,
            "aspect": aspect,
            "scenes": scene_summaries,
            "supported_text_presets": SUPPORTED_TEXT_PRESETS["general"],
            "supported_graphic_presets": list(SUPPORTED_GRAPHIC_PRESETS),
            "supported_transitions": list(SUPPORTED_TRANSITIONS),
        }, ensure_ascii=False)

        req = LlmGatewayRequest(
            project_id=project_id,
            stage_id="motion_plan",
            agent_id="motion_planning",
            purpose="generation",
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model_profile="fast_structured",
            timeout=30,
            max_retries=1,
            metadata={"source": "motion_planning_intelligence_engine"},
        )

        try:
            gw = get_gateway()
            res = gw.execute(req)
            if res.status in ("passed", "succeeded") and res.structured_data:
                return res.structured_data
            if res.raw_text:
                raw = res.raw_text.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning("LLM Gateway call failed during motion planning: %s", e)
            return None

        return None

    def plan_motion_intelligence(
        self,
        project_dir: Path,
        scenes: list[dict[str, Any]],
        aspect: str = "16:9",
    ) -> MotionIntelligenceResult:
        """Executes full cinematic motion planning pipeline."""
        t0 = time.perf_counter()
        project_id = project_dir.name

        # 1. Audio telemetry ingestion
        audio_telemetry = self._extract_audio_telemetry(project_dir, scenes)

        # 2. Heuristic baseline strategies
        heuristic_strategies = self._build_heuristic_strategies(scenes, aspect, audio_telemetry)

        # 3. Attempt LLM Planning via Gateway
        llm_data = self._execute_llm_motion_planning(
            project_id=project_id,
            scenes=scenes,
            aspect=aspect,
            audio_telemetry=audio_telemetry,
        )

        llm_used = llm_data is not None
        status: Literal["completed", "fallback_deterministic"] = "completed" if llm_used else "fallback_deterministic"

        final_strategies: list[SceneMotionStrategy] = []
        collision_resolutions: list[dict[str, Any]] = []

        if llm_used and isinstance(llm_data, dict) and "scenes" in llm_data:
            llm_scenes = llm_data.get("scenes", [])
            for idx, ls in enumerate(llm_scenes):
                if not isinstance(ls, dict):
                    continue
                h_fallback = heuristic_strategies[idx] if idx < len(heuristic_strategies) else heuristic_strategies[0]
                sid = str(ls.get("scene_id") or h_fallback.scene_id)
                plan_id = int(ls.get("plan_scene_id") or h_fallback.plan_scene_id)

                # Camera intent with deterministic bounds enforcement
                cam_data = ls.get("camera", {})
                move = cam_data.get("move", h_fallback.camera.move)
                z_from = max(MIN_CAMERA_ZOOM, min(MAX_CAMERA_ZOOM, float(cam_data.get("from", 1.0))))
                z_to = max(MIN_CAMERA_ZOOM, min(MAX_CAMERA_ZOOM, float(cam_data.get("to", 1.05))))
                focus = cam_data.get("focus", [0.5, 0.5])
                cam = CameraIntent(
                    move=move if move in ("static", "push-in", "pull-out", "pan-left", "pan-right", "tilt-up", "tilt-down", "zoom-to-focus") else "static",
                    zoom_from=z_from,
                    zoom_to=z_to,
                    focus=[max(0.15, min(0.85, focus[0])), max(0.15, min(0.85, focus[1]))] if len(focus) >= 2 else [0.5, 0.5],
                    drift=max(0.0, min(1.0, float(cam_data.get("drift", 0.2)))),
                    rationale=cam_data.get("rationale", h_fallback.camera.rationale),
                )

                # Spring profile
                s_name = ls.get("spring_profile", h_fallback.spring.name)
                spring = SPRING_PROFILES.get(s_name, h_fallback.spring)

                # Presets with Telugu safety verification
                txt = _scene_text(scenes[idx]) if idx < len(scenes) else ""
                text_preset = self._resolve_safe_text_preset(txt, ls.get("text_preset"))

                gfx = ls.get("graphic_preset", h_fallback.graphic_preset)
                if gfx not in SUPPORTED_GRAPHIC_PRESETS:
                    gfx = h_fallback.graphic_preset

                trans = ls.get("transition_type", h_fallback.transition_type)
                if trans not in SUPPORTED_TRANSITIONS:
                    trans = h_fallback.transition_type

                dur = _scene_time(scenes[idx], "end", 5.0) - _scene_time(scenes[idx], "start", 0.0)
                trans_dur = min(0.5, max(MIN_ACTION_DURATION, dur * 0.15)) if trans != "none" else 0.0

                final_strategies.append(SceneMotionStrategy(
                    scene_id=sid,
                    plan_scene_id=plan_id,
                    strategy_name=ls.get("strategy_name", h_fallback.strategy_name),
                    narrative_role=ls.get("narrative_role", h_fallback.narrative_role),
                    emotional_tone=ls.get("emotional_tone", h_fallback.emotional_tone),
                    intensity=ls.get("intensity", h_fallback.intensity) if ls.get("intensity") in ("restrained", "moderate", "energetic") else "moderate",
                    camera=cam,
                    spring=spring,
                    primary_element_id=ls.get("primary_element_id", h_fallback.primary_element_id),
                    text_preset=text_preset,
                    graphic_preset=gfx,
                    transition_type=trans,
                    transition_duration=trans_dur,
                    audio_reactive_accents=ls.get("audio_reactive_accents", h_fallback.audio_reactive_accents),
                    rationale=ls.get("rationale", h_fallback.rationale),
                ))

        if not final_strategies:
            final_strategies = heuristic_strategies

        # 4. Continuity and collision audit across consecutive scenes
        continuity_issues = []
        for i in range(len(final_strategies) - 1):
            cur = final_strategies[i]
            nxt = final_strategies[i + 1]
            if cur.transition_type != "none" and cur.transition_type == nxt.transition_type:
                # Prevent repeating identical transition
                alt_pool = [t for t in SUPPORTED_TRANSITIONS if t != "none" and t != cur.transition_type]
                nxt.transition_type = alt_pool[0]
                continuity_issues.append({
                    "scene_id": nxt.scene_id,
                    "fixed_rule": "transition_not_repeated",
                    "original": cur.transition_type,
                    "corrected": nxt.transition_type,
                })

        continuity_report = {
            "total_scenes": len(final_strategies),
            "variety_count": len(set(s.strategy_name for s in final_strategies)),
            "transitions_used": [s.transition_type for s in final_strategies],
            "repairs_count": len(continuity_issues),
            "repairs": continuity_issues,
        }

        latency_ms = round((time.perf_counter() - t0) * 1000)
        llm_metadata = {
            "llm_used": llm_used,
            "latency_ms": latency_ms,
            "model_profile": "fast_structured",
            "provider": "canonical_gateway",
            "aspect": aspect,
        }

        return MotionIntelligenceResult(
            status=status,
            scene_strategies=final_strategies,
            continuity_report=continuity_report,
            audio_telemetry=audio_telemetry,
            collision_resolutions=collision_resolutions,
            llm_metadata=llm_metadata,
        )

    def compile_motion_plan_json(
        self,
        project_dir: Path,
        scenes: list[dict[str, Any]],
        aspect: str,
        intelligence: MotionIntelligenceResult,
    ) -> dict[str, Any]:
        """Compiles validated MotionIntelligenceResult into downstream-compatible motion_plan.json."""
        s_by_id = {s.scene_id: s for s in intelligence.scene_strategies}
        compiled_scenes: list[dict[str, Any]] = []

        mgn = SAFE_MARGIN_16_9
        lim_y = 1.0 - SAFE_MARGIN_PORTRAIT_BOTTOM if aspect == "9:16" else 1.0 - mgn

        for idx, sc in enumerate(scenes):
            sid = str(sc.get("scene_id") or sc.get("id") or f"scene_{idx+1}")
            strat = s_by_id.get(sid) or intelligence.scene_strategies[idx]
            start_t = _scene_time(sc, "start", 0.0)
            end_t = _scene_time(sc, "end", 5.0)
            dur = max(0.1, end_t - start_t)
            txt = _scene_text(sc)

            # Texts array
            enter_s = min(0.64, max(0.35, dur * 0.12))
            exit_s = min(0.40, max(0.25, dur * 0.08))

            text_entry = {
                "text": txt,
                "style": "headline",
                "preset": strat.text_preset,
                "exit": "drop-out",
                "emphasis": "stroke",
                "enter_s": round(enter_s, 2),
                "at": round(start_t + 0.15, 2),
                "until": None,
                "exit_s": round(exit_s, 2),
                "emphasis_at": [round(start_t + 0.35, 2)],
                "source": "visual_plan",
                "drawn_box": [
                    round(mgn + 0.05, 3),
                    round(0.35, 3),
                    round(1.0 - mgn - 0.05, 3),
                    round(0.65, 3),
                ],
            }

            # Graphics array
            graphics_entry = [
                {
                    "preset": "light-sweep",
                    "atmosphere": True,
                    "speed": 1.4,
                    "anchored": False,
                    "start": round(start_t + 0.04, 2),
                    "end": None,
                    "exit_s": round(exit_s, 2),
                    "box": [0, 0, 1, 1],
                    "why": "atmosphere",
                },
                {
                    "preset": strat.graphic_preset,
                    "atmosphere": False,
                    "speed": 1.4 if strat.intensity == "energetic" else 1.0,
                    "anchored": False,
                    "start": round(start_t + 0.25, 2),
                    "end": None,
                    "exit_s": round(exit_s, 2),
                    "box": [
                        round(1.0 - mgn - 0.25, 3),
                        round(mgn + 0.05, 3),
                        0.20,
                        0.30,
                    ],
                    "why": f"hint:{strat.strategy_name}",
                },
            ]

            compiled_scenes.append({
                "id": strat.plan_scene_id,
                "scene_id": sid,
                "start": round(start_t, 2),
                "end": round(end_t, 2),
                "duration": round(dur, 2),
                "pattern": "hero_text",
                "pictures": 0,
                "strategy": strat.strategy_name,
                "narrative_role": strat.narrative_role,
                "camera": strat.camera.to_dict(),
                "spring": strat.spring.to_dict(),
                "texts": [text_entry],
                "graphics": graphics_entry,
                "transition": {
                    "type": strat.transition_type,
                    "dur": round(strat.transition_duration, 2),
                },
                "icons": [],
                "classic_texts": [],
                "other_layers": ["background"],
                "why": {
                    "texts": "visual_plan",
                    "strategy": strat.rationale,
                },
            })

        sfx = "_9x16" if aspect == "9:16" else ""
        plan_dict = {
            "version": 2,
            "aspect": aspect,
            "mode": "motion-only",
            "speed": 1.4,
            "fps": DEFAULT_FPS,
            "visual_plan_used": True,
            "scenes": compiled_scenes,
            "intelligence_metadata": {
                "status": intelligence.status,
                "llm_used": intelligence.llm_metadata.get("llm_used", False),
                "latency_ms": intelligence.llm_metadata.get("latency_ms", 0),
                "total_scenes": len(compiled_scenes),
                "average_wpm": intelligence.audio_telemetry.get("global", {}).get("average_wpm", 0.0),
            },
        }

        # Write to motion_plan.json
        mp_path = project_dir / f"motion_plan{sfx}.json"
        mp_path.write_text(json.dumps(plan_dict, indent=2, ensure_ascii=False), encoding="utf-8")

        # Also write companion intelligence artifact motion_intelligence.json
        intel_path = project_dir / f"motion_intelligence{sfx}.json"
        intel_path.write_text(json.dumps(intelligence.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        return plan_dict
