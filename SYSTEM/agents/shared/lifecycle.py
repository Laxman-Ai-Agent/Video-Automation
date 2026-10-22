"""Standardized Lifecycle and Execution State Machine for SYSTEM Agents."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from SYSTEM.history.execution_history import ExecutionRecord
from SYSTEM.history.history_service import history_service
from .contracts import AgentRequest, AgentResult


class AgentLifecycleManager:
    """Oversees agent execution lifecycle, history recording, and error boundaries."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._history = history_service

    def run_lifecycle(
        self,
        project_dir: Path,
        request: AgentRequest,
        validate_fn: Callable[[Path, AgentRequest], list[str]],
        execute_fn: Callable[[Path, AgentRequest], AgentResult],
        review_fn: Callable[[Path, AgentRequest, AgentResult], AgentResult] | None = None,
    ) -> AgentResult:
        """Executes full agent lifecycle: Validate -> Execute -> Review -> Record History."""
        t0 = time.perf_counter()
        exec_record = ExecutionRecord(
            agent_id=self.agent_id,
            task_id=request.request_id or "",
            project_id=request.project_id or project_dir.name,
            stage_id=request.stage_id,
            inputs_summary={"parameters": list(request.parameters.keys()) if request.parameters else []},
        )

        # 1. Validation phase
        validation_errors = validate_fn(project_dir, request)
        if validation_errors:
            err_msg = "; ".join(validation_errors)
            exec_record.mark_completed("blocked", error=err_msg)
            exec_record.duration_ms = (time.perf_counter() - t0) * 1000.0
            self._history.record_execution(exec_record)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id,
                project_id=project_dir.name,
                status="blocked",
                summary=f"Validation failed for agent {self.agent_id}",
                error=err_msg,
            )

        # 2. Execution phase
        try:
            result = execute_fn(project_dir, request)
        except Exception as e:
            err_msg = str(e)
            exec_record.mark_completed("failed", error=err_msg)
            exec_record.duration_ms = (time.perf_counter() - t0) * 1000.0
            self._history.record_execution(exec_record)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id,
                project_id=project_dir.name,
                status="failed",
                summary=f"Execution error in {self.agent_id}",
                error=err_msg,
            )

        # 3. Review phase (e.g. LLM review gate)
        if review_fn:
            try:
                result = review_fn(project_dir, request, result)
            except Exception as e:
                result.status = "blocked"
                result.error = f"Review hook failure: {e}"

        # 4. History recording phase
        exec_record.mark_completed(
            status="succeeded" if result.status == "succeeded" else "blocked" if result.status == "blocked" else "failed",
            outputs={"summary": result.summary, "artifacts": len(result.artifacts)},
            error=result.error,
        )
        exec_record.duration_ms = (time.perf_counter() - t0) * 1000.0
        self._history.record_execution(exec_record)

        return result
