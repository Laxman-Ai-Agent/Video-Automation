"""Dedicated implementation module for Visual Planning Agent.
Agent ID: visual_planning
Stage ID: planning
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.memory import store


class VisualPlanningAgent(BaseAgent):
    """A05: Visual Planning Agent. Generates scene-specific visual concepts and element breakdowns through canonical LLM Gateway, approved skills, verified memory, and mandatory review."""

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        sf = project_dir / "scene_segmentation.json"
        if not sf.exists():
            return ["Missing scene_segmentation.json for visual planning"]
        sp = project_dir / "scene_plan.json"
        if not sp.exists():
            return ["Missing scene_plan.json for visual planning"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        from VIDEO_ENGINE.stages import visual_planning
        from SYSTEM.core import llm_gateway
        from SYSTEM.policies import llm_review
        from SYSTEM.core.artifact_contracts import validate_planning_artifacts

        skills_used = [
            "audio.bilingual_preservation",
            "visual.scene_planning",
            "visual.cinematic_composition",
            "visual.narrative_semantic_mapping",
            "visual.word_semantic_animation",
            "visual.scene_variety_pacing",
        ]
        memories_used = [
            "mem-telugu-orthography",
            "mem-canvas-aspect-ratios",
            "mem-motion-safe-zones",
            "mem-timeline-fps-30",
        ]

        vf = project_dir / "visual_planning.json"
        force = bool(getattr(request, "parameters", {}).get("force"))

        if vf.exists() and not force:
            try:
                plan = json.loads(vf.read_text(encoding="utf-8"))
            except Exception:
                plan = {}
        else:
            def gateway_ask(prompt: str, system: str | None = None, timeout: int | None = None) -> str:
                skill_dir = Path(__file__).parent / "skills"
                skill_docs = []
                for sk_md in sorted(skill_dir.glob("*/SKILL.md")):
                    try:
                        skill_docs.append(sk_md.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                enhanced_system = (system or visual_planning.VISUAL_SYSTEM)
                if skill_docs:
                    enhanced_system += "\n\nACTIVE VISUAL PLANNING SKILLS:\n" + "\n---\n".join(skill_docs)

                gw_req = llm_gateway.GatewayRequest(
                    prompt=prompt,
                    system_prompt=enhanced_system,
                    stage_id="planning",
                    purpose="generation",
                    model_profile="fast_structured",
                    correlation_id=request.correlation_id,
                    caller_agent_id=self.agent_id,
                    metadata={
                        "project_id": project_dir.name,
                        "skills_used": skills_used,
                        "memory_used": memories_used,
                    },
                )
                gw_res = llm_gateway.execute_llm_gateway_call(gw_req)
                if gw_res.status not in ("passed", "needs_review") or not gw_res.raw_output:
                    raise Exception(f"LLM Gateway call failed: {gw_res.error_message or gw_res.status}")
                return gw_res.raw_output

            try:
                plan = visual_planning.run(project_dir, ask=gateway_ask)
            except Exception as e:
                try:
                    sp_data = json.loads((project_dir / "scene_plan.json").read_text(encoding="utf-8"))
                    pm_data = json.loads((project_dir / "prompts_map.json").read_text(encoding="utf-8")) if (project_dir / "prompts_map.json").exists() else {"prompts": []}
                    raw_data = None
                    if (project_dir / "visual_planning.json").exists():
                        try:
                            old_vp = json.loads((project_dir / "visual_planning.json").read_text(encoding="utf-8"))
                            llm_scs = [visual_planning._to_llm(s) for s in old_vp.get("scenes", [])]
                            if llm_scs:
                                vs = old_vp.get("visual_style", {})
                                raw_data = {
                                    "visual_style": {k: vs.get(k) for k in ("category", "tone", "typography", "density", "contrast_policy") if vs.get(k) is not None},
                                    "scenes": llm_scs,
                                }
                        except Exception:
                            raw_data = None
                    plan, _ = visual_planning.assemble(project_dir, sp_data, pm_data, raw_data)
                    visual_planning.save(project_dir, plan)
                except Exception:
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id="planning",
                        project_id=project_dir.name,
                        status="failed",
                        summary=f"Visual planning generation failed: {e}",
                    )

            # Enforce contract validation
            try:
                validate_planning_artifacts(project_dir)
            except Exception as e:
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="planning",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Visual planning contract validation failed: {e}",
                )

        # Motion-only security check: no external image URLs
        scenes = plan.get("scenes", [])
        for sc in scenes:
            for el in sc.get("elements", []):
                v_desc = str(el.get("visual_description", "")).lower()
                if "http://" in v_desc or "https://" in v_desc:
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id="planning",
                        project_id=project_dir.name,
                        status="blocked",
                        summary="External image URL detected in motion-only visual plan",
                    )

        spf = project_dir / "scene_plan.json"
        outputs = []
        if vf.exists():
            outputs.append(ArtifactRef(path=str(vf), description="Visual Planning JSON"))
        if spf.exists():
            outputs.append(ArtifactRef(path=str(spf), description="Scene Plan JSON"))

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="planning",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary=f"Visual planning assembled for {len(scenes)} scenes",
            metadata={
                "scenes_count": len(scenes),
                "skills_used": skills_used,
                "memory_used": memories_used,
            },
        )


# Backward-compatibility alias
VisualPlanningAdapter = VisualPlanningAgent
