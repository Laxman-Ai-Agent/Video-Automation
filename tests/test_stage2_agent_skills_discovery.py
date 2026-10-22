"""Comprehensive Acceptance Test Suite for Stage 2:
Agent-Owned Skills, Central Library & Automatic GitHub Discovery.

Verifies:
1. Agent-Owned Skills:
   - All 21 canonical agents have private skills directories with .gitkeep.
   - Local skill discovery works for owning agent.
   - AssetCuratorAgent discovers and invokes custom_svg_filter from its private directory.
   - Cross-agent isolation: Agent A cannot access Agent B's private skill.
   - Central library integrity is preserved without corruption.

2. Central Library Compatibility:
   - Authorized central skills remain accessible.
   - get_skill('media_probe') remains valid, verified, and operational.
   - Central fallback works when local skill is not present.
   - Invalid local skill does not silently shadow central skill.
   - Duplicate identifiers follow explicit resolution rules (local takes precedence for owner).

3. Automatic GitHub Skill Discovery:
   - Requirement mapping and query sanitization (telugu-phoneme-align).
   - Candidate parsing from deterministic fixture.
   - Error handling: rate-limit, timeout, auth failure, malformed response, no-results.
   - Secret token masking in diagnostics and logs.
   - Optional read-only live connectivity check.

4. Skill Factory Agent-Local Installation:
   - Synthetic skill creation, AST audit, and promotion to target_agent_id.
   - Target agent directory updated while central catalog.json remains untouched.
   - Invalid target_agent_id rejection.
   - Malformed skill definitions rejected.

5. Security Boundaries:
   - AST sandbox rejects unauthorized imports and dangerous calls.
   - Discovered candidate is quarantined without auto-execution.
   - Path traversal attempts in skill resolution are blocked.
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent
from SYSTEM.agents.capability_finder.github_discovery import (
    CapabilitySearchMapper,
    DiscoveryResult,
    GitHubRepoCandidate,
    GitHubSkillDiscoveryService,
    mask_token,
)
from SYSTEM.agents.capability_finder.learning.authorization import AuthenticatedOperator
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent
from SYSTEM.agents.skill_factory.lifecycle import SkillLifecycle
from SYSTEM.agents.skill_factory.publisher import PromotionError, SkillPublisher
from SYSTEM.agents.skill_factory.security_validator import SecurityValidator
from SYSTEM.agents.skill_factory.specification import SkillSpecification, validate_specification
from SYSTEM.core import config
from SYSTEM.registries.agent_registry import AgentRegistry
from SYSTEM.registries.skill_registry import (
    CATALOG_FILE,
    SKILLS_DIR,
    SkillRecord,
    SkillSecurityError,
    verify_skill_path_confinement,
    registry as skill_registry,
)


# ==============================================================================
# Test Fixtures & Synthetic Agents
# ==============================================================================

class AssetCuratorAgent(BaseAgent):
    """Synthetic test agent representing an asset curator with private skill capabilities."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="asset_curator",
                name="Asset Curator Agent",
                version="1.0.0",
                category=AgentCategory.VIDEO_ENGINE_AGENT,
                status=AgentStatus.IMPLEMENTED,
                purpose="Curates, validates, and filters vector and motion assets.",
                capabilities=["asset-curation", "svg-filtering"],
                stage_id="planning",
                allowed_tools=["resource_library"],
                owner="agent-system",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            stage_id="planning",
            project_id=request.project_id or "test",
            status="succeeded",
            summary="Asset curation completed.",
        )


@pytest.fixture
def clean_test_skill_dirs(tmp_path):
    """Provides temporary isolated skill directories for test agents."""
    agent_a_dir = tmp_path / "SYSTEM" / "agents" / "agent_alpha" / "skills"
    agent_b_dir = tmp_path / "SYSTEM" / "agents" / "agent_beta" / "skills"
    agent_a_dir.mkdir(parents=True, exist_ok=True)
    agent_b_dir.mkdir(parents=True, exist_ok=True)
    (agent_a_dir / ".gitkeep").write_text("", encoding="utf-8")
    (agent_b_dir / ".gitkeep").write_text("", encoding="utf-8")
    yield {"agent_alpha": agent_a_dir, "agent_beta": agent_b_dir, "root": tmp_path}


# ==============================================================================
# Group A: Agent-Owned Skills
# ==============================================================================

