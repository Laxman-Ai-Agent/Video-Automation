"""Authoritative Agent Registry: the Agent System's own agents (the Main Architecture Agent and its 6 subagents) plus the agents a connected
domain project provides through the integration interface (SYSTEM/core/integrations.py, capability 'agent_entries': the video project's 15)."""
from __future__ import annotations

from typing import Type

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentCategory, AgentMetadata, AgentStatus
from SYSTEM.core import integrations

from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent
from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent
from SYSTEM.agents.architecture_validator.agent import ArchitectureValidatorAgent
from SYSTEM.agents.verification_and_test.agent import VerificationAndTestAgent
from SYSTEM.agents.security_policy.agent import SecurityPolicyAgent
from SYSTEM.agents.autonomous_execution.agent import AutonomousExecutionAgent

# Backward compatibility aliases
AutonomousExecutionAdapter = AutonomousExecutionAgent
ArchitectureValidatorAdapter = ArchitectureValidatorAgent
VerificationAndTestAdapter = VerificationAndTestAgent
SecurityPolicyAdapter = SecurityPolicyAgent


class AgentRegistry:
    """Authoritative registry mapping stable Agent IDs to metadata and allowlisted adapters."""

    def __init__(self) -> None:
        self._metadata: dict[str, AgentMetadata] = {}
        self._adapters: dict[str, BaseAgent] = {}
        self._synced_entries: object = None
        self._init_defaults()

    def _init_defaults(self) -> None:
        entries: list[tuple[AgentMetadata, Type[BaseAgent]]] = [
            (
                AgentMetadata(
                    agent_id="main_architecture_agent",
                    name="Main Architecture Agent",
                    version="1.0.0",
                    category=AgentCategory.ORCHESTRATOR,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Coordinates agent discovery, high-level goal decomposition, task assignment, and system governance.",
                    capabilities=["goal_planning", "task_decomposition", "agent_delegation", "system_governance"],
                    allowed_tools=["agent_registry", "tool_registry", "skill_registry", "memory_service", "history_service"],
                    owner="system",
                ),
                MainArchitectureAgent,
            ),
            (
                AgentMetadata(
                    agent_id="capability_finder",
                    name="Capability Finder Agent",
                    version="1.0.0",
                    category=AgentCategory.SYSTEM_SUBAGENT,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Discovers matching agents and skills based on task specifications and inspects prerequisite readiness.",
                    capabilities=["agent_discovery", "skill_discovery", "prerequisite_inspection"],
                    allowed_tools=["agent_registry", "skill_registry", "tool_registry"],
                    owner="system",
                ),
                CapabilityFinderAgent,
            ),
            (
                AgentMetadata(
                    agent_id="skill_factory",
                    name="Skill Factory Agent",
                    version="1.0.0",
                    category=AgentCategory.SYSTEM_SUBAGENT,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Generates, registers, and audits custom skills following strict YAML frontmatter and security rules.",
                    capabilities=["skill_generation", "security_auditing", "skill_registration"],
                    allowed_tools=["skill_registry", "ast_validator"],
                    owner="system",
                ),
                SkillFactoryAgent,
            ),
            (
                AgentMetadata(
                    agent_id="architecture_validator",
                    name="Architecture Validator Agent",
                    version="1.0.0",
                    category=AgentCategory.SYSTEM_SUBAGENT,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Audits architectural consistency, agent and capability registries, dependency graphs, video pipeline integrity, and security boundaries.",
                    capabilities=[
                        "agent-registry-validation",
                        "capability-registry-validation",
                        "dependency-graph-validation",
                        "video-pipeline-validation",
                        "contract-validation",
                        "security-boundary-validation",
                        "full-architecture-audit",
                    ],
                    allowed_tools=[
                        "agent_registry",
                        "skill_registry",
                        "capability_registry",
                        "ast_scanner",
                        "hash_verifier",
                    ],
                    owner="system",
                ),
                ArchitectureValidatorAgent,
            ),
            (
                AgentMetadata(
                    agent_id="verification_and_test",
                    name="Verification & Test Agent",
                    version="1.0.0",
                    category=AgentCategory.SYSTEM_SUBAGENT,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Executes evidence-driven verification, component-mapped testing, failure diagnosis, frozen-file integrity checks, and regression protection for the video automation system.",
                    capabilities=[
                        "change-verification",
                        "component-test-mapping",
                        "test-execution",
                        "result-capture",
                        "failure-diagnosis",
                        "regression-protection",
                        "frozen-hash-verification",
                        "evidence-based-verdict",
                    ],
                    allowed_tools=[
                        "pytest_runner",
                        "hash_verifier",
                        "agent_registry",
                        "component_mapper",
                        "diagnostician",
                    ],
                    owner="system",
                ),
                VerificationAndTestAgent,
            ),
            (
                AgentMetadata(
                    agent_id="security_policy",
                    name="Security Policy Agent",
                    version="1.0.0",
                    category=AgentCategory.SYSTEM_SUBAGENT,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Evaluates security policies, agent permissions, tool access, file and sandbox boundaries, approval requirements, and enforcement for the video automation system.",
                    capabilities=[
                        "policy-evaluation",
                        "agent-authorization",
                        "tool-access-control",
                        "file-boundary-enforcement",
                        "approval-verification",
                        "risk-classification",
                        "security-audit",
                    ],
                    allowed_tools=[
                        "agent_registry",
                        "tool_registry",
                        "approval_engine",
                        "policy_enforcer",
                        "hash_verifier",
                    ],
                    owner="system",
                ),
                SecurityPolicyAgent,
            ),
            (
                AgentMetadata(
                    agent_id="autonomous_execution",
                    name="Autonomous Execution Agent",
                    version="1.0.0",
                    category=AgentCategory.SYSTEM_SUBAGENT,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Supervises autonomous task execution, bounded failure recovery, durable checkpointing, and independent completion verification without competing with the Main Architecture Agent or Video Pipeline Orchestrator.",
                    capabilities=[
                        "task-execution",
                        "bounded-recovery",
                        "checkpoint-persistence",
                        "task-resume",
                        "loop-prevention",
                        "verification-dispatch",
                    ],
                    allowed_tools=[
                        "agent_registry",
                        "security_policy",
                        "verification_and_test",
                        "checkpoint_manager",
                        "recovery_manager",
                    ],
                    owner="system",
                ),
                AutonomousExecutionAgent,
            ),
        ]

        for meta, adapter_cls in entries:
            self.register(meta, adapter_cls)

    def register(self, meta: AgentMetadata, adapter_cls: Type[BaseAgent], allow_replace: bool = False) -> None:
        """Registers an agent metadata entry and instantiates its adapter."""
        if not meta.agent_id:
            raise ValueError("Agent ID cannot be empty")
        if not issubclass(adapter_cls, BaseAgent):
            raise TypeError(f"Adapter {adapter_cls} must inherit from BaseAgent")
        if not allow_replace and meta.agent_id in self._metadata:
            raise ValueError(f"Agent ID '{meta.agent_id}' is already registered in AgentRegistry. Duplicate registration rejected.")

        self._metadata[meta.agent_id] = meta
        adapter = adapter_cls(meta)
        if hasattr(adapter, "set_agent_registry"):
            adapter.set_agent_registry(self)
        self._adapters[meta.agent_id] = adapter

    def _sync_integrations(self) -> None:
        """The agents a connected domain project provides join the registry, whenever that project connects (checked before every lookup)."""
        entries = integrations.get("agent_entries")
        if entries is None or entries is self._synced_entries:
            return
        self._synced_entries = entries          # set first: an adapter that asks the registry while it is built must not start a second sync
        for meta, adapter_cls in entries:
            if meta.agent_id not in self._metadata:
                self.register(meta, adapter_cls)

    def get(self, agent_id: str) -> AgentMetadata | None:
        self._sync_integrations()
        return self._metadata.get(agent_id)

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        self._sync_integrations()
        return self._adapters.get(agent_id)

    get_adapter = get_agent  # Backward compatibility alias

    def list_agents(self, include_system: bool = False) -> list[AgentMetadata]:
        """Returns registered agent metadata. Defaults to the connected domain project's agents (the video project's 15: the orchestrator and one agent per stage)."""
        if include_system:
            return self.list_all_agents()
        return self.list_video_agents()

    def list_all_agents(self) -> list[AgentMetadata]:
        """Returns all registered agents: the Agent System's own and those of a connected domain project."""
        self._sync_integrations()
        return list(self._metadata.values())

    def list_video_agents(self) -> list[AgentMetadata]:
        """Returns the video generation agent metadata records (the orchestrator and one agent per stage); none unless the video project is connected."""
        self._sync_integrations()
        return [
            m for m in self._metadata.values()
            if m.category in (AgentCategory.VIDEO_ENGINE_AGENT, AgentCategory.ORCHESTRATOR)
            and m.agent_id != "main_architecture_agent"
        ]

    def list_system_agents(self) -> list[AgentMetadata]:
        """Returns all system agent metadata records (Main Architecture Agent and system subagents)."""
        self._sync_integrations()
        return [
            m for m in self._metadata.values()
            if m.category == AgentCategory.SYSTEM_SUBAGENT or m.agent_id == "main_architecture_agent"
        ]

    def validate_registry(self) -> list[str]:
        """Validates all registered agents for completeness, uniqueness, and consistency."""
        self._sync_integrations()
        issues: list[str] = []
        expected_video_ids = {
            "main_orchestrator",
            "audio_input",
            "audio_analyzer",
            "scene_segmentation",
            "visual_planning",
            "asset_collection",
            "motion_planning",
            "motion_template_selection",
            "motion_animation",
            "motion_timeline_validation",
            "timeline_build",
            "timeline_approval",
            "render_video",
            "final_qc",
            "final_video_delivery",
        }
        mandatory_system_ids = {
            "main_architecture_agent",
            "capability_finder",
            "skill_factory",
            "architecture_validator",
            "verification_and_test",
            "security_policy",
            "autonomous_execution",
        }
        actual_ids = set(self._metadata.keys())
        actual_video_ids = {
            m.agent_id for m in self._metadata.values()
            if m.category in (AgentCategory.VIDEO_ENGINE_AGENT, AgentCategory.ORCHESTRATOR)
            and m.agent_id != "main_architecture_agent"
        }
        missing_video = expected_video_ids - actual_video_ids
        if missing_video:
            issues.append(f"Missing logical video agents: {sorted(missing_video)}")

        unexpected_video = actual_video_ids - expected_video_ids
        if unexpected_video:
            issues.append(f"Unexpected video engine agents: {sorted(unexpected_video)}")

        missing_system = mandatory_system_ids - actual_ids
        if missing_system:
            issues.append(f"Missing mandatory system agents: {sorted(missing_system)}")

        for aid, meta in self._metadata.items():
            if not meta.name:
                issues.append(f"Agent {aid} has empty name")
            if not meta.purpose:
                issues.append(f"Agent {aid} has empty purpose")
            if aid not in self._adapters:
                issues.append(f"Agent {aid} lacks registered adapter instance")

        return issues


# Singleton instance
registry = AgentRegistry()


def get_agent_registry() -> AgentRegistry:
    """Returns the authoritative singleton AgentRegistry instance."""
    return registry
