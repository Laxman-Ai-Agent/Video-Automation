"""Authoritative Agent Registry for all 13 logical video agents and 7 system agents in the Dark World Video Generation Agent system."""
from __future__ import annotations

from typing import Type

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentCategory, AgentMetadata, AgentStatus
from SYSTEM.agents.video_generation_agents.main_orchestrator.agent import MainOrchestratorAgent
from SYSTEM.agents.video_generation_agents.audio_input.agent import AudioInputAgent
from SYSTEM.agents.video_generation_agents.audio_analyzer.agent import AudioAnalyzerAgent
from SYSTEM.agents.video_generation_agents.scene_segmentation.agent import SceneSegmentationAgent
from SYSTEM.agents.video_generation_agents.visual_planning.agent import VisualPlanningAgent
from SYSTEM.agents.video_generation_agents.asset_collection.agent import AssetCollectionAgent
from SYSTEM.agents.video_generation_agents.motion_planning.agent import MotionPlanningAgent
from SYSTEM.agents.video_generation_agents.motion_template_selection.agent import MotionTemplateSelectionAgent
from SYSTEM.agents.video_generation_agents.motion_animation.agent import MotionAnimationAgent
from SYSTEM.agents.video_generation_agents.motion_timeline_validation.agent import MotionValidationAgent
from SYSTEM.agents.video_generation_agents.timeline_build.agent import TimelineBuildAgent
from SYSTEM.agents.video_generation_agents.timeline_approval.agent import TimelineApprovalAgent
from SYSTEM.agents.video_generation_agents.render_video.agent import RenderVideoAgent
from SYSTEM.agents.video_generation_agents.final_qc.agent import FinalQcAgent
from SYSTEM.agents.video_generation_agents.final_video_delivery.agent import FinalVideoDeliveryAgent

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
MainOrchestratorAdapter = MainOrchestratorAgent
AudioInputAdapter = AudioInputAgent
AudioAnalyzerAdapter = AudioAnalyzerAgent
SceneSegmentationAdapter = SceneSegmentationAgent
VisualPlanningAdapter = VisualPlanningAgent
AssetCollectionAdapter = AssetCollectionAgent
MotionPlanningAdapter = MotionPlanningAgent
MotionTemplateSelectionAdapter = MotionTemplateSelectionAgent
MotionAnimationAdapter = MotionAnimationAgent
MotionValidationAdapter = MotionValidationAgent
TimelineBuildAdapter = TimelineBuildAgent
TimelineApprovalAdapter = TimelineApprovalAgent
RenderVideoAdapter = RenderVideoAgent
FinalQcAdapter = FinalQcAgent
FinalVideoDeliveryAdapter = FinalVideoDeliveryAgent