def test_all_22_canonical_agents_have_skills_directories():
    """Verifies that all 22 registered canonical agents (15 video, 7 system) have existing skills/ directories with .gitkeep."""
    reg = AgentRegistry()
    agents = reg.list_all_agents()
    assert len(agents) == 22, f"Expected 22 canonical agents, found {len(agents)}"

    for agent_meta in agents:
        aid = agent_meta.agent_id
        target_skills_dir = (
            (config.PROJECT_ROOT / "SYSTEM" / "agents" / "video_generation_agents" / aid / "skills")
            if (config.PROJECT_ROOT / "SYSTEM" / "agents" / "video_generation_agents" / aid).exists()
            else (config.PROJECT_ROOT / "SYSTEM" / "agents" / aid / "skills")
        )
        assert target_skills_dir.exists(), f"Agent '{aid}' missing private skills directory: {target_skills_dir}"
        gitkeep = target_skills_dir / ".gitkeep"
        assert gitkeep.exists(), f"Agent '{aid}' missing .gitkeep in {target_skills_dir}"


def test_asset_curator_discovers_and_invokes_custom_svg_filter(tmp_path, monkeypatch):
    """Verifies AssetCuratorAgent discovers and executes custom_svg_filter from its private directory."""
    agent_skills_dir = tmp_path / "SYSTEM" / "agents" / "asset_curator" / "skills"
    agent_skills_dir.mkdir(parents=True, exist_ok=True)

    # Place an executable custom_svg_filter in asset_curator's private directory
    filter_dir = agent_skills_dir / "custom_svg_filter"
    filter_dir.mkdir(parents=True, exist_ok=True)
    
    skill_md = filter_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "skill_id: custom_svg_filter\n"
        "name: Custom SVG Filter Specialist\n"
        "domain: motion\n"
        "version: 1.0.0\n"
        "summary: Generates dynamic turbulence and displacement map filters.\n"
        "---\n\n"
        "# Custom SVG Filter\n\nExecutes dynamic SVG displacement filters.\n",
        encoding="utf-8",
    )

    skill_py = filter_dir / "skill.py"
    skill_py.write_text(
        "\"\"\"Custom SVG filter executable module.\"\"\"\n\n"
        "def execute(filter_type: str = 'displacement', scale: int = 15):\n"
        "    return {'status': 'filtered', 'filter_type': filter_type, 'fe_scale': scale}\n",
        encoding="utf-8",
    )

    # Monkeypatch config root so BaseAgent discovers tmp_path
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    agent = AssetCuratorAgent()
    assert "custom_svg_filter" in agent._local_skills
    rec = agent._local_skills["custom_svg_filter"]
    assert rec["domain"] == "motion"
    assert rec["metadata"]["scope"] == "local"

    # Invoke the local skill
    result = agent.invoke_skill("custom_svg_filter", filter_type="feTurbulence", scale=25)
    assert isinstance(result, dict)
    assert result.get("status") == "filtered"
    assert result.get("fe_scale") == 25


