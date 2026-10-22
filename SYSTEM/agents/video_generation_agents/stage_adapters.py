"""Backward-compatibility facade for Video Generation Agents.

All implementations have been modularized into their dedicated agent directories:
SYSTEM/agents/video_generation_agents/<agent_name>/agent.py
"""
from __future__ import annotations

from .main_orchestrator.agent import MainOrchestratorAgent, MainOrchestratorAdapter
from .audio_input.agent import AudioInputAgent, AudioInputAdapter
from .audio_analyzer.agent import AudioAnalyzerAgent, AudioAnalyzerAdapter
from .scene_segmentation.agent import SceneSegmentationAgent, SceneSegmentationAdapter
from .visual_planning.agent import VisualPlanningAgent, VisualPlanningAdapter
from .asset_collection.agent import AssetCollectionAgent, AssetCollectionAdapter
from .motion_planning.agent import MotionPlanningAgent, MotionPlanningAdapter
from .motion_template_selection.agent import MotionTemplateSelectionAgent, MotionTemplateSelectionAdapter
from .motion_animation.agent import MotionAnimationAgent, MotionAnimationAdapter
from .motion_timeline_validation.agent import MotionValidationAgent, MotionValidationAdapter
from .timeline_build.agent import TimelineBuildAgent, TimelineBuildAdapter
from .timeline_approval.agent import TimelineApprovalAgent, TimelineApprovalAdapter
from .render_video.agent import RenderVideoAgent, RenderVideoAdapter
from .final_qc.agent import FinalQcAgent, FinalQcAdapter
from .final_video_delivery.agent import FinalVideoDeliveryAgent, FinalVideoDeliveryAdapter

__all__ = [
    "MainOrchestratorAgent", "MainOrchestratorAdapter",
    "AudioInputAgent", "AudioInputAdapter",
    "AudioAnalyzerAgent", "AudioAnalyzerAdapter",
    "SceneSegmentationAgent", "SceneSegmentationAdapter",
    "VisualPlanningAgent", "VisualPlanningAdapter",
    "AssetCollectionAgent", "AssetCollectionAdapter",
    "MotionPlanningAgent", "MotionPlanningAdapter",
    "MotionTemplateSelectionAgent", "MotionTemplateSelectionAdapter",
    "MotionAnimationAgent", "MotionAnimationAdapter",
    "MotionValidationAgent", "MotionValidationAdapter",
    "TimelineBuildAgent", "TimelineBuildAdapter",
    "TimelineApprovalAgent", "TimelineApprovalAdapter",
    "RenderVideoAgent", "RenderVideoAdapter",
    "FinalQcAgent", "FinalQcAdapter",
    "FinalVideoDeliveryAgent", "FinalVideoDeliveryAdapter",
]
