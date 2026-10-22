"""FastAPI routes for the Central Skills Registry, static audit, and decision trail."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from SYSTEM.registries import skill_registry

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillDecisionRequest(BaseModel):
    objective: str
    agent_id: str
    domain: str | None = None
    tags: list[str] = Field(default_factory=list)
    allow_adapt: bool = True


class SkillAuditRequest(BaseModel):
    content: str
    filename: str = ""


class SkillPromoteRequest(BaseModel):
    reviewer: str
    evidence: str


class SkillStageCandidateRequest(BaseModel):
    filename: str
    raw_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillClassifyRequest(BaseModel):
    query: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)


class SkillDiscoverRequest(BaseModel):
    query: str
    description: str = ""
    agent_id: str | None = None
    preferred_category: str | None = None
    allow_remote: bool = True


class SkillEvaluateRequest(BaseModel):
    candidate: dict[str, Any]
    target_category: str
    target_capability: str = ""
    code_files: dict[str, str] = Field(default_factory=dict)


class SkillInstallRequest(BaseModel):
    candidate: dict[str, Any]
    target_category: str | None = None
    force_update: bool = False


class AgentResolveRequest(BaseModel):
    agent_id: str
    capability_or_skill_id: str
    category_hint: str | None = None


@router.get("/categories")
def list_categories() -> list[dict[str, Any]]:
    """Lists all 25 video-editing skill categories with subcategories and technology stacks."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    return [c.to_dict() for c in manager.list_categories()]


@router.get("/categories/{category_id}")
def get_category_details(category_id: str) -> dict[str, Any]:
    """Retrieves full metadata and subcategories for a specific category."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    cat = manager.get_category(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail=f"Category '{category_id}' not found")
    return cat.to_dict()


@router.post("/classify")
def classify_capability(body: SkillClassifyRequest) -> dict[str, Any]:
    """Intelligently classifies a capability requirement into the 25-category taxonomy."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    return manager.classify_capability(body.query, description=body.description, keywords=body.keywords).to_dict()


@router.post("/discover")
def discover_skill(body: SkillDiscoverRequest) -> dict[str, Any]:
    """Executes multi-tiered skill discovery across local, central, curated, and remote sources."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    res = manager.discover_skill(
        capability_query=body.query,
        description=body.description,
        agent_id=body.agent_id,
        preferred_category=body.preferred_category,
        allow_remote=body.allow_remote,
    )
    return res.to_dict()


@router.post("/evaluate")
def evaluate_candidate(body: SkillEvaluateRequest) -> dict[str, Any]:
    """Evaluates an external or candidate skill against multi-criteria requirements."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    rep = manager.evaluate_candidate(
        candidate_data=body.candidate,
        target_category=body.target_category,
        target_capability=body.target_capability,
        code_files=body.code_files,
    )
    return rep.to_dict()


@router.post("/install")
def install_skill(body: SkillInstallRequest) -> dict[str, Any]:
    """Installs, validates, tests, and registers a candidate skill into the category library."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    res = manager.install_skill(
        candidate=body.candidate,
        target_category=body.target_category,
        force_update=body.force_update,
    )
    return res.to_dict()


@router.get("/library/installed")
def list_installed_category_skills(category_id: str | None = None) -> list[dict[str, Any]]:
    """Lists verified skills installed in the category library."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    return [s.to_dict() for s in manager.list_installed_skills(category_id=category_id)]


@router.get("/library/report")
def get_skill_library_report() -> dict[str, Any]:
    """Returns library health, category distribution, and installed skill counts."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    return manager.generate_library_report()


@router.post("/resolve-agent")
def resolve_agent_skill(body: AgentResolveRequest) -> dict[str, Any]:
    """Resolves an authorized skill for a specific agent across local, category, and central tiers."""
    from SYSTEM.skills import get_skill_library_manager
    manager = get_skill_library_manager()
    res = manager.resolve_skill_for_agent(
        agent_id=body.agent_id,
        capability_or_skill_id=body.capability_or_skill_id,
        category_hint=body.category_hint,
    )
    return res.to_dict()


@router.get("")
def list_skills(
    query: str = "",
    agent_id: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    status: str = "approved",
) -> list[dict[str, Any]]:
    """Lists registered skills matching query, domain, tag, agent, and status filters."""
    skills = skill_registry.registry.search_skills(
        query=query,
        agent_id=agent_id,
        domain=domain,
        tag=tag,
        status=status,  # type: ignore[arg-type]
    )
    return [s.to_dict() for s in skills]


@router.get("/{skill_id}")
def get_skill(skill_id: str, version: str | None = None) -> dict[str, Any]:
    """Retrieves metadata and verified instructions for a specific skill."""
    try:
        record, content = skill_registry.registry.get_skill(
            skill_id,
            version=version,
            load_content=True,
        )
        data = record.to_dict()
        data["content"] = content
        return data
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    except skill_registry.SkillSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except skill_registry.SkillVerificationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decision")
def evaluate_skill_decision(body: SkillDecisionRequest) -> dict[str, Any]:
    """Evaluates the Reuse / Adapt / Create decision trail for an agent's objective."""
    return skill_registry.registry.resolve_skill_decision(
        objective=body.objective,
        agent_id=body.agent_id,
        domain=body.domain,
        tags=body.tags,
        allow_adapt=body.allow_adapt,
    )


@router.post("/audit")
def audit_skill(body: SkillAuditRequest) -> dict[str, Any]:
    """Performs static security audit on skill markdown/code for prompt injection and unsafe patterns."""
    return skill_registry.audit_skill_content(body.content, filename=body.filename)


@router.post("/{skill_id}/promote")
def promote_skill(skill_id: str, body: SkillPromoteRequest) -> dict[str, Any]:
    """Promotes a reviewed skill to 'approved' status with explicit reviewer evidence."""
    try:
        updated = skill_registry.registry.transition_status(
            skill_id=skill_id,
            new_status="approved",
            reviewer=body.reviewer,
            evidence=body.evidence,
        )
        return updated.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    except (skill_registry.InvalidSkillTransitionError, skill_registry.SkillSecurityError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stage-candidate")
def stage_external_candidate(body: SkillStageCandidateRequest) -> dict[str, Any]:
    """Safely stages an external candidate file in quarantine and performs static audit."""
    try:
        return skill_registry.registry.stage_external_candidate(
            filename=body.filename,
            raw_content=body.raw_content,
            metadata=body.metadata,
        )
    except skill_registry.SkillSecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))