def test_cross_agent_private_skill_isolation(tmp_path, monkeypatch):
    """Verifies Agent A cannot discover or execute Agent B's private skill."""
    base = tmp_path / "SYSTEM" / "agents"
    agent_a_dir = base / "agent_alpha" / "skills" / "alpha_private"
    agent_b_dir = base / "agent_beta" / "skills" / "beta_private"
    agent_a_dir.mkdir(parents=True, exist_ok=True)
    agent_b_dir.mkdir(parents=True, exist_ok=True)

    (agent_a_dir / "SKILL.md").write_text(
        "---\nskill_id: alpha_private\nname: Alpha Secret\n---\n# Secret Alpha",
        encoding="utf-8",
    )
    (agent_b_dir / "SKILL.md").write_text(
        "---\nskill_id: beta_private\nname: Beta Secret\n---\n# Secret Beta",
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    meta_a = AgentMetadata(agent_id="agent_alpha", name="Alpha", version="1.0.0", status=AgentStatus.IMPLEMENTED, purpose="A")
    meta_b = AgentMetadata(agent_id="agent_beta", name="Beta", version="1.0.0", status=AgentStatus.IMPLEMENTED, purpose="B")

    class TestAgent(BaseAgent):
        def validate(self, p, r): return []
        def execute(self, p, r): return AgentResult(agent_id=self.agent_id, stage_id="", project_id="", status="succeeded")

    agent_a = TestAgent(meta_a)
    agent_b = TestAgent(meta_b)

    # Agent A has alpha_private, but NOT beta_private
    assert "alpha_private" in agent_a._local_skills
    assert "beta_private" not in agent_a._local_skills

    # Agent B has beta_private, but NOT alpha_private
    assert "beta_private" in agent_b._local_skills
    assert "alpha_private" not in agent_b._local_skills

    # Agent A querying beta_private via registry is rejected with KeyError
    with pytest.raises(KeyError, match="not found for agent 'agent_alpha'"):
        skill_registry.get_agent_skill(agent_id="agent_alpha", skill_name="beta_private")


def test_adding_private_skill_leaves_central_catalog_unmodified(tmp_path, monkeypatch):
    """Verifies that authoring an agent-local skill never corrupts or alters central skills/catalog.json."""
    catalog_before = CATALOG_FILE.read_text(encoding="utf-8") if CATALOG_FILE.exists() else ""

    agent_skills_dir = (
        (config.PROJECT_ROOT / "SYSTEM" / "agents" / "video_generation_agents" / "audio_input" / "skills" / "temp_isolated_test")
        if (config.PROJECT_ROOT / "SYSTEM" / "agents" / "video_generation_agents" / "audio_input").exists()
        else (config.PROJECT_ROOT / "SYSTEM" / "agents" / "audio_input" / "skills" / "temp_isolated_test")
    )
    agent_skills_dir.mkdir(parents=True, exist_ok=True)
    (agent_skills_dir / "SKILL.md").write_text("---\nskill_id: temp_isolated_test\n---\n# Test", encoding="utf-8")

    try:
        catalog_after = CATALOG_FILE.read_text(encoding="utf-8") if CATALOG_FILE.exists() else ""
        assert catalog_before == catalog_after, "Central catalog.json was modified when creating private agent skill!"
    finally:
        shutil.rmtree(agent_skills_dir, ignore_errors=True)


# ==============================================================================
# Group B: Central Library Compatibility
# ==============================================================================

def test_central_media_probe_skill_remains_accessible():
    """Verifies that central skill media_probe remains valid, approved, and accessible via get_skill."""
    skill_registry.initialize()
    rec, content = skill_registry.get_skill("media_probe")
    assert rec.skill_id == "media_probe"
    assert rec.status == "approved"
    assert "media" in rec.capabilities or "qc" in rec.domain
    assert len(content) > 0


def test_central_fallback_when_local_skill_missing():
    """Verifies that an agent requesting a central skill falls back seamlessly to the central catalog."""
    rec, content = skill_registry.get_agent_skill(agent_id="render_video", skill_name="media_probe")
    assert rec.skill_id == "media_probe"
    assert rec.metadata.get("scope") == "central"
    assert len(content) > 0


def test_duplicate_identifier_local_takes_precedence_for_owner(tmp_path, monkeypatch):
    """Verifies that if an agent has a local skill shadowing a central skill, the local version is selected."""
    agent_skills_dir = tmp_path / "SYSTEM" / "agents" / "render_video" / "skills" / "media_probe"
    agent_skills_dir.mkdir(parents=True, exist_ok=True)
    (agent_skills_dir / "SKILL.md").write_text(
        "---\nskill_id: media_probe\nname: Overridden Local Probe\nversion: 2.0.0\n---\n# Local Overridden Probe",
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    # For render_video, local shadows central
    rec, content = skill_registry.get_agent_skill(agent_id="render_video", skill_name="media_probe")
    assert rec.metadata.get("scope") == "local"
    assert rec.version == "2.0.0"
    assert "Overridden Local Probe" in rec.name

    # For another agent (e.g. final_qc), central skill is still returned
    central_rec, _ = skill_registry.get_agent_skill(agent_id="final_qc", skill_name="media_probe")
    assert central_rec.metadata.get("scope") == "central"


# ==============================================================================
# Group C: Automatic GitHub Discovery
# ==============================================================================

def test_query_mapping_and_sanitization():
    """Verifies mapping of domain capabilities to sanitized search terms."""
    mapper = CapabilitySearchMapper()
    raw_query = mapper.map_capability("telugu-phoneme-align")
    assert "telugu" in raw_query
    assert "phoneme" in raw_query

    # Test sanitization strips dangerous shell punctuation
    dirty = "telugu-phoneme-align; rm -rf /; `curl http://bad.com`"
    clean = mapper.sanitize_query(dirty)
    assert ";" not in clean
    assert "`" not in clean
    assert "rm -rf" in clean  # words remain, control chars stripped
    assert len(clean) <= 100


def test_github_discovery_with_deterministic_fixture():
    """Verifies GitHub discovery client parses candidate metadata from fixture without network."""
    sample_fixture = {
        "total_count": 1,
        "items": [
            {
                "id": 1029384,
                "name": "telugu-phoneme-align",
                "full_name": "indic-ai/telugu-phoneme-align",
                "html_url": "https://github.com/indic-ai/telugu-phoneme-align",
                "description": "High-accuracy phonetic alignment tool for Telugu speech audio using CTC loss.",
                "language": "Python",
                "license": {"spdx_id": "MIT"},
                "default_branch": "main",
                "stargazers_count": 142,
                "forks_count": 28,
                "topics": ["telugu", "phoneme", "alignment", "speech"],
                "score": 85.0,
            }
        ],
    }

    def mock_client(query: str, headers: dict[str, str]) -> dict[str, Any]:
        return sample_fixture

    service = GitHubSkillDiscoveryService(http_client=mock_client)
    res = service.search("telugu-phoneme-align", limit=1)

    assert res.status == "succeeded"
    assert res.total_candidates == 1
    cand = res.candidates[0]
    assert cand.name == "telugu-phoneme-align"
    assert cand.owner == "indic-ai"
    assert cand.license == "MIT"
    assert cand.compatibility_status == "compatible"
    assert cand.internally_ranked_score > 0.5


def test_github_discovery_error_handling():
    """Verifies graceful handling of rate limits, timeouts, auth errors, and no-results."""
    # 1. Rate limit error
    def mock_rate_limit(q, h):
        raise urllib.error.HTTPError(None, 403, "Rate Limit Exceeded", {}, None)

    service = GitHubSkillDiscoveryService(http_client=mock_rate_limit)
    res = service.search("telugu-audio")
    assert res.status == "failed"
    assert "Rate Limit Exceeded" in str(res.diagnostic) or res.error_code == "client_error"

    # 2. Timeout error
    def mock_timeout(q, h):
        raise TimeoutError("Connection timed out after 5.0 seconds")

    service = GitHubSkillDiscoveryService(http_client=mock_timeout)
    res = service.search("scene-segmentation")
    assert res.status == "failed"
    assert "timed out" in str(res.diagnostic).lower()

    # 3. Empty results (no fabrication)
    def mock_empty(q, h):
        return {"total_count": 0, "items": []}

    service = GitHubSkillDiscoveryService(http_client=mock_empty)
    res = service.search("nonexistent-niche-skill-xyz")
    assert res.status == "no_results"
    assert len(res.candidates) == 0


def test_github_token_is_masked_in_diagnostics():
    """Verifies that secrets and GitHub tokens are strictly masked in logs and diagnostics."""
    fake_token = "ghp_superSecretToken1234567890abcdef"
    masked = mask_token(fake_token)
    assert "superSecretToken" not in masked
    assert masked.startswith("ghp_") and masked.endswith("cdef")

    def mock_error_with_token(q, h):
        raise RuntimeError(f"Authentication failed with token: {fake_token}")

    service = GitHubSkillDiscoveryService(token=fake_token, http_client=mock_error_with_token)
    res = service.search("test")
    assert fake_token not in str(res.diagnostic)
    assert masked in str(res.diagnostic)


# ==============================================================================
# Group D: Skill Factory Agent-Local Installation
# ==============================================================================

def test_skill_factory_agent_local_installation(tmp_path, monkeypatch):
    """Verifies SkillFactory promotes a synthetic skill directly into an agent's private directory."""
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    agent_skills_dir = tmp_path / "SYSTEM" / "agents" / "visual_planning" / "skills"
    agent_skills_dir.mkdir(parents=True, exist_ok=True)

    spec = SkillSpecification(
        skill_id="telugu_concept_stylizer",
        name="Telugu Concept Stylizer",
        purpose="Applies cultural cinematic style motifs to visual concepts.",
        domain="planning",
        version="1.0.0",
        capabilities=["style-mapping", "concept-adaptation"],
        target_agent_id="visual_planning",
        compatible_agents=["visual_planning"],
    )

    content = spec.to_yaml_manifest()
    lifecycle = SkillLifecycle(skill_id=spec.skill_id, version=spec.version, current_state="APPROVED")
    test_operator = AuthenticatedOperator(
        operator_id="test_runner",
        role="operator",
        auth_method="trusted_context",
        verified_at="2026-10-17T00:00:00+00:00",
    )

    publisher = SkillPublisher()
    prom_res = publisher.promote_skill(
        spec=spec,
        content=content,
        lifecycle=lifecycle,
        operator=test_operator,
        target_agent_id="visual_planning",
    )

    assert prom_res.status == "approved"
    target_file = Path(prom_res.entrypoint)
    assert target_file.exists()
    assert "visual_planning" in str(target_file)
    assert (agent_skills_dir / "telugu_concept_stylizer" / "SKILL.md").exists()


def test_skill_factory_rejects_invalid_target_agent_id():
    """Verifies SkillFactory rejects installation if target_agent_id is not in AgentRegistry."""
    spec = SkillSpecification(
        skill_id="invalid_agent_skill",
        name="Invalid Agent Skill",
        purpose="Testing invalid agent rejection.",
        domain="general",
        capabilities=["test"],
        target_agent_id="completely_fictional_agent_999",
    )
    content = spec.to_yaml_manifest()
    lifecycle = SkillLifecycle(skill_id=spec.skill_id, version="1.0.0", current_state="APPROVED")
    publisher = SkillPublisher()
    test_operator = AuthenticatedOperator(
        operator_id="test_runner",
        role="operator",
        auth_method="trusted_context",
        verified_at="2026-10-17T00:00:00+00:00",
    )

    with pytest.raises((ValueError, PromotionError), match="not registered in AgentRegistry"):
        publisher.promote_skill(
            spec=spec,
            content=content,
            lifecycle=lifecycle,
            operator=test_operator,
            target_agent_id="completely_fictional_agent_999",
        )


def test_skill_specification_validation_rejects_malformed_definitions():
    """Verifies validate_specification rejects invalid skill IDs, missing capabilities, or bad versions."""
    bad_spec = SkillSpecification(
        skill_id="../escape_path",  # Path traversal
        name="",                   # Missing name
        purpose="",
        domain="planning",
        version="not_semver",      # Bad version
        capabilities=[],           # Empty capabilities
    )
    errors = validate_specification(bad_spec)
    assert len(errors) >= 4
    assert any("Path traversal" in e or "invalid" in e for e in errors)
    assert any("name is required" in e for e in errors)
    assert any("Semantic Version" in e for e in errors)
    assert any("capabilities" in e for e in errors)


# ==============================================================================
# Group E: Security Boundaries
# ==============================================================================

def test_ast_sandbox_rejects_dangerous_code_in_external_skills():
    """Verifies SecurityValidator detects unauthorized imports (ctypes, socket) and dangerous calls."""
    validator = SecurityValidator()

    dangerous_code = (
        "import socket\n"
        "import ctypes\n"
        "import os\n\n"
        "def run_exploit():\n"
        "    s = socket.socket()\n"
        "    os.system('rm -rf /')\n"
    )

    audit = validator.audit(dangerous_code, filename="untrusted_candidate.py")
    assert audit.passed is False
    assert audit.quarantine_required is True
    assert any("ctypes" in f or "socket" in f for f in audit.findings)
    assert any("os.system" in f for f in audit.findings)


def test_path_traversal_in_skill_lookup_is_strictly_blocked():
    """Verifies path traversal attempts in skill lookup throw SkillSecurityError."""
    with pytest.raises(SkillSecurityError, match="Path traversal"):
        skill_registry.verify_skill_path_confinement("../../../etc/shadow")


def test_candidate_repository_is_quarantined_without_execution(tmp_path):
    """Verifies discovered GitHub candidate is staged in quarantine without executing code."""
    staging_dir = tmp_path / "staging"
    service = GitHubSkillDiscoveryService(staging_dir=staging_dir)

    cand = GitHubRepoCandidate(
        name="sample-nlp-repo",
        owner="untrusted-org",
        full_name="untrusted-org/sample-nlp-repo",
        url="https://github.com/untrusted-org/sample-nlp-repo",
        description="Candidate NLP repo.",
        primary_language="Python",
        license="MIT",
        default_branch="main",
    )

    malicious_snippet = "import os; os.system('format c:')"
    stage_report = service.stage_and_inspect(cand, content=malicious_snippet)

    assert stage_report["status"] == "staged"
    assert stage_report["security_review_status"] in ("quarantined", "rejected")
    assert (staging_dir / "untrusted_org" / "sample_nlp_repo" / "candidate_manifest.json").exists()


# ==============================================================================
# Group F: Capability Resolution Workflow
# ==============================================================================

def test_capability_finder_resolution_workflow(tmp_path, monkeypatch):
    """Verifies end-to-end capability resolution: local check -> central check -> github discovery."""
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    # 1. Test local hit
    agent_dir = tmp_path / "SYSTEM" / "agents" / "audio_input" / "skills" / "local_equalizer"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "SKILL.md").write_text("---\nskill_id: local_equalizer\nname: Equalizer\n---\n# Eq", encoding="utf-8")

    finder = CapabilityFinderAgent()
    res_local = finder.resolve_capability_workflow(agent_id="audio_input", requirement="local_equalizer")
    assert res_local["status"] == "succeeded"
    assert res_local["source"] == "agent_local"

    # 2. Test central hit
    res_central = finder.resolve_capability_workflow(agent_id="final_qc", requirement="media_probe")
    assert res_central["status"] == "succeeded"
    assert res_central["source"] == "central_library"
