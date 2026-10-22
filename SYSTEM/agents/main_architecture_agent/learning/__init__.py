"""Learning package for Main Architecture Agent."""
from __future__ import annotations

from .experience_collector import ExperienceCollector, ExperienceRecord, experience_collector
from .improvement_proposals import ImprovementProposal, ImprovementProposalEngine, proposal_engine
from .reflection_engine import LessonItem, ReflectionEngine, ReflectionReport, reflection_engine
from .learning_scheduler import LearningScheduler, learning_scheduler
from .strategy_manager import StrategyManager, strategy_manager

__all__ = [
    "ExperienceCollector",
    "ExperienceRecord",
    "experience_collector",
    "LessonItem",
    "ReflectionEngine",
    "ReflectionReport",
    "reflection_engine",
    "ImprovementProposal",
    "ImprovementProposalEngine",
    "proposal_engine",
    "StrategyManager",
    "strategy_manager",
    "LearningScheduler",
    "learning_scheduler",
]
