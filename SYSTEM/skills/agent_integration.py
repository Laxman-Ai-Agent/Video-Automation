"""Integration of Category-Based Video Editing Skill Library with Multi-Agent System.

Enforces:
1. Agent-specific capability and category access control (prevents assigning every skill to every agent).
2. Multi-tier resolution order: Local agent-private -> Category library -> Central catalog.
3. Preservation of existing per-agent skill directories, agent memory, and registry contracts.
4. Seamless invocation from video-generation agents (motion_animation, visual_planning, etc.).
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from SYSTEM.registries.agent_registry import registry as agent_registry
from SYSTEM.registries.skill_registry import SkillRecord, SkillSecurityError, get_skill_registry
from .installer import InstalledSkillRecord, get_skill_library_installer
from .taxonomy import CategoryTaxonomy, get_category_taxonomy

logger = logging.getLogger("skill_library.agent_integration")

# ---------------------------------------------------------------------------
# Canonical Agent Authorization Matrix across the 25 Video-Editing Categories
# ---------------------------------------------------------------------------

AGENT_CATEGORY_PERMISSIONS: dict[str, set[str]] = {
    # Video Generation Agents
    "visual_planning": {
        "graphics", "charts", "maps", "infographics", "2d_graphics", "3d_graphics",
        "science_visuals", "documentary_graphics", "ui_hud", "layouts", "image_animation",
        "backgrounds", "templates", "typography",
    },
    "motion_planning": {
        "motion_animation", "transitions", "typography", "layouts", "time_effects",
    },
    "motion_template_selection": {
        "templates", "graphics", "motion_animation", "2d_graphics", "backgrounds",
    },
    "asset_collection": {
        "documentary_graphics", "image_animation", "backgrounds",
    },
    "motion_animation": {
        "motion_animation", "transitions", "typography", "vfx", "graphics", "charts",
        "infographics", "2d_graphics", "3d_graphics", "ui_hud", "image_animation",
        "audio_visualization", "backgrounds", "compositing", "templates", "captions",
    },
    "motion_validation": {
        "layouts", "motion_animation", "render_qa", "templates",
    },
    "timeline_build": {
        "transitions", "compositing", "video_editing", "time_effects", "layouts",
        "captions", "typography", "vfx", "backgrounds", "graphics", "charts", "maps",
    },
    "render_video": {
        "render_qa", "compositing", "color_grading", "time_effects",
    },
    "final_qc": {
        "render_qa", "color_grading", "audio_editing", "captions",
    },
    "audio_analyzer": {
        "audio_editing", "audio_visualization", "captions", "typography",
    },
    "audio_input": {
        "audio_editing",
    },
    "scene_segmentation": {
        "video_editing",
    },
    "final_video_delivery": {
        "render_qa",
    },
    "main_orchestrator": {
        # Orchestrator can coordinate all categories
        "*",
    },
    # System Agents have system-wide authority
    "capability_finder": {"*"},
    "skill_factory": {"*"},
    "architecture_validator": {"*"},
    "verification_and_test": {"*"},
    "security_policy": {"*"},
    "autonomous_execution": {"*"},
    "main_architecture_agent": {"*"},
}


@dataclass
class AgentSkillResolution:
    """Result of an agent resolving and obtaining access to a skill."""
    status: Literal["resolved", "unauthorized", "not_found"]
    agent_id: str
    skill_id: str
    scope: Literal["agent_local", "category_library", "central_catalog", "none"]
    category_id: str | None
    version: str
    entrypoint: str
    content: str
    code_files: dict[str, str] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentSkillAccessController:
    """Manages role-based skill discovery and execution permissions for the 20 canonical agents."""

    def __init__(self) -> None:
        self._taxonomy: CategoryTaxonomy = get_category_taxonomy()
        self._installer = get_skill_library_installer()
        self._skill_registry = get_skill_registry()

    def is_agent_authorized_for_category(self, agent_id: str, category_id: str) -> bool:
        """Checks if a given agent is authorized to access skills in the specified category."""
        allowed_cats = AGENT_CATEGORY_PERMISSIONS.get(agent_id, set())
        if "*" in allowed_cats:
            return True
        return category_id.lower().strip() in allowed_cats

    def resolve_skill_for_agent(
        self,
        agent_id: str,
        capability_or_skill_id: str,
        category_hint: str | None = None,
    ) -> AgentSkillResolution:
        """Resolves a skill for an agent using the strict 3-level hierarchy:
        Level 1: Agent private local skill (SYSTEM/agents/.../<agent_id>/skills/)
        Level 2: Category-managed library (SYSTEM/skills/library/<category>/<skill_id>/)
        Level 3: Central catalog (SYSTEM/skills/catalog.json)
        """
        self._skill_registry.initialize()
        target_id = capability_or_skill_id.lower().strip()

        # -------------------------------------------------------------
        # Level 1: Agent Private Local Skill
        # -------------------------------------------------------------
        local_res = self._skill_registry._resolve_local_agent_skill(agent_id, target_id, load_content=True)
        if local_res:
            rec, content = local_res
            return AgentSkillResolution(
                status="resolved",
                agent_id=agent_id,
                skill_id=rec.skill_id,
                scope="agent_local",
                category_id=rec.domain,
                version=rec.version,
                entrypoint=rec.entrypoint,
                content=content,
                code_files={Path(rec.entrypoint).name: content},
                message=f"Resolved agent-private skill '{rec.skill_id}' for agent '{agent_id}'.",
            )

        # -------------------------------------------------------------
        # Level 2: Category-Managed Skill Library
        # -------------------------------------------------------------
        # Check installed skills
        installed_match: InstalledSkillRecord | None = None
        for inst in self._installer.list_installed_skills():
            if inst.skill_id.lower() == target_id or target_id in [c.lower() for c in inst.capabilities]:
                installed_match = inst
                break

        if installed_match:
            cat_id = installed_match.category_id
            # Authorization check
            if not self.is_agent_authorized_for_category(agent_id, cat_id):
                return AgentSkillResolution(
                    status="unauthorized",
                    agent_id=agent_id,
                    skill_id=installed_match.skill_id,
                    scope="category_library",
                    category_id=cat_id,
                    version=installed_match.version,
                    entrypoint=installed_match.entrypoint,
                    content="",
                    message=f"Agent '{agent_id}' is not authorized to use category '{cat_id}' skills.",
                )

            # Read skill files
            content = ""
            code_files: dict[str, str] = {}
            skill_dir = Path(__file__).parent / "library" / cat_id / installed_match.skill_id
            if skill_dir.exists():
                for f in skill_dir.glob("*"):
                    if f.is_file():
                        try:
                            code_files[f.name] = f.read_text(encoding="utf-8")
                        except Exception:
                            pass
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text(encoding="utf-8")

            return AgentSkillResolution(
                status="resolved",
                agent_id=agent_id,
                skill_id=installed_match.skill_id,
                scope="category_library",
                category_id=cat_id,
                version=installed_match.version,
                entrypoint=installed_match.entrypoint,
                content=content,
                code_files=code_files,
                message=f"Resolved category-managed skill '{installed_match.skill_id}' in category '{cat_id}'.",
            )

        # -------------------------------------------------------------
        # Level 3: Central Catalog Fallback
        # -------------------------------------------------------------
        try:
            rec, content = self._skill_registry.get_agent_skill(agent_id, target_id, load_content=True)
            return AgentSkillResolution(
                status="resolved",
                agent_id=agent_id,
                skill_id=rec.skill_id,
                scope="central_catalog",
                category_id=rec.domain,
                version=rec.version,
                entrypoint=rec.entrypoint,
                content=content,
                code_files={Path(rec.entrypoint).name: content} if rec.entrypoint else {},
                message=f"Resolved central shared skill '{rec.skill_id}' for agent '{agent_id}'.",
            )
        except SkillSecurityError as e:
            return AgentSkillResolution(
                status="unauthorized",
                agent_id=agent_id,
                skill_id=target_id,
                scope="central_catalog",
                category_id=None,
                version="",
                entrypoint="",
                content="",
                message=str(e),
            )
        except KeyError:
            pass

        return AgentSkillResolution(
            status="not_found",
            agent_id=agent_id,
            skill_id=target_id,
            scope="none",
            category_id=category_hint,
            version="",
            entrypoint="",
            content="",
            message=f"Skill '{target_id}' not found in agent-local, category library, or central catalog.",
        )


# Singleton instance
_access_controller_singleton: AgentSkillAccessController | None = None


def get_agent_skill_access_controller() -> AgentSkillAccessController:
    """Returns the singleton AgentSkillAccessController instance."""
    global _access_controller_singleton
    if _access_controller_singleton is None:
        _access_controller_singleton = AgentSkillAccessController()
    return _access_controller_singleton
