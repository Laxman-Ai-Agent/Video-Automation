"""The 15 video generation agents (the orchestrator and one per pipeline stage) as Agent Registry entries.

Video-owned. The Agent System's registry never imports this module: the video project provides these entries through the
integration interface (SYSTEM/core/integrations.py, capability 'agent_entries'; see VIDEO_ENGINE/agent_system_integration.py).
"""
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

# Backward compatibility aliases
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


def video_agent_entries() -> list[tuple[AgentMetadata, Type[BaseAgent]]]:
    return [
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
    ]
