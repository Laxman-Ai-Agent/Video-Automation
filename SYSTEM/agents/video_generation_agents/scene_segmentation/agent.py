"""Dedicated implementation module for Scene Segmentation Agent.
Agent ID: scene_segmentation
Stage ID: segmentation
Version: 2.0.0
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.agents.video_generation_agents.scene_segmentation.semantic_analyzer import SemanticAnalyzer
from SYSTEM.memory import store

logger = logging.getLogger("scene_segmentation.agent")


class SceneSegmentationAgent(BaseAgent):
    """A04: Scene Segmentation Agent (v2.0.0 Semantic Intelligence Upgrade).
    Combines LLM narrative reasoning, cross-lingual topic modeling, Telugu-English vocabulary
    standardization, and adaptive pacing telemetry; the deterministic core keeps its timing and coverage invariants.
    """

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="scene_segmentation",
                name="Scene Segmentation Agent",
                version="2.0.0",
                status=AgentStatus.IMPLEMENTED,
                stage_id="segmentation",
                is_frozen=False,
                capabilities=[
                    "semantic-chunking",
                    "boundary-snapping",
                    "duration-enforcement",
                    "topic-modeling",
                    "adaptive-pacing",
                    "vocabulary-standardization",
                ],
            )
        super().__init__(metadata)
        self.semantic_analyzer = SemanticAnalyzer()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        tf = project_dir / "transcript.json"
        if not tf.exists():
            return ["Missing transcript.json for scene segmentation"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        sf = project_dir / "scene_segmentation.json"
        if not sf.exists():
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="segmentation",
                project_id=project_dir.name,
                status="blocked",
                summary="Missing scene_segmentation.json. Silent ASR or re-segmentation is prohibited.",
            )

        from SYSTEM.core.artifact_contracts import _file_sha256, validate_segmentation_artifacts
        try:
            validate_segmentation_artifacts(project_dir)
            data = json.loads(sf.read_text(encoding="utf-8"))
            scenes = data.get("scenes", [])
            for sc in scenes:
                start = float(sc.get("start", sc.get("start_time", 0.0)))
                end = float(sc.get("end", sc.get("end_time", 0.0)))
                if end <= start:
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id="segmentation",
                        project_id=project_dir.name,
                        status="failed",
                        summary=f"Scene {sc.get('scene_id') or sc.get('id')} has non-positive duration: {start} -> {end}",
                    )
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="segmentation",
                project_id=project_dir.name,
                status="failed",
                summary=f"Scene segmentation validation failed: {e}",
            )

        # Execute semantic intelligence review layer
        tf = project_dir / "transcript.json"
        cf = project_dir / "cuts.json"
        transcript_data: dict[str, Any] = {}
        cuts_data: Any = None

        if tf.exists():
            try:
                transcript_data = json.loads(tf.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Could not read transcript.json for semantic analysis: %s", e)

        if cf.exists():
            try:
                cuts_data = json.loads(cf.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Could not read cuts.json for semantic analysis: %s", e)

        semantic_res = self.semantic_analyzer.analyze(
            project_dir=project_dir,
            canonical_segmentation=data,
            transcript_data=transcript_data,
            cuts_data=cuts_data,
        )

        # Non-destructively write enriched scenes to scene_segmentation.json
        if semantic_res.scenes:
            data["scenes"] = semantic_res.scenes
            data["semantic_intelligence"] = {
                "version": "2.0.0",
                "topics_count": len(semantic_res.topics),
                "vocabulary_count": len(semantic_res.vocabulary),
                "average_wpm": semantic_res.global_pacing.get("average_wpm", 0.0),
                "global_pacing_tier": semantic_res.global_pacing.get("global_pacing_tier", "balanced"),
                "status": semantic_res.status,
            }
            try:
                sf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.error("Failed to write enriched scene_segmentation.json: %s", e)

        # Record self-learning experience in memory
        try:
            if hasattr(self, "memory") and self.memory is not None:
                exp_payload = {
                    "task_type": "segmentation_semantic_review",
                    "task_id": request.correlation_id or f"req-seg-{int(time.time())}",
                    "project_id": project_dir.name,
                    "outcome": "succeeded",
                    "metrics": {
                        "scenes_count": len(scenes),
                        "topics_count": len(semantic_res.topics),
                        "average_wpm": semantic_res.global_pacing.get("average_wpm", 0.0),
                        "latency_ms": semantic_res.llm_metadata.get("latency_ms", 0),
                    },
                    "reflection": {
                        "status": "success",
                        "summary": f"Scene segmentation semantic review enriched {len(scenes)} scenes across {len(semantic_res.topics)} narrative topics.",
                        "takeaway": f"Pacing classified as {semantic_res.global_pacing.get('global_pacing_tier', 'balanced')}; {len(semantic_res.vocabulary)} vocabulary terms normalized.",
                    },
                    "confidence": 0.95 if semantic_res.status == "completed" else 0.85,
                }
                self.memory.add_experience(exp_payload)
        except Exception as e:
            logger.debug("Memory reflection recording skipped: %s", e)

        outputs = [
            ArtifactRef(path=str(sf), description="Scene Segmentation JSON"),
        ]

        annotations_path = project_dir / "scene_semantic_annotations.json"
        metadata = {
            "scenes_count": len(scenes),
            "segmentation_sha256": _file_sha256(sf),
            "semantic_status": semantic_res.status,
            "topics_count": len(semantic_res.topics),
            "vocabulary_terms_count": len(semantic_res.vocabulary),
            "average_wpm": semantic_res.global_pacing.get("average_wpm", 0.0),
            "global_pacing_tier": semantic_res.global_pacing.get("global_pacing_tier", "balanced"),
            "all_invariants_passed": semantic_res.invariant_status.get("all_invariants_passed", True),
            "semantic_annotations_path": str(annotations_path) if annotations_path.exists() else None,
            "llm_used": semantic_res.llm_metadata.get("llm_used", False),
        }

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="segmentation",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary=f"Scene segmentation validated with {len(scenes)} scenes (no ASR re-run)",
            metadata=metadata,
        )


# Backward-compatibility alias
SceneSegmentationAdapter = SceneSegmentationAgent
