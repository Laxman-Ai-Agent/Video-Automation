"""Dedicated implementation module for the Asset Collection Agent.
Agent ID: asset_collection
Stage ID: assets
Version: 1.0.0

One agent for the whole stage (requirements planning, provider search, capture/clip preparation, validation, manifest): the work is one sequential pipeline over shared state
(candidate cache, manifest), so splitting it into several agents would only add hand-offs. The logic lives in VIDEO_ENGINE/stages/asset_collection.py; this agent is the stage adapter.
"""
from __future__ import annotations

import logging
from pathlib import Path

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef

logger = logging.getLogger("asset_collection")


class AssetCollectionAgent(BaseAgent):
    """Finds, validates and records the real photographs and video clips the scenes need (optional evidence on top of the generated motion graphics)."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="asset_collection",
                name="Asset Collection Agent",
                version="1.0.0",
                status=AgentStatus.IMPLEMENTED,
                purpose="Plans which scenes need real photos or video clips, searches licensed sources, validates and records provenance, rights and scene assignment of every collected asset.",
                capabilities=["asset-requirement-planning", "licensed-source-search", "clip-preparation", "rights-and-provenance-tracking", "duplicate-detection"],
                stage_id="assets",
                allowed_tools=["stock_providers", "ffmpeg", "llm_gateway", "asset_manifest"],
                owner="agent-system",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        if not (project_dir / "scene_plan.json").exists():
            return ["Missing scene_plan.json: Visual Planning must run before Asset Collection"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        from VIDEO_ENGINE.stages import asset_collection

        params = getattr(request, "parameters", {}) or {}
        aspect = params.get("aspect", "16:9")
        try:
            manifest = asset_collection.run(project_dir, aspect, force=bool(params.get("force")) and not params.get("resume", False))
        except asset_collection.AssetError as e:
            logger.error("Asset collection failed: %s", e)
            return AgentResult(agent_id=self.agent_id, stage_id="assets", project_id=project_dir.name, status="failed", summary=f"Asset collection failed: {e}", error=str(e))
        findings = asset_collection.check_assets(project_dir, manifest)
        errors = [f for f in findings if f["severity"] == "error"]
        if errors:                                                      # a collected asset that fails its own checks must never be passed downstream
            msg = "; ".join(f["message"] for f in errors[:3])
            return AgentResult(agent_id=self.agent_id, stage_id="assets", project_id=project_dir.name, status="failed", summary=f"Collected assets failed their checks: {msg}", error=msg)
        outputs = [ArtifactRef(path=str(p), description=d) for p, d in ((asset_collection.requirements_path(project_dir), "Asset requirements JSON"),
                                                                      (asset_collection.manifest_path(project_dir), "Assets manifest JSON")) if p.exists()]
        review = [f for f in findings if f["severity"] == "review"]
        return AgentResult(
            agent_id=self.agent_id, stage_id="assets", project_id=project_dir.name, status="succeeded", output_refs=outputs,
            summary=(f"{len(manifest['assets'])} real asset(s) collected for {manifest['requirement_count']} requirement(s)" if manifest["requirement_count"] else "no scene needs real media"),
            metadata={"requirements": manifest["requirement_count"], "assets": len(manifest["assets"]), "fallbacks": len(manifest["fallbacks"]), "needs_human_review": len(review), "aspect": aspect})


# Backward-compatibility alias (every stage agent exposes an Adapter name)
AssetCollectionAdapter = AssetCollectionAgent
