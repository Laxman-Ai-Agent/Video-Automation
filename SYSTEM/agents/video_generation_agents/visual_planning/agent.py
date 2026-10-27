"""Dedicated implementation module for Visual Planning Agent.
Agent ID: visual_planning
Stage ID: planning
"""
from __future__ import annotations

from pathlib import Path

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentRequest, AgentResult, ArtifactRef
from SYSTEM.memory import store

SKILLS_USED = [
    "audio.bilingual_preservation",
    "visual.scene_planning",
    "visual.cinematic_composition",
    "visual.narrative_semantic_mapping",
    "visual.word_semantic_animation",
    "visual.scene_variety_pacing",
]
MEMORIES_USED = ["mem-telugu-orthography", "mem-canvas-aspect-ratios", "mem-motion-safe-zones", "mem-timeline-fps-30"]


class VisualPlanningAgent(BaseAgent):
    """A05: Visual Planning Agent. Plans what every scene shows (motion graphics, real pictures, real clips) for the media mix the user chose at upload, through the canonical LLM Gateway,
    approved skills, verified memory and the deterministic checks of VIDEO_ENGINE.stages.visual_planning. Nothing is derived when the planner fails: the result is `failed` with the cause."""

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        return [f"Missing {n} for visual planning" for n in ("scene_segmentation.json", "scene_plan.json") if not (project_dir / n).exists()]

    def _gateway_ask(self, project_dir: Path, request: AgentRequest):
        from SYSTEM.core import llm_gateway
        from VIDEO_ENGINE.stages import visual_planning

        def ask(prompt: str, system: str | None = None, timeout: int | None = None) -> str:
            docs = []
            for sk_md in sorted((Path(__file__).parent / "skills").glob("*/SKILL.md")):
                try:
                    docs.append(sk_md.read_text(encoding="utf-8"))
                except OSError:
                    pass
            enhanced = (system or visual_planning.VISUAL_SYSTEM) + ("\n\nACTIVE VISUAL PLANNING SKILLS:\n" + "\n---\n".join(docs) if docs else "")
            res = llm_gateway.execute_llm_gateway_call(llm_gateway.GatewayRequest(
                prompt=prompt, system_prompt=enhanced, stage_id="planning", purpose="generation", model_profile="fast_structured", correlation_id=request.correlation_id,
                caller_agent_id=self.agent_id, timeout=timeout or 900,                        # the planner asks for 900 s: the gateway's default of 60 s cut a planner answer (minutes long) off three times
                metadata={"project_id": project_dir.name, "skills_used": SKILLS_USED, "memory_used": MEMORIES_USED}))
            if res.status not in ("passed", "needs_review") or not res.raw_output:
                raise visual_planning.GenError(f"LLM Gateway call failed: {res.error_message or res.status}")
            return res.raw_output
        return ask

    def _result(self, project_dir: Path, status: str, summary: str, **kw) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, stage_id="planning", project_id=project_dir.name, status=status, summary=summary, **kw)

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        from SYSTEM.core.artifact_contracts import validate_planning_artifacts
        from VIDEO_ENGINE.stages import visual_planning

        vf = project_dir / visual_planning.FILE
        force = bool(getattr(request, "parameters", {}).get("force"))
        plan = visual_planning.load(project_dir)
        if plan is None or plan.get("stale") or force:
            try:
                plan = visual_planning.run(project_dir, ask=self._gateway_ask(project_dir, request))
            except Exception as e:                                      # GenError names the cause; nothing is derived in its place
                return self._result(project_dir, "failed", f"Visual planning generation failed: {e}")
        try:
            validate_planning_artifacts(project_dir)
        except Exception as e:
            return self._result(project_dir, "failed", f"Visual planning contract validation failed: {e}")
        scenes = plan.get("scenes", [])
        mix = plan.get("media_mix", {})
        outputs = [ArtifactRef(path=str(p), description=d) for p, d in ((vf, "Visual Planning JSON"), (project_dir / "scene_plan.json", "Scene Plan JSON")) if p.exists()]
        return self._result(project_dir, "succeeded", f"Visual planning assembled for {len(scenes)} scenes", output_refs=outputs,
                            metadata={"scenes_count": len(scenes), "media_mix_actual": mix.get("actual"), "totals": plan.get("totals"),
                                      "skills_used": SKILLS_USED, "memory_used": MEMORIES_USED, "project_media": store.media(project_dir)})


# Backward-compatibility alias
VisualPlanningAdapter = VisualPlanningAgent
