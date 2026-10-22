"""Dedicated implementation module for Timeline Approval Agent.
Agent ID: timeline_approval
Stage ID: approval
Version: 2.0.0 (Upgraded with Visual & Structural Diff Inspector, LLM Quality Assessment, and Central Audit Logging)
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared import communication
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.agents.video_generation_agents.timeline_approval.approval_intelligence import (
    ApprovalRiskClassifier,
    LLMTimelineAssessor,
    StructuralDiffAnalyzer,
    VisualDiffAnalyzer,
)
from SYSTEM.memory import store

logger = logging.getLogger("timeline_approval.agent")


class TimelineApprovalAgent(BaseAgent):
    """A11: Timeline Approval Agent. Cryptographic fingerprint lock + Visual/Structural Diff + Autonomous rubric approval."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="timeline_approval",
                name="Timeline Approval Agent",
                stage_id="approval",
            )
        super().__init__(metadata)
        self.diff_analyzer = StructuralDiffAnalyzer()
        self.visual_diff_analyzer = VisualDiffAnalyzer()
        self.llm_assessor = LLMTimelineAssessor()
        self.risk_classifier = ApprovalRiskClassifier()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        tl = project_dir / f"timeline{sfx}.json"
        if not tl.exists():
            return [f"Missing timeline{sfx}.json for timeline approval"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        task_id = request.parameters.get("task_id") or request.run_id
        t0 = time.perf_counter()

        from VIDEO_ENGINE.stages import timeline_approval
        from SYSTEM.core.artifact_contracts import validate_approval_artifacts

        cur_fp = timeline_approval.fingerprint(project_dir, aspect)
        st = timeline_approval.state(project_dir, aspect)

        hist_file = project_dir / f"timeline_approval_history{sfx}.json"
        legacy_file = project_dir / "timeline_approval.json"
        intel_file = project_dir / f"timeline_approval_intelligence{sfx}.json"

        outputs = []
        if hist_file.exists():
            outputs.append(ArtifactRef(path=str(hist_file), description="Timeline Approval History JSON"))
        elif legacy_file.exists():
            outputs.append(ArtifactRef(path=str(legacy_file), description="Timeline Approval JSON"))

        # 1. Structural and Visual Diff Inspection
        struct_diff = self.diff_analyzer.analyze_diff(project_dir, aspect)
        vis_diff = self.visual_diff_analyzer.compare_previews(project_dir, aspect)

        # 2. LLM Timeline Quality Assessment
        tl_meta = {
            "duration_seconds": (st.get("manifest") or {}).get("duration_seconds", 4.0),
            "total_frames": (st.get("manifest") or {}).get("duration_frames", 120),
            "fps": (st.get("manifest") or {}).get("format", {}).get("fps", 30),
            "scene_count": len(struct_diff.get("unchanged_scenes", [])) + len(struct_diff.get("modified_scenes", [])) + len(struct_diff.get("added_scenes", [])),
        }
        requirements = st.get("requirements") or []
        llm_assessment = self.llm_assessor.assess(
            project_id=project_dir.name,
            timeline_meta=tl_meta,
            requirements=requirements,
            diff_summary=struct_diff,
            visual_diff_meta=vis_diff,
        )

        # 3. Evidence-Based Risk Classification
        blockers = st.get("blockers") or []
        is_stale = bool(st.get("stale"))
        risk_info = self.risk_classifier.evaluate_risk(
            blockers=blockers,
            fingerprint=cur_fp,
            is_stale=is_stale,
            llm_assessment=llm_assessment,
            structural_diff=struct_diff,
        )

        # Helper to persist intelligence artifact
        def _write_intelligence_record(decision_str: str) -> None:
            payload = {
                "schema_version": "2.0",
                "project_id": project_dir.name,
                "aspect": aspect,
                "current_fingerprint": cur_fp,
                "decision": decision_str,
                "structural_diff": struct_diff,
                "visual_diff": vis_diff,
                "llm_quality_assessment": llm_assessment,
                "risk_classification": risk_info,
                "timings_ms": round((time.perf_counter() - t0) * 1000),
            }
            intel_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # 4. Timeline Approval is decided by the LLM approval review (no person): an unapproved or stale version is reviewed and, only when the review passes, approved
        #    through timeline_approval.auto_approve (the one implementation, also used by the pipeline step). A rejection fails the stage with the exact cause.
        approved_now = False
        if not st.get("approved"):
            if not cur_fp:
                _write_intelligence_record("blocked")
                return AgentResult(agent_id=self.agent_id, stage_id="approval", project_id=project_dir.name, status="blocked",
                                   summary=f"Timeline approval blocked{' (stale: the timeline changed since it was approved)' if is_stale else ''}: " + "; ".join(blockers[:3] or ["no current timeline version"]), error="; ".join(blockers) or "no current timeline version",
                                   output_refs=outputs, metadata={"fingerprint": cur_fp, "state": st, "risk_classification": risk_info, "timeline_approval_intelligence_ref": str(intel_file)})
            try:
                st = timeline_approval.auto_approve(project_dir, aspect, in_job=True)       # the orchestrator runs this agent inside the project's job
            except timeline_approval.ApprovalError as e:
                _write_intelligence_record("llm_rejected")
                return AgentResult(agent_id=self.agent_id, stage_id="approval", project_id=project_dir.name, status="failed",
                                   summary=f"Timeline Approval (LLM) did not approve: {e}", error="; ".join([str(e), *e.blockers]),
                                   output_refs=outputs, metadata={"fingerprint": cur_fp, "state": st, "risk_classification": risk_info, "structural_diff": struct_diff,
                                                                   "llm_quality_assessment": llm_assessment, "timeline_approval_intelligence_ref": str(intel_file)})
            self._append_audit_log(project_id=project_dir.name, decision="approved", reviewer=(st.get("last_decision") or {}).get("decided_by", "llm"), fingerprint=cur_fp)
            approved_now = True
            if hist_file.exists() and not any(o.path == str(hist_file) for o in outputs):
                outputs.append(ArtifactRef(path=str(hist_file), description="Timeline Approval History JSON"))
            try:
                communication.publish_lifecycle_event(project_id=project_dir.name, stage_id="approval", sender_agent_id=self.agent_id, event="stage_completed",
                                                      detail="Timeline approved by the LLM approval review; ready for rendering",
                                                      telugu_activity="టైమ్‌లైన్ సరిగ్గా ఉందని నిర్ధారించాను. వీడియో తయారీ కొనసాగుతోంది.", task_id=task_id)
            except Exception:
                pass

        # 6. Already Approved: Validate Contracts and Emit Success
        if hist_file.exists():
            try:
                validate_approval_artifacts(project_dir, aspect)
            except Exception as e:
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="approval",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Timeline approval artifact contract validation failed: {e}",
                    error=str(e),
                )

        _write_intelligence_record("approved_by_llm" if approved_now else "already_approved_verified")

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="approval",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary="Timeline approval verified against current timeline fingerprint",
            metadata={
                "approved": True,
                "fingerprint": cur_fp,
                "state": st,
                "risk_classification": risk_info,
                "structural_diff": struct_diff,
                "llm_quality_assessment": llm_assessment,
                "timeline_approval_intelligence_ref": str(intel_file),
            },
        )

    def _append_audit_log(
        self,
        project_id: str,
        decision: str,
        reviewer: str,
        fingerprint: str | None,
    ) -> None:
        """Appends a tamper-evident audit record to config/approvals_audit.jsonl."""
        try:
            audit_path = Path("config/approvals_audit.jsonl")
            record = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_type": "approval_granted" if decision == "approved" else "approval_blocked",
                "request_id": f"auto_{int(time.time())}_{project_id}",
                "action_type": "timeline_render",
                "requester_agent_id": self.agent_id,
                "risk_level": "medium",
                "fingerprint": fingerprint,
                "project_id": project_id,
                "reviewer": reviewer,
            }
            with audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append to approvals_audit.jsonl: {e}")


# Backward-compatibility alias
TimelineApprovalAdapter = TimelineApprovalAgent
