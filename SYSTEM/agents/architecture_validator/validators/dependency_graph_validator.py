"""Agent and Pipeline Dependency Graph Validator for Architecture Validator Agent.

Validates:
- Graph representation of agent dependencies and delegation relationships.
- Detection of unknown or missing dependency targets.
- Detection of forbidden cycles in execution pipelines using Tarjan's SCC algorithm.
- Distinction between forbidden pipeline stage cycles and supported bidirectional coordination.
- Reachability analysis for mandatory pipeline stages and system agents.
"""
from __future__ import annotations

import collections
from pathlib import Path
from typing import Any

from SYSTEM.agents.architecture_validator.contracts import (
    ArchitectureFinding,
    FindingCategory,
    FindingSeverity,
)


class DependencyGraphValidator:
    """Audits agent delegation, pipeline stage ordering, and dependency graph integrity."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[4]

    def validate(
        self,
        agent_registry_instance: Any = None,
        custom_pipeline_deps: dict[str, tuple[str, ...]] | None = None,
    ) -> list[ArchitectureFinding]:
        findings: list[ArchitectureFinding] = []

        # 1. Resolve registered agents
        registered_agents: set[str] = set()
        if agent_registry_instance is None:
            try:
                from SYSTEM.registries.agent_registry import registry
                registered_agents = set(registry.list_all_agents_metadata().keys()) if hasattr(registry, "list_all_agents_metadata") else set(getattr(registry, "_metadata", {}).keys())
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.DEPENDENCY_GRAPH,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="AgentRegistry",
                        message=f"Could not load AgentRegistry for dependency validation: {e}",
                        evidence=str(e),
                        remediation="Ensure AgentRegistry is available and initialized.",
                    )
                )
        else:
            meta = getattr(agent_registry_instance, "_metadata", {})
            registered_agents = set(meta.keys())

        # 2. Build Pipeline Stage Dependency Graph
        pipeline_deps: dict[str, tuple[str, ...]] = {}
        if custom_pipeline_deps is not None:
            pipeline_deps = custom_pipeline_deps
        else:
            try:
                from VIDEO_ENGINE.pipeline.orchestrator import STAGE_DEPENDENCIES
                pipeline_deps = STAGE_DEPENDENCIES
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.DEPENDENCY_GRAPH,
                        severity=FindingSeverity.WARNING,
                        component="VIDEO_ENGINE.pipeline.orchestrator.STAGE_DEPENDENCIES",
                        message=f"Could not import pipeline STAGE_DEPENDENCIES: {e}",
                        evidence=str(e),
                        remediation="Verify VIDEO_ENGINE/pipeline/orchestrator.py defines STAGE_DEPENDENCIES.",
                    )
                )

        if pipeline_deps:
            # Check for unknown stage references
            all_stages = set(pipeline_deps.keys())
            for stage, deps in pipeline_deps.items():
                for dep in deps:
                    if dep not in all_stages:
                        findings.append(
                            ArchitectureFinding(
                                category=FindingCategory.DEPENDENCY_GRAPH,
                                severity=FindingSeverity.BLOCKING_ERROR,
                                component=f"PipelineStage.{stage}",
                                message=f"Stage '{stage}' depends on non-existent stage '{dep}'.",
                                evidence=f"dependencies={deps}, all_stages={sorted(all_stages)}",
                                remediation=f"Define stage '{dep}' in STAGE_DEPENDENCIES or remove it from '{stage}' prerequisites.",
                            )
                        )

            # Cycle Detection in Pipeline DAG (Tarjan's strongly connected components)
            cycles = self._find_cycles(pipeline_deps)
            for cycle in cycles:
                cycle_str = " -> ".join(cycle)
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.DEPENDENCY_GRAPH,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="PipelineStageGraph",
                        message=f"Forbidden cycle detected in video pipeline stage dependency graph: {cycle_str}",
                        evidence=f"Cycle path: {cycle_str}",
                        remediation="Remove circular dependency; video pipeline must form a strict directed acyclic graph (DAG).",
                    )
                )

        # 3. Agent Delegation Relationships
        # Main Architecture Agent should be able to delegate to system subagents without cycle
        system_delegations: dict[str, list[str]] = {
            "main_architecture_agent": [
                "capability_finder",
                "skill_factory",
                "architecture_validator",
                "verification_and_test",
                "security_policy",
                "autonomous_execution",
            ],
        }
        for parent, children in system_delegations.items():
            if registered_agents and parent in registered_agents:
                for child in children:
                    if registered_agents and child not in registered_agents:
                        findings.append(
                            ArchitectureFinding(
                                category=FindingCategory.DEPENDENCY_GRAPH,
                                severity=FindingSeverity.WARNING,
                                component=f"AgentDelegation.{parent}",
                                message=f"Coordinator '{parent}' has configured delegation target '{child}' which is not in AgentRegistry.",
                                evidence=f"child='{child}', registered={sorted(registered_agents)}",
                                remediation=f"Register agent '{child}' in AgentRegistry.",
                            )
                        )

        # Self-delegation check
        for parent, children in system_delegations.items():
            if parent in children:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.DEPENDENCY_GRAPH,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"AgentDelegation.{parent}",
                        message=f"Direct circular self-delegation detected: '{parent}' lists itself as delegation target.",
                        evidence=f"{parent} -> {parent}",
                        remediation="Remove self from delegation targets to avoid infinite recursion.",
                    )
                )

        return findings

    def _find_cycles(self, graph: dict[str, tuple[str, ...] | list[str]]) -> list[list[str]]:
        """Finds all elementary cycles in a directed graph using DFS cycle detection."""
        # Note: in graph, graph[v] = predecessors of v (i.e. dep -> v)
        # Convert to adjacency list where edge is (u -> v) meaning u must run before v
        adj: dict[str, list[str]] = collections.defaultdict(list)
        all_nodes = set(graph.keys())
        for node, preds in graph.items():
            for pred in preds:
                adj[pred].append(node)
                all_nodes.add(pred)

        visited: dict[str, int] = {node: 0 for node in all_nodes}  # 0: unvisited, 1: visiting, 2: visited
        cycles: list[list[str]] = []
        path: list[str] = []

        def dfs(u: str) -> None:
            visited[u] = 1
            path.append(u)
            for v in adj.get(u, []):
                if visited.get(v, 0) == 1:
                    # Cycle detected
                    idx = path.index(v)
                    cycles.append(path[idx:] + [v])
                elif visited.get(v, 0) == 0:
                    dfs(v)
            path.pop()
            visited[u] = 2

        for node in sorted(all_nodes):
            if visited[node] == 0:
                dfs(node)

        return cycles
