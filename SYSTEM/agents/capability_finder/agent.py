"""Capability Finder System Agent (Canonical).

Discovers, inspects, and evaluates:
1. Registered and implemented agents, skills, and tools.
2. Natural language capability requirements and structured constraints.
3. Static AST-based code definitions without executing unverified code.
4. Capability matching, deduplication, and structured gap analysis.
5. System runtime prerequisites (FFmpeg, local Whisper weights, etc.).
6. Evidence-based experience memory, outcome attribution, and reviewer feedback.
7. Candidate lesson generation, offline benchmark evaluation, and non-regression gates.
8. Controlled, atomic knowledge promotion and safe rollback management.

Canonical Location: SYSTEM/agents/capability_finder/agent.py
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.registries.skill_registry import registry as skill_registry
from SYSTEM.registries.tool_registry import tool_registry

from .discovery.ast_scanner import ast_scanner
from .discovery.gap_analyzer import gap_analyzer
from .discovery.matcher import capability_matcher
from .discovery.requirement_parser import requirement_parser
from .discovery.semantic_index import semantic_index
from .github_discovery import github_discovery_service
from .learning.case_collector import LearningCase, case_collector
from .learning.feedback_processor import feedback_processor
from .learning.knowledge_promoter import knowledge_promoter
from .learning.lesson_evaluator import LearningEvaluation, lesson_evaluator
from .learning.lesson_generator import LessonProposal, lesson_generator
from .learning.outcome_analyzer import outcome_analyzer
from .learning.rollback_manager import rollback_manager


class CapabilityFinderAgent(BaseAgent):
    """System agent specialized in requirement parsing, AST code discovery, capability gap analysis, and self-learning."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="capability_finder",
                name="Capability Finder Agent",
                version="3.0.0",
                category=AgentCategory.SYSTEM_SUBAGENT,
                status=AgentStatus.IMPLEMENTED,
                purpose="Discovers, parses, matches, and evaluates system capabilities, code artifacts, and prerequisites with evidence-based self-learning.",
                capabilities=[
                    "capability-query",
                    "skill-discovery",
                    "prerequisite-inspection",
                    "requirement-parsing",
                    "semantic-search",
                    "semantic-indexing",
                    "ast-discovery",
                    "gap-analysis",
                    "experience-memory",
                    "outcome-attribution",
                    "self-learning",
                    "knowledge-promotion",
                    "knowledge-rollback",
                ],
                allowed_tools=["agent_registry", "skill_registry", "tool_registry", "capability_registry"],
                owner="system-core",
            )
        super().__init__(metadata)

    @property
    def _registry(self):
        from SYSTEM.registries.agent_registry import registry
        return registry

    @property
    def _capability_registry(self):
        from SYSTEM.registries.capability_registry import capability_registry
        return capability_registry

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        action = request.parameters.get("action", "discover")
        query = request.parameters.get("query", "")
        domain = request.parameters.get("domain")
        check_prereqs = request.parameters.get("check_prerequisites", True)
        scan_ast = request.parameters.get("scan_ast", False)

        # Ensure central CapabilityRegistry is indexed
        if len(self._capability_registry.list_all()) == 0:
            self._capability_registry.sync_with_registries()

        # Ensure SemanticCapabilityIndex is initialized
        if semantic_index.get_stats()["total_documents"] == 0:
            semantic_index.rebuild_index(self._capability_registry.list_all())

        # -------------------------------------------------------------
        # 1. Administrative and Registry Actions
        # -------------------------------------------------------------
        if action == "sync_registry":
            sync_res = self._capability_registry.sync_with_registries(force=True)
            semantic_index.rebuild_index(self._capability_registry.list_all())
            index_stats = semantic_index.get_stats()
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Capability registry synchronized: {sync_res['total_records']} records. Semantic index: {index_stats['total_documents']} documents.",
                metadata={"sync_report": sync_res, "semantic_index": index_stats},
            )

        if action == "index_rebuild":
            all_recs = self._capability_registry.list_all()
            semantic_index.rebuild_index(all_recs)
            stats = semantic_index.get_stats()
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Semantic index rebuilt: {stats['total_documents']} documents indexed, vocabulary: {stats['vocabulary_size']}.",
                metadata={"semantic_index_stats": stats},
            )

        if action == "search_semantic":
            q_str = query or request.parameters.get("query_text", "")
            top_k = int(request.parameters.get("top_k", 10))
            min_sim = float(request.parameters.get("min_similarity", 0.15))
            hits = semantic_index.search_semantic(query=q_str, domain=domain, top_k=top_k, min_similarity=min_sim)
            results = []
            for cap_id, sim in hits:
                rec = self._capability_registry.get_capability(cap_id)
                results.append({
                    "capability_id": cap_id,
                    "similarity_score": sim,
                    "record": rec.to_dict() if rec else {},
                })
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Semantic search found {len(results)} matches for '{q_str}'.",
                metadata={"semantic_results": results, "query": q_str, "domain": domain},
            )

        if action == "prerequisites":
            prereqs_dict: dict[str, Any] = {
                "ffmpeg": shutil.which("ffmpeg") is not None,
                "ffprobe": shutil.which("ffprobe") is not None,
            }
            try:
                from SYSTEM.core import config
                models_dir = config.PROJECT_ROOT / "models"
                prereqs_dict["whisper_model_present"] = (models_dir / "hf").exists() or any(models_dir.glob("*.bin"))
            except Exception:
                prereqs_dict["whisper_model_present"] = False

            all_satisfied = all(prereqs_dict.values())
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded" if all_satisfied else "failed",
                summary=f"Prerequisites check: {'ALL SATISFIED' if all_satisfied else 'MISSING DEPENDENCIES'}.",
                metadata={"prerequisites": prereqs_dict, "satisfied": all_satisfied},
            )

        if action == "ast_scan":
            scan_target = request.parameters.get("target_path")
            target_dir = Path(scan_target) if scan_target else (project_dir / "SYSTEM" if project_dir else Path("."))
            ast_items = ast_scanner.scan_directory(target_dir)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"AST scan complete: {len(ast_items)} symbols discovered across {target_dir}.",
                metadata={"discovered_symbols": [item.to_dict() for item in ast_items]},
            )

        if action == "resolve_capability_workflow":
            target_agent = request.parameters.get("target_agent_id") or request.parameters.get("agent_id") or "main_orchestrator"
            req_str = request.parameters.get("requirement") or query
            auto_inst = request.parameters.get("auto_install", False)
            approval_request_id = request.parameters.get("approval_request_id")
            wf_res = self.resolve_capability_workflow(
                agent_id=target_agent,
                requirement=req_str,
                domain=domain,
                auto_install=auto_inst,
                approval_request_id=approval_request_id,
            )
            is_success = wf_res.get("status") in ("succeeded", "ready_for_installation")
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded" if is_success else "failed",
                summary=f"Capability workflow for '{req_str}' (agent: {target_agent}): {wf_res.get('status', 'unknown').upper()} at stage '{wf_res.get('stage', 'unknown')}'.",
                metadata={"workflow_result": wf_res},
            )

        # -------------------------------------------------------------
        # 2. Phase 3 Self-Learning Subsystem Actions
        # -------------------------------------------------------------
        if action == "record_outcome":
            task_id = request.parameters.get("task_id", "")
            parsed_req_dict = request.parameters.get("parsed_requirement", {})
            discovery_res = request.parameters.get("discovery_result", {})
            execution_res = request.parameters.get("execution_outcome", {})
            err_msg = request.parameters.get("execution_error")
            env_info = request.parameters.get("environment_info", {})

            attribution = outcome_analyzer.analyze_outcome(
                discovery_result=discovery_res,
                execution_outcome=execution_res,
                execution_error=err_msg,
                environment_info=env_info,
            )

            case = LearningCase(
                task_id=task_id,
                parsed_requirement=parsed_req_dict,
                discovery_result=discovery_res,
                execution_outcome=execution_res,
                outcome_attribution=attribution.to_dict(),
                environment_state=env_info,
            )
            case_collector.record_case(case)

            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Recorded learning case '{case.case_id}' with attribution: {attribution.primary_failure_category}.",
                metadata={"case_id": case.case_id, "attribution": attribution.to_dict()},
            )

        if action == "submit_feedback":
            case_id = request.parameters.get("case_id", "")
            feedback_data = request.parameters.get("feedback", {})
            if not feedback_data and "reviewer_id" in request.parameters:
                feedback_data = {
                    "reviewer_id": request.parameters.get("reviewer_id"),
                    "feedback_type": request.parameters.get("feedback_type", "correction"),
                    "accuracy_score": request.parameters.get("accuracy_score", 1.0),
                    "suggested_action": request.parameters.get("suggested_action"),
                    "suggested_delegate_id": request.parameters.get("suggested_delegate_id"),
                    "notes": request.parameters.get("notes", ""),
                }
            fb_res = feedback_processor.process_feedback(case_id, feedback_data)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded" if fb_res.is_valid else "failed",
                summary=f"Processed feedback '{fb_res.feedback_id}' for case '{case_id}'. Status: {fb_res.status}.",
                metadata={"feedback_report": fb_res.to_dict()},
            )

        if action == "generate_lessons":
            proposals = lesson_generator.generate_proposals()
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Generated {len(proposals)} candidate lesson proposal(s).",
                metadata={"proposals": [p.to_dict() for p in proposals]},
            )

        if action == "evaluate_proposal":
            prop_data = request.parameters.get("proposal", {})
            if isinstance(prop_data, dict):
                proposal = LessonProposal.from_dict(prop_data)
            else:
                proposal = prop_data
            evaluation = lesson_evaluator.evaluate_proposal(proposal)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Evaluated proposal '{proposal.proposal_id}'. Passed gate: {evaluation.passed_gate} (Delta: {evaluation.accuracy_delta:+.4f}).",
                metadata={"evaluation": evaluation.to_dict()},
            )

        if action == "promote_lesson":
            prop_data = request.parameters.get("proposal", {})
            eval_data = request.parameters.get("evaluation", {})
            authorized_by = request.parameters.get("authorized_by")
            operator_id = request.parameters.get("operator_id")
            role = request.parameters.get("role")
            approval_request_id = request.parameters.get("approval_request_id")
            check_provenance = request.parameters.get("check_case_existence", True)

            proposal = LessonProposal.from_dict(prop_data) if isinstance(prop_data, dict) else prop_data
            evaluation = LearningEvaluation(**eval_data) if isinstance(eval_data, dict) else eval_data

            try:
                report = knowledge_promoter.promote_proposal(
                    proposal=proposal,
                    evaluation=evaluation,
                    authorized_by=authorized_by,
                    operator_id=operator_id,
                    role=role,
                    approval_request_id=approval_request_id,
                    check_case_existence=check_provenance,
                )
                status = "succeeded"
                summary = f"Successfully promoted proposal '{proposal.proposal_id}' to active knowledge version {report['new_version']}."
            except Exception as e:
                status = "failed"
                summary = f"Promotion failed: {e}"
                report = {"error": str(e)}

            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status=status,
                summary=summary,
                metadata={"promotion_report": report},
            )

        if action == "rollback_knowledge":
            target_archive = request.parameters.get("target_archive_filename")
            authorized_by = request.parameters.get("authorized_by")
            operator_id = request.parameters.get("operator_id")
            role = request.parameters.get("role")
            approval_request_id = request.parameters.get("approval_request_id")
            try:
                rb_report = rollback_manager.rollback(
                    target_archive_filename=target_archive,
                    authorized_by=authorized_by,
                    operator_id=operator_id,
                    role=role,
                    approval_request_id=approval_request_id,
                )
                status = "succeeded"
                summary = f"Rollback succeeded. Restored version: {rb_report['restored_version']} from {rb_report['restored_from']}."
            except Exception as e:
                status = "failed"
                summary = f"Rollback failed: {e}"
                rb_report = {"error": str(e)}

            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status=status,
                summary=summary,
                metadata={"rollback_report": rb_report},
            )

        if action == "get_active_knowledge":
            active_data = knowledge_promoter.load_active_knowledge()
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Active knowledge version: {active_data.get('version', 'unknown')}.",
                metadata={"active_knowledge": active_data},
            )

        # -------------------------------------------------------------
        # 3. Standard Discovery Workflow with Active Knowledge Integration
        # -------------------------------------------------------------
        active_knowledge = knowledge_promoter.load_active_knowledge()

        # Apply active synonym expansions before parsing
        synonyms = active_knowledge.get("synonym_expansions", {})
        query_to_parse = query
        for k, v in synonyms.items():
            if k.lower() in query_to_parse.lower():
                query_to_parse = f"{query_to_parse} {v}"

        parsed_req = requirement_parser.parse(query_to_parse, request.parameters)

        # Apply active constraint overrides if configured for the domain
        constraint_overrides = active_knowledge.get("constraint_overrides", {})
        if parsed_req.domain in constraint_overrides:
            parsed_req.constraints.update(constraint_overrides[parsed_req.domain])

        # Backward-compatible agent, skill, and tool retrieval
        matching_agents = []
        for a in self._registry.list_all_agents():
            if not query or query.lower() in a.name.lower() or any(query.lower() in c.lower() for c in a.capabilities):
                matching_agents.append(a.to_dict())

        matching_skills = [
            s.to_dict()
            for s in skill_registry.search_skills(query=query, domain=domain or parsed_req.domain, status="approved")
        ]
        available_tools = [t.to_dict() for t in tool_registry.list_tools()]

        # Query central CapabilityRegistry
        candidate_records = self._capability_registry.search_capabilities(
            query=query or parsed_req.primary_capability,
            domain=domain or (parsed_req.domain if parsed_req.domain != "general" else None),
        )
        if not candidate_records:
            candidate_records = self._capability_registry.list_all()

        # If active knowledge specifies a preferred delegate for this domain, include its records
        routing_prefs = active_knowledge.get("routing_preferences", {})
        pref = routing_prefs.get(parsed_req.domain)
        if pref and pref.get("preferred_delegate_id"):
            pref_id = pref["preferred_delegate_id"]
            pref_records = self._capability_registry.search_capabilities(query=pref_id)
            seen_ids = {r.capability_id for r in candidate_records}
            for r in pref_records:
                if r.capability_id not in seen_ids:
                    candidate_records.append(r)
                    seen_ids.add(r.capability_id)

        # Optional AST scanning
        ast_items = []
        if scan_ast and project_dir:
            sys_dir = project_dir / "SYSTEM"
            if sys_dir.exists():
                ast_items = ast_scanner.scan_directory(sys_dir, max_depth=3)

        # Capability matching
        matches = capability_matcher.match(
            req=parsed_req,
            candidates=candidate_records,
            ast_items=ast_items,
        )

        # Apply active knowledge routing preferences to candidate matches
        routing_prefs = active_knowledge.get("routing_preferences", {})
        if parsed_req.domain in routing_prefs:
            pref = routing_prefs[parsed_req.domain]
            pref_id = pref.get("preferred_delegate_id")
            boost = float(pref.get("boost_score", 0.25))
            if pref_id:
                for m in matches:
                    if pref_id.lower() in m.source_id.lower() or pref_id.lower() in m.capability_id.lower():
                        m.score = min(1.0, round(max(m.score + boost, 0.85), 3))
                        m.match_type = "exact"
                        m.matched_by.append("active_knowledge_boost")
                # Re-sort matches by score descending
                matches.sort(key=lambda x: x.score, reverse=True)

        # Gap analysis
        gap_report = gap_analyzer.analyze(
            req=parsed_req,
            matches=matches,
            project_dir=project_dir,
        )

        # Environment prerequisites
        prereqs: dict[str, Any] = {}
        if check_prereqs:
            prereqs["ffmpeg_available"] = shutil.which("ffmpeg") is not None
            prereqs["ffprobe_available"] = shutil.which("ffprobe") is not None
            try:
                from SYSTEM.core import config
                models_dir = config.PROJECT_ROOT / "models"
                prereqs["whisper_model_present"] = (models_dir / "hf").exists() or any(models_dir.glob("*.bin"))
            except Exception:
                prereqs["whisper_model_present"] = False

        summary = (
            f"Capability discovery complete: {len(matching_agents)} agents, {len(matching_skills)} skills, "
            f"{len(matches)} matched capabilities. Gap status: {gap_report.overall_status.upper()} "
            f"(Action: {gap_report.recommended_action}). Active knowledge version: {active_knowledge.get('version', '1.0.0')}."
        )

        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status="succeeded",
            summary=summary,
            metadata={
                # Backward-compatible fields
                "matching_agents": matching_agents,
                "matching_skills": matching_skills,
                "available_tools": available_tools,
                "prerequisites": prereqs,
                # Phase 2 upgraded fields
                "parsed_requirement": parsed_req.to_dict(),
                "capability_matches": [m.to_dict() for m in matches[:10]],
                "gap_analysis": gap_report.to_dict(),
                "recommended_action": gap_report.recommended_action,
                "action_rationale": gap_report.action_rationale,
                "suggested_delegate_id": gap_report.suggested_delegate_id,
                "evidence_refs": gap_report.evidence_summary,
                # Phase 3 self-learning fields
                "active_knowledge_version": active_knowledge.get("version", "1.0.0"),
                # Semantic Index fields
                "semantic_index_stats": semantic_index.get_stats(),
            },
        )

    def resolve_capability_workflow(
        self,
        agent_id: str,
        requirement: str,
        domain: str | None = None,
        auto_install: bool = False,
        approval_request_id: str | None = None,
    ) -> dict[str, Any]:
        """Executes the 12-step autonomous capability resolution workflow:
        1. Checks agent private skills.
        2. Falls back to central skill library.
        3. If unavailable, invokes automatic GitHub discovery.
        4. Evaluates candidates (relevance, license, security).
        5. Adapts candidate via SkillFactory or creates new skill.
        6. Validates via AST sandbox and test runner.
        7. Installs locally for the requesting agent.
        8. Returns structured resolution outcome.
        """
        import re
        from SYSTEM.registries.skill_registry import registry as skill_reg

        # 1. Check agent's private skills
        local_res = skill_reg.resolve_agent_skill(agent_id, requirement)
        if local_res.get("status") == "resolved" and local_res.get("scope") == "local":
            return {
                "status": "succeeded",
                "stage": "agent_private_skills",
                "source": "agent_local",
                "agent_id": agent_id,
                "requirement": requirement,
                "skill": local_res,
            }

        # 2. Check central skill library
        if local_res.get("status") == "resolved" and local_res.get("scope") == "central":
            return {
                "status": "succeeded",
                "stage": "central_library",
                "source": "central_library",
                "agent_id": agent_id,
                "requirement": requirement,
                "skill": local_res,
            }

        # 3. Invoke GitHub discovery
        disc_res = github_discovery_service.search(requirement, domain=domain, limit=3)
        if disc_res.status == "succeeded" and disc_res.candidates:
            # 4. Evaluate candidates for relevance, license suitability, and security
            best_candidate = None
            for cand in disc_res.candidates:
                if cand.compatibility_status in ("compatible", "needs_adapter"):
                    best_candidate = cand
                    break

            if best_candidate is not None:
                # Stage and static inspect without executing untrusted code
                stage_info = github_discovery_service.stage_and_inspect(best_candidate)
                if best_candidate.security_review_status == "rejected":
                    return {
                        "status": "blocked",
                        "stage": "security_audit",
                        "agent_id": agent_id,
                        "requirement": requirement,
                        "candidate": best_candidate.full_name,
                        "reason": f"Discovered candidate rejected by static security audit: {stage_info.get('audit', {}).get('findings')}",
                    }

                # Adapt candidate into SkillSpecification
                from SYSTEM.agents.skill_factory.generator import skill_generator
                from SYSTEM.agents.skill_factory.lifecycle import SkillLifecycle
                from SYSTEM.agents.skill_factory.publisher import skill_publisher
                from SYSTEM.agents.skill_factory.security_validator import security_validator
                from SYSTEM.agents.skill_factory.specification import SkillSpecification

                clean_skill_id = re.sub(r"[^\w\-.]", "_", requirement).lower().strip("_")
                spec = SkillSpecification(
                    skill_id=clean_skill_id,
                    name=best_candidate.name.replace("-", " ").title(),
                    purpose=best_candidate.description,
                    domain=domain or "general",
                    version="1.0.0",
                    capabilities=[requirement],
                    license=best_candidate.license if best_candidate.license != "Unknown" else "MIT",
                    license_evidence=f"Discovered from GitHub: {best_candidate.url}",
                    provenance=f"github:{best_candidate.full_name}",
                    target_agent_id=agent_id,
                    compatible_agents=[agent_id],
                )

                # Synthesize draft package
                draft = skill_generator.generate(spec, allow_template_fallback=True)

                # Static security audit
                sec_audit = security_validator.audit(draft.content, filename=draft.filename)
                if not sec_audit.passed:
                    return {
                        "status": "blocked",
                        "stage": "specification_security",
                        "agent_id": agent_id,
                        "requirement": requirement,
                        "reason": f"Adapted skill draft failed security audit: {'; '.join(sec_audit.findings)}",
                    }

                # Install locally for target agent if requested
                if auto_install:
                    lifecycle = SkillLifecycle(skill_id=spec.skill_id, version=spec.version, current_state="APPROVED")
                    prom_res = skill_publisher.promote_skill(
                        spec=spec,
                        content=draft.content,
                        lifecycle=lifecycle,
                        operator_id="capability_finder_workflow",
                        role="system",
                        approval_request_id=approval_request_id,
                        target_agent_id=agent_id,
                    )
                    return {
                        "status": "succeeded",
                        "stage": "adapted_and_installed",
                        "source": "github_adapted",
                        "agent_id": agent_id,
                        "skill_id": clean_skill_id,
                        "candidate": best_candidate.full_name,
                        "promotion": prom_res.to_dict(),
                    }

                return {
                    "status": "ready_for_installation",
                    "stage": "github_discovered",
                    "source": "github",
                    "agent_id": agent_id,
                    "requirement": requirement,
                    "candidate": best_candidate.to_dict(),
                    "draft": draft.to_dict(),
                }

        return {
            "status": "missing_capability",
            "stage": "discovery_exhausted",
            "agent_id": agent_id,
            "requirement": requirement,
            "diagnostic": disc_res.diagnostic or "No suitable candidate discovered on GitHub.",
        }
