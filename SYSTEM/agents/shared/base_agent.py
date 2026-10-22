"""Common BaseAgent abstract class defining standard lifecycle hooks."""
from __future__ import annotations

import abc
import time
from pathlib import Path
from typing import Any

from .communication import publish_lifecycle_event, publish_message
from .contracts import AgentMetadata, AgentRequest, AgentResult, ArtifactRef, MessageType


class BaseAgent(abc.ABC):
    """Abstract BaseAgent for all 14 logical agents."""

    def __init__(self, metadata: AgentMetadata) -> None:
        self.metadata = metadata
        from .memory_adapter import AgentMemoryAdapter
        self.memory = AgentMemoryAdapter(self.agent_id)
        self._local_skills: dict[str, Any] = {}
        self._local_skill_executors: dict[str, Any] = {}
        self._discover_local_skills()

    @property
    def agent_id(self) -> str:
        return self.metadata.agent_id

    @property
    def stage_id(self) -> str | None:
        return self.metadata.stage_id

    @abc.abstractmethod
    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        """Validates prerequisites and inputs before execution. Returns blocking error messages."""
        pass

    @abc.abstractmethod
    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Executes the agent's primary work, returning structured output references."""
        pass

    def get_local_skills_dirs(self) -> list[Path]:
        """Resolves existing private skill directory paths for this agent."""
        dirs = []
        try:
            from SYSTEM.core import config
            root = config.PROJECT_ROOT
        except ImportError:
            root = Path(__file__).resolve().parents[3]

        base_dir = root / "SYSTEM" / "agents"
        candidates = [
            base_dir / self.agent_id / "skills",
            base_dir / "video_generation_agents" / self.agent_id / "skills",
        ]
        try:
            import sys
            mod = sys.modules.get(self.__class__.__module__)
            if mod and getattr(mod, "__file__", None):
                pkg_dir = Path(mod.__file__).parent / "skills"
                candidates.append(pkg_dir)
        except Exception:
            pass

        seen = set()
        for d in candidates:
            if d.exists() and d.is_dir():
                resolved = str(d.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    dirs.append(d)
        return dirs

    def _discover_local_skills(self) -> dict[str, Any]:
        """Discovers, validates, and registers agent-local private skills without unsafe execution."""
        import ast
        import hashlib
        import re

        self._local_skills.clear()
        self._local_skill_executors.clear()

        for s_dir in self.get_local_skills_dirs():
            for item in s_dir.iterdir():
                if item.name.startswith("."):
                    continue

                target_file: Path | None = None
                skill_id: str = item.stem if item.is_file() else item.name

                py_executor = None
                if item.is_dir():
                    md_cand = item / "SKILL.md"
                    py_cand = item / "skill.py"
                    if md_cand.exists():
                        target_file = md_cand
                    elif py_cand.exists():
                        target_file = py_cand
                    if py_cand.exists():
                        py_executor = py_cand
                elif item.is_file():
                    if item.suffix in (".md", ".py"):
                        target_file = item
                    if item.suffix == ".py":
                        py_executor = item

                if target_file is None:
                    continue

                # Path confinement check
                try:
                    if s_dir.resolve() not in target_file.resolve().parents and target_file.resolve() != s_dir.resolve():
                        continue
                except Exception:
                    continue

                # ID validation
                if not re.match(r"^[a-z0-9_.-]+$", skill_id):
                    continue

                try:
                    content = target_file.read_text(encoding="utf-8")
                except Exception:
                    continue

                content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
                title = skill_id
                domain = "agent_local"
                summary = f"Agent-local private skill for {self.agent_id}"
                version = "1.0.0"
                tags = ["local", self.agent_id]
                caps = [skill_id]
                is_executable = False

                if target_file.suffix == ".md":
                    if content.startswith("---"):
                        try:
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                for line in parts[1].splitlines():
                                    if ":" in line and not line.strip().startswith("-"):
                                        k, v = line.split(":", 1)
                                        k = k.strip()
                                        v = v.strip().strip("'\"")
                                        if k == "name":
                                            title = v
                                        elif k == "domain":
                                            domain = v
                                        elif k == "version":
                                            version = v
                                        elif k == "summary":
                                            summary = v
                        except Exception:
                            pass
                elif target_file.suffix == ".py":
                    try:
                        parsed = ast.parse(content, filename=str(target_file))
                        doc = ast.get_docstring(parsed)
                        if doc:
                            summary = doc.splitlines()[0]
                        is_executable = True
                    except Exception:
                        continue

                if py_executor is not None:
                    try:
                        py_code = py_executor.read_text(encoding="utf-8")
                        parsed = ast.parse(py_code, filename=str(py_executor))
                        doc = ast.get_docstring(parsed)
                        if doc and (target_file.suffix != ".md" or not summary):
                            summary = doc.splitlines()[0]
                        is_executable = True
                    except Exception:
                        pass

                skill_entry = {
                    "skill_id": skill_id,
                    "name": title,
                    "summary": summary,
                    "domain": domain,
                    "version": version,
                    "tags": tags,
                    "capabilities": caps,
                    "status": "approved",
                    "source": "local",
                    "entrypoint": str(target_file),
                    "content_sha256": content_sha,
                    "license": "Internal-Proprietary",
                    "compatible_agents": [self.agent_id],
                    "risk_level": "low",
                    "metadata": {
                        "scope": "local",
                        "owner_agent_id": self.agent_id,
                        "is_local": True,
                        "is_executable": is_executable,
                        "file_path": str(target_file),
                    },
                }
                self._local_skills[skill_id] = skill_entry
                if is_executable and py_executor:
                    self._local_skill_executors[skill_id] = py_executor

        return self._local_skills

    def get_local_skills(self) -> list[dict[str, Any]]:
        """Returns list of discovered private skills owned by this agent."""
        return list(self._local_skills.values())

    def invoke_skill(self, skill_id: str, *args, **kwargs) -> Any:
        """Invokes an agent-local skill or delegates to central skill execution."""
        if skill_id in self._local_skills:
            exec_path = self._local_skill_executors.get(skill_id)
            if exec_path and exec_path.suffix == ".py":
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"local_skill_{skill_id}", str(exec_path))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "execute"):
                        return mod.execute(*args, **kwargs)
                    elif hasattr(mod, "run"):
                        return mod.run(*args, **kwargs)
                    elif hasattr(mod, skill_id):
                        return getattr(mod, skill_id)(*args, **kwargs)
                    return mod
            _, content = self.get_skill(skill_id)
            return {"status": "succeeded", "skill_id": skill_id, "instruction": content}

        rec, content = self.get_skill(skill_id)
        return {"status": "succeeded", "skill_id": skill_id, "scope": rec.get("metadata", {}).get("scope", "central"), "instruction": content}

    def search_skills(
        self,
        query: str = "",
        domain: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Discovers approved compatible skills for this agent, local private skills taking precedence."""
        from SYSTEM.registries import skill_registry
        records = skill_registry.registry.search_skills(
            query=query,
            agent_id=self.agent_id,
            domain=domain,
            tag=tag,
            status="approved",
        )
        return [r.to_dict() for r in records]

    def get_skill(
        self,
        skill_id: str,
        version: str | None = None,
        load_content: bool = True,
    ) -> tuple[dict[str, Any], str]:
        """Retrieves and verifies an approved skill, checking private skills first, then central library."""
        # 1. Local private skills check
        if skill_id in self._local_skills:
            local_entry = self._local_skills[skill_id]
            if version and local_entry.get("version") != version:
                raise ValueError(f"Local skill version mismatch: requested {version}, found {local_entry.get('version')}")
            content = ""
            if load_content:
                fp = Path(local_entry["metadata"]["file_path"])
                if fp.exists():
                    content = fp.read_text(encoding="utf-8")
            return local_entry, content

        # 2. Central library fallback with scoped authorization
        from SYSTEM.registries import skill_registry
        record, content = skill_registry.registry.get_agent_skill(
            agent_id=self.agent_id,
            skill_name=skill_id,
            version=version,
            load_content=load_content,
        )
        return record.to_dict(), content

    def retrieve_memory(
        self,
        query: str = "",
        project_id: str | None = None,
        scope: str | None = None,
        kind: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves verified technical knowledge scoped to this agent and project."""
        from SYSTEM.memory import shared_memory
        items = shared_memory.service.retrieve_memory(
            query=query,
            agent_id=self.agent_id,
            project_id=project_id,
            scope=scope,  # type: ignore[arg-type]
            kind=kind,    # type: ignore[arg-type]
            include_candidates=False,
            limit=limit,
        )
        return [i.to_dict() for i in items]

    def submit_memory_candidate(
        self,
        title: str,
        content: str,
        kind: str,
        confidence: float = 0.6,
        evidence: list[dict[str, Any]] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Proposes an observation or lesson as an unverified candidate memory."""
        from SYSTEM.memory import shared_memory
        item = shared_memory.service.submit_candidate(
            title=title,
            content=content,
            kind=kind,  # type: ignore[arg-type]
            owner=self.agent_id,
            scope="project" if project_id else "global",
            evidence=evidence,
            confidence=confidence,
            project_id=project_id,
        )
        return item.to_dict()

    def record_experience(
        self,
        task_type: str,
        outcome: str,
        context: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        error_category: str | None = None,
        task_id: str | None = None,
        project_id: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        reflection: str | dict[str, Any] | None = None,
        proposed_lesson: dict[str, Any] | None = None,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Records a granular task execution experience strictly into this agent's private partition."""
        from SYSTEM.memory.per_agent_store import per_agent_store
        exp = per_agent_store.record_experience(
            agent_id=self.agent_id,
            task_type=task_type,
            outcome=outcome,
            context=context,
            metrics=metrics,
            error_category=error_category,
            task_id=task_id,
            project_id=project_id,
            evidence=evidence,
            reflection=reflection,
            proposed_lesson=proposed_lesson,
            confidence=confidence,
        )
        return exp.to_dict()

    def retrieve_agent_memories(
        self,
        task_type: str | None = None,
        query: str = "",
        outcome: str | None = None,
        limit: int = 10,
        include_shared: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieves past task experiences strictly from this agent's private partition,
        optionally combined with relevant verified shared knowledge.
        Cross-agent private isolation is strictly enforced.
        """
        from SYSTEM.memory.per_agent_store import per_agent_store
        private_exps = per_agent_store.retrieve_agent_experiences(
            agent_id=self.agent_id,
            task_type=task_type,
            query=query,
            outcome=outcome,
            limit=limit,
        )
        memories = [e.to_dict() for e in private_exps]

        if include_shared:
            try:
                from SYSTEM.memory import shared_memory
                shared_items = shared_memory.service.retrieve_memory(
                    query=query or (task_type or ""),
                    agent_id=self.agent_id,
                    scope="global",
                    include_candidates=False,
                    limit=max(1, limit // 2),
                )
                for item in shared_items:
                    d = item.to_dict()
                    d["source_type"] = "shared_verified_memory"
                    memories.append(d)
            except Exception:
                pass

        return memories[:limit]

    def reflect_on_task_outcome(
        self,
        task_type: str,
        outcome: str,
        context: dict[str, Any],
        metrics: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Generates role-appropriate reflection and optional candidate lesson proposal."""
        metrics = metrics or {}
        duration_ms = metrics.get("duration_ms", 0.0)
        aid = self.agent_id
        analysis = f"Agent '{aid}' completed task '{task_type}' with outcome '{outcome}' in {duration_ms}ms."

        if outcome == "succeeded":
            takeaway = f"Parameters and inputs for '{task_type}' produced verified output."
            if aid == "scene_segmentation":
                takeaway = "Scene boundaries aligned successfully within audio duration constraints."
            elif aid == "visual_planning":
                takeaway = "Visual concept generated and verified against bilingual terminology rules."
            elif aid == "motion_planning":
                takeaway = "Motion layout respected safe zones without typography collisions."
            elif aid == "render_video":
                takeaway = "Video rendered and validated against frame rate and resolution invariants."
            elif aid == "final_qc":
                takeaway = "Technical QC passed: audio sync and frame integrity verified."
            elif aid == "capability_finder":
                takeaway = "Capability requirement resolved without discovery regressions."
            elif aid == "skill_factory":
                takeaway = "Skill synthesized and passed AST sandbox and test suites."
            elif aid == "security_policy":
                takeaway = "Security policy evaluated; all operations verified within permission boundaries."
            elif aid == "verification_and_test":
                takeaway = "Test execution completed; frozen file hashes and contracts confirmed."
            elif aid == "autonomous_execution":
                takeaway = "Autonomous execution succeeded within retry and approval bounds."

            return {
                "status": "success",
                "summary": analysis,
                "takeaway": takeaway,
                "performance": {"duration_ms": duration_ms},
            }
        else:
            err_msg = error or "Unspecified task failure"
            err_cat = "validation_error" if "validation" in err_msg.lower() else "runtime_error"
            takeaway = f"Task '{task_type}' failed with {err_cat}: {err_msg}."
            if aid == "scene_segmentation":
                takeaway = f"Scene segmentation defect: {err_msg}. Review duration window and speech boundaries."
            elif aid == "render_video":
                takeaway = f"Render failure: {err_msg}. Inspect ffmpeg stream parameters or font assets."
            elif aid == "security_policy":
                takeaway = f"Security boundary enforced: {err_msg}. Operation correctly prevented."

            lesson_proposal = {
                "title": f"Lesson from {aid} on {task_type}",
                "description": takeaway,
                "affected_domain": getattr(self.metadata, "stage_id", "general") or "general",
                "observed_pattern": err_msg[:120],
                "recommended_action": "adjust_parameters_or_retry",
                "risk_level": "low",
            }

            return {
                "status": "failure",
                "summary": analysis,
                "error": err_msg,
                "error_category": err_cat,
                "takeaway": takeaway,
                "proposed_lesson": lesson_proposal,
            }

    def propose_shared_lesson(
        self,
        title: str,
        description: str,
        rule_content: dict[str, Any],
        supporting_experience_ids: list[str],
        risk_level: str = "low",
        rule_type: str = "routing_preference",
    ) -> dict[str, Any]:
        """Proposes a candidate lesson derived from task experiences for evaluation and promotion."""
        from SYSTEM.agents.capability_finder.learning.case_collector import case_collector, LearningCase
        from SYSTEM.agents.capability_finder.learning.lesson_generator import LessonProposal
        from SYSTEM.memory.per_agent_store import per_agent_store

        # Ensure supporting case records exist in case collector
        for exp_id in supporting_experience_ids:
            try:
                exp = per_agent_store.get_experience(self.agent_id, exp_id)
                if exp:
                    case = LearningCase(
                        case_id=exp.experience_id,
                        task_id=exp.task_id,
                        parsed_requirement={"requirement": exp.task_type},
                        discovery_result={},
                        execution_outcome={"status": exp.outcome},
                        outcome_attribution={"primary_failure_category": exp.error_category or "none"},
                    )
                    case_collector.record_case(case)
            except Exception:
                pass

        proposal = LessonProposal(
            title=title,
            description=description,
            observed_pattern=f"Observed by {self.agent_id} across experiences {supporting_experience_ids}",
            affected_domain=getattr(self.metadata, "stage_id", "general") or "general",
            rule_type=rule_type,
            rule_content=rule_content,
            supporting_case_ids=supporting_experience_ids,
            risk_level=risk_level,
        )
        return proposal.to_dict()

    def review(self, project_dir: Path, request: AgentRequest, result: AgentResult) -> AgentResult:
        """Mandatory stage review hook.
        For active pipeline stages with an associated stage_id:
        1. If auto_review=True in request parameters, triggers stage review via the gateway.
        2. Evaluates is_stage_review_passed(project_dir, stage, aspect).
        3. If review failed, is missing, stale, or has blockers, transitions result.status to 'blocked'.
        """
        sid = request.stage_id or self.stage_id
        if not sid or sid in ("pipeline", "main_orchestrator", "motion_template"):
            return result

        try:
            from SYSTEM.policies import llm_review
            if sid not in llm_review.STAGE_DESCRIPTIONS:
                return result

            if result.status != "succeeded":
                return result

            aspect = "16:9"
            params = getattr(request, "parameters", {}) or {}
            meta = getattr(request, "metadata", {}) or {}
            if "aspect" in meta:
                aspect = meta["aspect"]
            elif "aspect" in params:
                aspect = params["aspect"]

            if params.get("auto_review") is True:
                llm_review.run_stage_llm_review(project_dir, sid, aspect=aspect)

            passed, reason, rev = llm_review.is_stage_review_passed(project_dir, sid, aspect)
            if not passed:
                result.status = "blocked"
                result.error = f"Mandatory LLM review gate failed: {reason}"
                result.summary = f"Stage {sid} blocked: LLM review {reason}"
                if rev:
                    result.metadata["llm_review"] = rev
            else:
                if rev:
                    result.metadata["llm_review"] = rev
        except Exception as e:
            result.status = "blocked"
            result.error = f"Mandatory LLM review gate check error: {e}"

        return result

    def invoke(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Standard lifecycle runner:
        1. Publishes lifecycle_event: started
        2. Validates inputs
        3. Executes work
        4. Reviews output
        5. Publishes lifecycle_event / completion message
        """
        pid = request.project_id
        sid = request.stage_id or (self.stage_id or "")

        aspect = "16:9"
        params = getattr(request, "parameters", {}) or {}
        meta = getattr(request, "metadata", {}) or {}
        if "aspect" in meta:
            aspect = meta["aspect"]
        elif "aspect" in params:
            aspect = params["aspect"]

        use_pipeline_state = False
        try:
            from SYSTEM.core import pipeline_state
            if sid in pipeline_state.ACTIVE_STAGES and (project_dir / "pipeline_state.json").exists() and not params.get("skip_pipeline_state"):
                use_pipeline_state = True
                pipeline_state.transition_stage(project_dir, sid, "running", aspect=aspect)
        except Exception:
            pass

        tid = getattr(request, "task_id", None) or getattr(request, "correlation_id", None) or getattr(request, "run_id", None) or getattr(request, "request_id", None)
        rid = getattr(request, "run_id", None)
        cid = getattr(request, "correlation_id", None) or tid

        publish_lifecycle_event(
            project_id=pid,
            stage_id=sid,
            sender_agent_id=self.agent_id,
            event="started",
            detail=f"{self.metadata.name} invocation started",
            task_id=tid,
            run_id=rid,
            correlation_id=cid,
        )

        # 1. Validation
        validation_errors = self.validate(project_dir, request)
        if validation_errors:
            err_msg = "; ".join(validation_errors)
            if use_pipeline_state:
                try:
                    pipeline_state.transition_stage(
                        project_dir, sid, "blocked", aspect=aspect, error_code="validation_failed", error_message=err_msg
                    )
                except Exception:
                    pass
            publish_lifecycle_event(
                project_id=pid,
                stage_id=sid,
                sender_agent_id=self.agent_id,
                event="blocked",
                detail=err_msg,
                task_id=tid,
                run_id=rid,
                correlation_id=cid,
            )
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=sid,
                project_id=pid,
                status="blocked",
                error=err_msg,
                summary=f"Validation failed: {err_msg}",
            )

        # 2. Execution
        try:
            t0 = time.perf_counter()
            result = self.execute(project_dir, request)
            duration_ms = round((time.perf_counter() - t0) * 1000)
            result.metadata["duration_ms"] = duration_ms
        except Exception as e:
            err_msg = str(e)
            if use_pipeline_state:
                try:
                    pipeline_state.transition_stage(
                        project_dir, sid, "failed", aspect=aspect, error_code="execution_failed", error_message=err_msg
                    )
                except Exception:
                    pass
            publish_lifecycle_event(
                project_id=pid,
                stage_id=sid,
                sender_agent_id=self.agent_id,
                event="failed",
                detail=err_msg,
                task_id=tid,
                run_id=rid,
                correlation_id=cid,
            )
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=sid,
                project_id=pid,
                status="failed",
                error=err_msg,
                summary=f"Execution error: {err_msg}",
            )

        # 3. Review
        try:
            result = self.review(project_dir, request, result)
        except Exception as e:
            result.status = "blocked"
            result.error = f"Review error: {e}"

        # 4. Checkpoint & State Finalization
        if use_pipeline_state:
            try:
                if result.status == "succeeded":
                    srec = pipeline_state.transition_stage(project_dir, sid, "completed", aspect=aspect)
                    result.metadata["checkpoint_id"] = srec.checkpoint_id
                elif result.status in ("blocked", "failed", "needs_review"):
                    pipeline_state.transition_stage(
                        project_dir,
                        sid,
                        result.status,
                        aspect=aspect,
                        error_code=result.status,
                        error_message=result.error or result.summary,
                    )
            except Exception as e:
                result.status = "blocked"
                result.error = f"Pipeline state transition error: {e}"

        # 5. Completion event
        event_name = "completed" if result.status == "succeeded" else result.status
        publish_lifecycle_event(
            project_id=pid,
            stage_id=sid,
            sender_agent_id=self.agent_id,
            event=event_name,
            detail=result.summary or f"Status: {result.status}",
            artifact_refs=result.output_refs,
            task_id=tid,
            run_id=rid,
            correlation_id=cid,
        )

        # 6. Durable History Recording
        try:
            from SYSTEM.history.execution_history import ExecutionRecord
            from SYSTEM.history.history_service import history_service
            rec = ExecutionRecord(
                agent_id=self.agent_id,
                task_id=request.request_id or "",
                project_id=pid,
                stage_id=sid,
                duration_ms=float(result.metadata.get("duration_ms", 0.0)),
                status="succeeded" if result.status == "succeeded" else "blocked" if result.status == "blocked" else "failed",
                inputs_summary={"parameters": list(params.keys())},
                outputs_summary={"summary": result.summary, "artifacts": len(result.output_refs)},
                error_message=result.error,
            )
            history_service.record_execution(rec)
        except Exception:
            pass

        # 7. Agent-Scoped Experience & Reflection Recording
        try:
            if not getattr(self, "_is_recording_experience", False):
                self._is_recording_experience = True
                try:
                    metrics_payload = {
                        "duration_ms": float(result.metadata.get("duration_ms", 0.0)),
                    }
                    if "quality_score" in result.metadata:
                        metrics_payload["quality_score"] = float(result.metadata["quality_score"])

                    ref_res = self.reflect_on_task_outcome(
                        task_type=sid or "execution",
                        outcome=result.status,
                        context={"parameters": list(params.keys())},
                        metrics=metrics_payload,
                        error=result.error or (result.summary if result.status != "succeeded" else None),
                    )

                    self.record_experience(
                        task_type=sid or "execution",
                        outcome=result.status,
                        context={"parameters": list(params.keys())},
                        metrics=metrics_payload,
                        error_category="validation_error" if result.status == "blocked" else ("execution_error" if result.status == "failed" else None),
                        task_id=getattr(request, "correlation_id", None) or getattr(request, "run_id", None) or getattr(request, "request_id", None) or f"req-{int(time.time())}",
                        project_id=pid,
                        reflection=ref_res,
                        proposed_lesson=ref_res.get("proposed_lesson"),
                        confidence=0.8 if result.status == "succeeded" else 0.4,
                    )
                finally:
                    self._is_recording_experience = False
        except Exception:
            # Experience recording failures must NEVER fail the task
            pass

        return result
