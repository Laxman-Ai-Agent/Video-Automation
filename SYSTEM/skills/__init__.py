"""Intelligent, Category-Based Video Editing Skill Library.

Authoritative package managing 25 video editing categories, multi-tiered discovery,
multi-criteria candidate evaluation, controlled validation & installation, and agent role-based access.
"""
from __future__ import annotations

from .agent_integration import (
    AgentSkillAccessController,
    AgentSkillResolution,
    get_agent_skill_access_controller,
)
from .discovery import (
    DiscoveredSkillCandidate,
    DiscoveryResult,
    SkillLibraryDiscovery,
    get_skill_library_discovery,
)
from .evaluator import (
    CandidateEvaluator,
    CriterionScore,
    EvaluationVerdict,
    SkillEvaluationReport,
    get_candidate_evaluator,
)
from .installer import (
    InstallationResult,
    InstalledSkillRecord,
    SkillLibraryInstaller,
    get_skill_library_installer,
)
from .manager import (
    SkillLibraryManager,
    get_skill_library_manager,
)
from .taxonomy import (
    CategoryClassificationResult,
    CategoryTaxonomy,
    VideoEditingCategory,
    get_category_taxonomy,
)

__all__ = [
    "SkillLibraryManager",
    "get_skill_library_manager",
    "CategoryTaxonomy",
    "get_category_taxonomy",
    "VideoEditingCategory",
    "CategoryClassificationResult",
    "CandidateEvaluator",
    "get_candidate_evaluator",
    "SkillEvaluationReport",
    "CriterionScore",
    "EvaluationVerdict",
    "SkillLibraryDiscovery",
    "get_skill_library_discovery",
    "DiscoveredSkillCandidate",
    "DiscoveryResult",
    "SkillLibraryInstaller",
    "get_skill_library_installer",
    "InstalledSkillRecord",
    "InstallationResult",
    "AgentSkillAccessController",
    "AgentSkillResolution",
]

import sys
# Backwards compatibility: ensure any legacy imports of SYSTEM.skill_library resolve to SYSTEM.skills
sys.modules.setdefault("SYSTEM.skill_library", sys.modules[__name__])

