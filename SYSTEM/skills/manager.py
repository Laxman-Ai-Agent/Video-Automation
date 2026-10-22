"""Authoritative Central Skill Library Manager.

Unified facade providing:
1. Category-based taxonomy management and semantic capability classification.
2. Multi-tiered intelligent skill discovery across local, central, curated, and remote sources.
3. Multi-criteria evidence-based candidate evaluation.
4. Controlled, confined, and validated installation with load testing and rollback.
5. Role-based agent access control and capability resolution.
6. Persistent caching and traceable reporting.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    SkillEvaluationReport,
    get_candidate_evaluator,
)
from .installer import (
    InstallationResult,
    InstalledSkillRecord,
    SkillLibraryInstaller,
    get_skill_library_installer,
)
from .taxonomy import (
    CategoryClassificationResult,
    CategoryTaxonomy,
    VideoEditingCategory,
    get_category_taxonomy,
)

logger = logging.getLogger("skill_library.manager")

CACHE_FILE = Path(__file__).parent / "cache.json"


class SkillLibraryManager:
    """The central manager orchestrating the intelligent video editing skill library."""

    def __init__(self) -> None:
        self._taxonomy: CategoryTaxonomy = get_category_taxonomy()
        self._evaluator: CandidateEvaluator = get_candidate_evaluator()
        self._discovery: SkillLibraryDiscovery = get_skill_library_discovery()
        self._installer: SkillLibraryInstaller = get_skill_library_installer()
        self._access_controller: AgentSkillAccessController = get_agent_skill_access_controller()
        self._cache: dict[str, Any] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if CACHE_FILE.exists():
            try:
                self._cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                self._cache = {}

    def _save_cache(self) -> None:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            CACHE_FILE.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    # -----------------------------------------------------------------------
    # 1. Category Taxonomy Management
    # -----------------------------------------------------------------------

    def list_categories(self) -> list[VideoEditingCategory]:
        """Lists all registered video-editing categories."""
        return self._taxonomy.list_categories()

    def get_category(self, category_id: str) -> VideoEditingCategory | None:
        """Retrieves category details by ID."""
        return self._taxonomy.get_category(category_id)

    def register_category(self, category_data: VideoEditingCategory | dict[str, Any]) -> VideoEditingCategory:
        """Registers a new or extended category dynamically."""
        return self._taxonomy.register_category(category_data)

    def classify_capability(
        self,
        capability_query: str,
        description: str = "",
        keywords: list[str] | None = None,
    ) -> CategoryClassificationResult:
        """Classifies a natural language or capability string into the 25-category taxonomy."""
        return self._taxonomy.classify_capability(capability_query, description=description, keywords=keywords)

    # -----------------------------------------------------------------------
    # 2. Intelligent Discovery & Candidate Evaluation
    # -----------------------------------------------------------------------

    def discover_skill(
        self,
        capability_query: str,
        description: str = "",
        agent_id: str | None = None,
        preferred_category: str | None = None,
        allow_remote: bool = True,
        use_cache: bool = True,
        offline_fixtures: list[dict[str, Any]] | None = None,
    ) -> DiscoveryResult:
        """Discovers, ranks, and selects the best compatible skill across all tiers."""
        cache_key = f"discover:{capability_query}:{agent_id or 'none'}:{preferred_category or 'none'}"
        if use_cache and cache_key in self._cache and not offline_fixtures:
            cached_data = self._cache[cache_key]
            # Fast return cached result if recent
            return DiscoveryResult(
                status=cached_data["status"],
                selected_candidate=(
                    DiscoveredSkillCandidate(**cached_data["selected_candidate"])
                    if cached_data.get("selected_candidate")
                    else None
                ),
                classification=CategoryClassificationResult(**cached_data["classification"]),
                candidates_evaluated=[
                    DiscoveredSkillCandidate(**c) for c in cached_data.get("candidates_evaluated", [])
                ],
                resolution_path=cached_data.get("resolution_path", []),
                actionable_message=cached_data.get("actionable_message", ""),
            )

        result = self._discovery.discover_skill(
            capability_query=capability_query,
            description=description,
            agent_id=agent_id,
            preferred_category=preferred_category,
            allow_remote=allow_remote,
            offline_fixtures=offline_fixtures,
        )

        if use_cache and not offline_fixtures:
            self._cache[cache_key] = result.to_dict()
            self._save_cache()

        return result

    def evaluate_candidate(
        self,
        candidate_data: dict[str, Any],
        target_category: str,
        target_capability: str = "",
        code_files: dict[str, str] | None = None,
    ) -> SkillEvaluationReport:
        """Evaluates an external or staged candidate skill against multi-criteria requirements."""
        return self._evaluator.evaluate_candidate(
            candidate_data=candidate_data,
            target_category=target_category,
            target_capability=target_capability,
            code_files=code_files,
        )

    # -----------------------------------------------------------------------
    # 3. Installation, Validation, and Registration
    # -----------------------------------------------------------------------

    def install_skill(
        self,
        candidate: DiscoveredSkillCandidate | dict[str, Any],
        target_category: str | None = None,
        force_update: bool = False,
    ) -> InstallationResult:
        """Installs and validates a candidate into the category library."""
        res = self._installer.install_skill(
            candidate=candidate,
            target_category=target_category,
            force_update=force_update,
        )
        return res

    def list_installed_skills(self, category_id: str | None = None) -> list[InstalledSkillRecord]:
        """Lists verified installed skills."""
        return self._installer.list_installed_skills(category_id=category_id)

    def uninstall_skill(self, skill_id: str) -> bool:
        """Safely removes an installed skill."""
        return self._installer.uninstall_skill(skill_id)

    # -----------------------------------------------------------------------
    # 4. Agent Integration & Access Control
    # -----------------------------------------------------------------------

    def resolve_skill_for_agent(
        self,
        agent_id: str,
        capability_or_skill_id: str,
        category_hint: str | None = None,
    ) -> AgentSkillResolution:
        """Resolves a skill for an agent respecting role-based access control."""
        return self._access_controller.resolve_skill_for_agent(
            agent_id=agent_id,
            capability_or_skill_id=capability_or_skill_id,
            category_hint=category_hint,
        )

    def is_agent_authorized(self, agent_id: str, category_id: str) -> bool:
        """Checks if an agent is authorized for a category."""
        return self._access_controller.is_agent_authorized_for_category(agent_id, category_id)

    # -----------------------------------------------------------------------
    # 5. Reporting & Health
    # -----------------------------------------------------------------------

    def generate_library_report(self) -> dict[str, Any]:
        """Generates comprehensive status and health report for the Skill Library."""
        categories = self._taxonomy.list_categories()
        installed = self._installer.list_installed_skills()

        cat_distribution: dict[str, int] = {c.category_id: 0 for c in categories}
        for s in installed:
            if s.category_id in cat_distribution:
                cat_distribution[s.category_id] += 1

        return {
            "status": "healthy",
            "total_categories": len(categories),
            "total_installed_skills": len(installed),
            "category_distribution": cat_distribution,
            "installed_skills": [s.to_dict() for s in installed],
            "cache_entries": len(self._cache),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Authoritative singleton
_manager_singleton: SkillLibraryManager | None = None


def get_skill_library_manager() -> SkillLibraryManager:
    """Returns the authoritative SkillLibraryManager singleton instance."""
    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = SkillLibraryManager()
    return _manager_singleton