class AgentRegistry:
    """Authoritative registry mapping stable Agent IDs to metadata and allowlisted adapters."""

    def __init__(self) -> None:
        self._metadata: dict[str, AgentMetadata] = {}
        self._adapters: dict[str, BaseAgent] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        entries: list[tuple[AgentMetadata, Type[BaseAgent]]] = [
            (
                AgentMetadata(
                    agent_id="main_orchestrator",
                    name="Main Orchestrator Agent",
                    version="1.0.0",
                    category=AgentCategory.ORCHESTRATOR,
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Coordinates pipeline execution flow, auto-advancement rules, and error recovery.",
                    capabilities=["orchestration", "auto-advance", "safe-stop-guard"],
                    stage_id="pipeline",
                    allowed_tools=["job_queue", "step_graph", "pipeline_view"],
                    owner="agent-system",
                ),
                MainOrchestratorAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="audio_input",
                    name="Audio Input Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Ingests user narration audio, downsamples to 16kHz mono, and extracts duration parameters.",
                    capabilities=["audio-ingest", "sample-rate-conversion", "ffprobe-metadata"],
                    stage_id="audio",
                    allowed_tools=["ffmpeg", "ffprobe", "store"],
                    owner="agent-system",
                ),
                AudioInputAgent,
            ),
            (
                AgentMetadata(
                    agent_id="audio_analyzer",
                    name="Audio Analyzer Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Transcribes audio with faster-whisper, performs bilingual phonetics review, and detects pauses.",
                    capabilities=["speech-to-text", "silence-detection", "phonetic-review"],
                    stage_id="analyzer",
                    allowed_tools=["faster-whisper", "silencedetect", "llm_client"],
                    skills=["audio.bilingual_preservation"],
                    is_frozen=False,
                    owner="agent-system",
                ),
                AudioAnalyzerAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="scene_segmentation",
                    name="Scene Segmentation Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Partitions narration transcript into semantic scenes obeying strict duration and word-boundary rules.",
                    capabilities=["semantic-chunking", "boundary-snapping", "duration-enforcement"],
                    stage_id="segmentation",
                    allowed_tools=["llm_client", "regex_validator"],
                    is_frozen=False,
                    owner="agent-system",
                ),
                SceneSegmentationAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="visual_planning",
                    name="Visual Planning Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Generates scene visual concepts, bilingual Telugu-to-English translations, and image prompt descriptors.",
                    capabilities=["visual-concept-generation", "translation", "image-prompt-generation"],
                    stage_id="planning",
                    allowed_tools=["llm_client", "pydantic_schemas"],
                    skills=[
                        "audio.bilingual_preservation",
                        "visual.scene_planning",
                        "visual.cinematic_composition",
                        "visual.narrative_semantic_mapping",
                        "visual.word_semantic_animation",
                        "visual.scene_variety_pacing",
                    ],
                    owner="agent-system",
                ),
                VisualPlanningAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="asset_collection",
                    name="Asset Collection Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Plans which scenes need real photos or video clips, searches licensed sources, validates and records provenance, rights and scene assignment of every collected asset.",
                    capabilities=["asset-requirement-planning", "licensed-source-search", "clip-preparation", "rights-and-provenance-tracking", "duplicate-detection"],
                    stage_id="assets",
                    allowed_tools=["stock_providers", "ffmpeg", "llm_gateway", "asset_manifest"],
                    owner="agent-system",
                ),
                AssetCollectionAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="motion_planning",
                    name="Motion Planning Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Plans kinetic typography rhythm, safe area bounding boxes, and solves layout collisions.",
                    capabilities=["typography-planning", "collision-solving", "safe-area-enforcement"],
                    stage_id="motion_plan",
                    allowed_tools=["remotion_planner", "heuristic_solver"],
                    skills=[
                        "motion.kinetic_typography",
                        "motion.remotion_spring_curves",
                        "validation.layout_safe_zones",
                    ],
                    owner="agent-system",
                ),
                MotionPlanningAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="motion_template_selection",
                    name="Motion Template Selection Agent",
                    version="1.0.0",
                    status=AgentStatus.DEPRECATED,
                    purpose="Removed from active workflow; preserved in 14-agent target architecture for future reconsideration only.",
                    capabilities=["template-matching", "routing-decision"],
                    stage_id="motion_template",
                    allowed_tools=["template_registry"],
                    owner="agent-system",
                ),
                MotionTemplateSelectionAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="motion_animation",
                    name="Motion Animation Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Generates standalone executable React/TSX animation source code and stages Remotion components.",
                    capabilities=["react-tsx-codegen", "ast-preset-scanning", "typescript-typechecking"],
                    stage_id="motion_gen",
                    allowed_tools=["ast_builder", "tsc", "remotion_stager"],
                    skills=[
                        "motion.kinetic_typography",
                        "motion.remotion_spring_curves",
                    ],
                    owner="agent-system",
                ),
                MotionAnimationAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="motion_timeline_validation",
                    name="Motion & Timeline Validation Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Applies 12 technical validation rules across the composition, checks resource library integrity, and renders preview stills.",
                    capabilities=["rule-checking", "resource-verification", "preview-generation"],
                    stage_id="motion_validation",
                    allowed_tools=["rule_engine", "resource_library", "preview_renderer"],
                    skills=["validation.layout_safe_zones"],
                    owner="agent-system",
                ),
                MotionValidationAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="timeline_build",
                    name="Timeline Build Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Compiles multi-track composition layers into a frame-accurate timeline matching audio duration.",
                    capabilities=["timeline-assembly", "frame-accounting", "audio-sync"],
                    stage_id="timeline",
                    allowed_tools=["timeline_compiler"],
                    owner="agent-system",
                ),
                TimelineBuildAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="timeline_approval",
                    name="Timeline Approval Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Mandatory approval gate, decided by an LLM review. Enforces cryptographic fingerprint lock before video rendering.",
                    capabilities=["fingerprint-verification", "human-decision-gating", "invalidation-check"],
                    stage_id="approval",
                    allowed_tools=["sha256_verifier", "store"],
                    owner="agent-system",
                ),
                TimelineApprovalAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="render_video",
                    name="Render Video Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Executes Remotion render in headless Chrome using dynamic ports and captures render telemetry.",
                    capabilities=["remotion-render", "headless-chrome", "stream-validation"],
                    stage_id="render",
                    allowed_tools=["remotion_renderer", "ffprobe"],
                    owner="agent-system",
                ),
                RenderVideoAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="final_qc",
                    name="Final QC Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Dual-gate quality control: automated media probe (black frames, freeze, clipping) + a mandatory decision by the Final QC LLM review.",
                    capabilities=["black-frame-detection", "freeze-frame-detection", "playback-confirmation"],
                    stage_id="qc",
                    allowed_tools=["ffprobe_qc", "opencv_sampler"],
                    owner="agent-system",
                ),
                FinalQcAdapter,
            ),
            (
                AgentMetadata(
                    agent_id="final_video_delivery",
                    name="Final Video Delivery Agent",
                    version="1.0.0",
                    status=AgentStatus.IMPLEMENTED,
                    purpose="Verifies end-to-end provenance, SHA-256 integrity match, and serves final video file delivery.",
                    capabilities=["provenance-audit", "sha256-matching", "file-delivery"],
                    stage_id="final",
                    allowed_tools=["hash_verifier", "file_streamer"],
                    owner="agent-system",
                ),
                FinalVideoDeliveryAgent,
            ),
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
                        "frozen-file-protection",
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

    def get(self, agent_id: str) -> AgentMetadata | None:
        return self._metadata.get(agent_id)

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        return self._adapters.get(agent_id)

    get_adapter = get_agent  # Backward compatibility alias

    def list_agents(self, include_system: bool = False) -> list[AgentMetadata]:
        """Returns registered agent metadata. Defaults to returning the 15 core video agents (the orchestrator and one agent per stage)."""
        if include_system:
            return list(self._metadata.values())
        return self.list_video_agents()

    def list_all_agents(self) -> list[AgentMetadata]:
        """Returns all registered agents including video engine agents and system agents."""
        return list(self._metadata.values())

    def list_video_agents(self) -> list[AgentMetadata]:
        """Returns all 15 video generation agent metadata records (the orchestrator and one agent per stage)."""
        return [
            m for m in self._metadata.values()
            if m.category in (AgentCategory.VIDEO_ENGINE_AGENT, AgentCategory.ORCHESTRATOR)
            and m.agent_id != "main_architecture_agent"
        ]

    def list_system_agents(self) -> list[AgentMetadata]:
        """Returns all system agent metadata records (Main Architecture Agent and system subagents)."""
        return [
            m for m in self._metadata.values()
            if m.category == AgentCategory.SYSTEM_SUBAGENT or m.agent_id == "main_architecture_agent"
        ]

    def validate_registry(self) -> list[str]:
        """Validates all registered agents for completeness, uniqueness, and consistency."""
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
