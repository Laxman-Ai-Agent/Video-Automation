"""Production Verification Test Suite for Phase 2: Capability Registry & Capability Finder Core Upgrade.

Validates:
1. Central CapabilityRegistry lifecycle, search, filtering, and cross-domain synchronization.
2. Natural language RequirementParser handling complex constraints and domains.
3. Static AST scanner extracting code symbols and advertised capabilities safely without executing code.
4. CapabilityMatcher scoring, ranking, and deduplication.
5. GapAnalyzer evaluating capability satisfaction and recommending actions (REUSE, ADAPT, CREATE_SKILL, CREATE_AGENT).
6. CapabilityFinderAgent end-to-end execution with backward-compatible contracts.
7. Main Architecture Agent (MAA) delegation to CapabilityFinderAgent receiving structured gap analysis.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent
from SYSTEM.agents.capability_finder.discovery.ast_scanner import AstScanner
from SYSTEM.agents.capability_finder.discovery.gap_analyzer import GapAnalyzer
from SYSTEM.agents.capability_finder.discovery.matcher import CapabilityMatcher
from SYSTEM.agents.capability_finder.discovery.requirement_parser import RequirementParser
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.contracts import AgentRequest, AgentResult
from SYSTEM.registries.capability_registry import (
    CapabilityRecord,
    CapabilityRegistry,
    get_capability_registry,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestCapabilityRegistryCore:
    """Verifies central CapabilityRegistry indexing and synchronization."""

    def test_registry_sync_populates_cross_domain_capabilities(self):
        reg = CapabilityRegistry()
        report = reg.sync_with_registries()

        assert report["agents_synced"] >= 14, "Expected video agents to be synced"
        assert report["skills_synced"] >= 5, "Expected approved skills to be synced"
        assert report["tools_synced"] >= 5, "Expected central tools to be synced"
        assert report["total_records"] >= 24

    def test_registry_search_by_domain_and_tag(self):
        reg = CapabilityRegistry()
        reg.sync_with_registries()

        # Search motion domain
        motion_caps = reg.search_capabilities(domain="video_engine_agent", query="motion")
        assert len(motion_caps) >= 1
        assert any("motion" in c.capability_id for c in motion_caps)

        # Search audio domain
        audio_caps = reg.search_capabilities(query="transcription")
        assert len(audio_caps) >= 1


class TestRequirementParsingAndAST:
    """Verifies natural language extraction and safe AST inspection."""

    def test_complex_chart_prompt_parsing(self):
        parser = RequirementParser()
        prompt = "Create an animated stacked bar chart for a 9:16 video with Telugu labels, smooth transitions, and deterministic rendering."
        req = parser.parse(prompt)

        assert req.domain == "motion"
        assert req.primary_capability == "data_visualization"
        assert req.constraints["aspect_ratio"] == "9:16"
        assert req.constraints["language"] == "telugu"
        assert req.constraints["chart_type"] == "stacked_bar_chart"
        assert req.constraints["deterministic_rendering"] is True
        assert req.constraints["smooth_transitions"] is True

    def test_safe_ast_inspection_of_real_codebase(self):
        scanner = AstScanner()
        target_dir = PROJECT_ROOT / "SYSTEM" / "agents" / "main_architecture_agent"
        items = scanner.scan_directory(target_dir, max_depth=2)

        assert len(items) > 0
        maa_class = next((i for i in items if i.name == "MainArchitectureAgent"), None)
        assert maa_class is not None
        assert maa_class.kind == "class"
        assert maa_class.line_start > 0
        assert len(maa_class.file_hash) == 64
        assert "main_architecture_agent" in maa_class.file_path


class TestGapAnalysisAndDecisions:
    """Verifies decision rationale: REUSE vs ADAPT vs CREATE_SKILL vs CREATE_AGENT."""

    def test_gap_analysis_exact_reuse(self):
        parser = RequirementParser()
        matcher = CapabilityMatcher()
        analyzer = GapAnalyzer()

        req = parser.parse("Transcribe speech in audio file")
        reg = CapabilityRegistry()
        reg.sync_with_registries()

        candidates = reg.search_capabilities(query="speech_to_text")
        matches = matcher.match(req, candidates)
        report = analyzer.analyze(req, matches)

        assert report.overall_status in ("satisfied", "partial")
        if report.overall_status == "satisfied":
            assert report.recommended_action == "REUSE"
            assert report.suggested_delegate_id in ("audio_input", "faster_whisper")

    def test_gap_analysis_missing_requires_skill_creation(self):
        parser = RequirementParser()
        matcher = CapabilityMatcher()
        analyzer = GapAnalyzer()

        req = parser.parse("Apply holographic 3D particle glow effect to visual theme")
        matches = matcher.match(req, [])
        report = analyzer.analyze(req, matches)

        assert report.overall_status == "missing"
        assert report.recommended_action == "CREATE_SKILL"
        assert report.suggested_delegate_id == "skill_factory"


class TestCapabilityFinderAgentIntegration:
    """Verifies upgraded CapabilityFinderAgent execute() lifecycle and MAA delegation."""

    def test_capability_finder_full_metadata(self, tmp_path: Path):
        agent = CapabilityFinderAgent()
        prompt = "Create an animated stacked bar chart for a 9:16 video with Telugu labels"
        req = AgentRequest(
            project_id="test_proj",
            agent_id="capability_finder",
            stage_id="system",
            parameters={"query": prompt, "check_prerequisites": True},
        )
        res = agent.execute(tmp_path, req)

        assert res.status == "succeeded"
        # Backward-compatible fields
        assert "matching_agents" in res.metadata
        assert "matching_skills" in res.metadata
        assert "available_tools" in res.metadata
        assert "prerequisites" in res.metadata

        # Upgraded fields
        assert "parsed_requirement" in res.metadata
        assert "capability_matches" in res.metadata
        assert "gap_analysis" in res.metadata
        assert "recommended_action" in res.metadata
        assert "suggested_delegate_id" in res.metadata

    def test_maa_delegation_with_gap_report(self, tmp_path: Path):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            project_id="test_reorg",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "target_agent_id": "capability_finder",
                "sub_parameters": {
                    "query": "Transcribe Telugu speech to text with word timestamps",
                    "check_prerequisites": True,
                },
            },
        )
        res = maa._handle_delegate(tmp_path, req)

        assert res.status == "succeeded"
        delegated_res = res.metadata.get("delegated_result", {})
        meta = delegated_res.get("metadata", {})
        assert "parsed_requirement" in meta
        assert "gap_analysis" in meta
        assert meta["parsed_requirement"]["domain"] == "audio"
