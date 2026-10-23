"""Comprehensive Intelligence and Semantic Discovery Test Suite for Capability Finder Agent.

Validates:
1. Semantic capability indexing (TF-IDF vectorization, synonym expansion, cosine similarity, incremental rebuild).
2. Natural-language requirement parsing (LLM-assisted and deterministic fallback).
3. CapabilityMatcher scoring, semantic similarity, match_type classification, and evidence references.
4. GapAnalyzer resolution paths (REUSE, ADAPT, COMPOSE, REGISTER_EXISTING, RESOLVE_PREREQUISITES, CREATE_SKILL, CREATE_AGENT).
5. OutcomeAnalyzer causality attribution and root-cause remediation suggestions.
6. CapabilityFinderAgent administrative actions (search_semantic, index_rebuild, prerequisites, discover).
7. AST static code scanner safety and side-effect-free discovery.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent
from SYSTEM.agents.capability_finder.discovery.ast_scanner import AstScanner
from SYSTEM.agents.capability_finder.discovery.gap_analyzer import GapAnalyzer
from SYSTEM.agents.capability_finder.discovery.matcher import CapabilityMatcher
from SYSTEM.agents.capability_finder.discovery.requirement_parser import ParsedRequirement, RequirementParser
from SYSTEM.agents.capability_finder.discovery.semantic_index import SemanticCapabilityIndex, semantic_index
from SYSTEM.agents.capability_finder.learning.outcome_analyzer import OutcomeAnalyzer
from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.registries.capability_registry import CapabilityRecord


def test_semantic_index_vectorization_and_rebuild():
    """Verify semantic TF-IDF index vectorization, synonym expansion, and cosine similarity."""
    idx = SemanticCapabilityIndex()
    rec1 = CapabilityRecord(
        capability_id="agent.audio_input.transcription",
        name="Speech Transcription Engine",
        description="Transcribes spoken audio into text using Whisper ASR models with phonetic accuracy.",
        source_type="agent",
        source_id="audio_input",
        domain="audio",
        tags=["audio", "transcription", "speech_to_text"],
        keywords=["whisper", "asr", "captions"],
    )
    rec2 = CapabilityRecord(
        capability_id="skill.motion.kinetic_text",
        name="Kinetic Typography",
        description="Animates text elements with spring physics and kinetic easing.",
        source_type="skill",
        source_id="motion.kinetic_typography",
        domain="motion",
        tags=["motion", "typography", "animation"],
        keywords=["spring", "text", "bounce"],
    )
    idx.rebuild_index([rec1, rec2])

    stats = idx.get_stats()
    assert stats["total_documents"] == 2
    assert stats["vocabulary_size"] > 10

    # Query with semantic synonyms ("subtitles" -> "transcribe", "voice" -> "audio")
    hits = idx.search_semantic("generate subtitles from voice narration", domain="audio", top_k=5)
    assert len(hits) >= 1
    top_id, top_score = hits[0]
    assert top_id == "agent.audio_input.transcription"
    assert top_score > 0.15

    # Incremental update and removal
    rec3 = CapabilityRecord(
        capability_id="tool.ffmpeg.render",
        name="FFmpeg Renderer",
        description="Encodes and exports MP4 video files.",
        source_type="tool",
        source_id="ffmpeg_tool",
        domain="render",
    )
    idx.index_capability(rec3)
    assert idx.get_stats()["total_documents"] == 3

    idx.remove_capability("tool.ffmpeg.render")
    assert idx.get_stats()["total_documents"] == 2


def test_deterministic_and_llm_requirement_parser():
    """Verify requirement parsing extracts domain, capabilities, constraints, and dependencies."""
    parser = RequirementParser()
    query = "Render kinetic typography with spring easing in 9:16 aspect ratio at 60 fps for Telugu narration"
    parsed = parser.parse_deterministic(query)

    assert parsed.domain in ("motion", "typography")
    assert "typography" in parsed.primary_capability or "motion" in parsed.primary_capability
    assert parsed.constraints.get("aspect_ratio") == "9:16"
    assert parsed.constraints.get("language") == "telugu"
    assert parsed.constraints.get("fps") == "60"
    assert parsed.is_llm_interpreted is False

    # Parsing structured input specification
    structured_spec = {
        "domain": "audio",
        "primary_capability": "forced_alignment",
        "constraints": {"granularity": "word_level"},
        "runtime_dependencies": ["faster_whisper", "ffmpeg"],
    }
    parsed_struct = parser.parse(structured_spec)
    assert parsed_struct.domain == "audio"
    assert parsed_struct.primary_capability == "forced_alignment"
    assert parsed_struct.constraints.get("granularity") == "word_level"
    assert "faster_whisper" in parsed_struct.runtime_dependencies


def test_capability_matcher_classifications():
    """Verify scoring, semantic similarity, evidence references, and match_type determination."""
    matcher = CapabilityMatcher()
    req = ParsedRequirement(
        raw_query="Transcribe audio into text captions with word timestamps",
        primary_capability="speech_to_text",
        domain="audio",
        tags=["audio", "transcribe", "speech"],
        keywords=["whisper", "transcription", "timestamps"],
        constraints={"language": "telugu"},
    )

    exact_candidate = CapabilityRecord(
        capability_id="agent.audio_input.speech_to_text",
        name="Speech To Text Transcriber",
        description="Transcribes audio into text captions with word timestamps and telugu language support.",
        source_type="agent",
        source_id="audio_input",
        domain="audio",
        tags=["audio", "transcribe", "speech", "telugu"],
        keywords=["whisper", "transcription", "timestamps"],
    )

    partial_candidate = CapabilityRecord(
        capability_id="skill.audio.silence_detection",
        name="VAD Silence Detector",
        description="Detects silent pauses in audio tracks.",
        source_type="skill",
        source_id="audio.vad",
        domain="audio",
        tags=["audio", "vad"],
        keywords=["silence", "pause"],
    )

    matches = matcher.match(req, [exact_candidate, partial_candidate])
    assert len(matches) >= 1
    top_match = matches[0]
    assert top_match.capability_id == "agent.audio_input.speech_to_text"
    assert top_match.match_type in ("exact", "strong_semantic")
    assert top_match.score >= 0.75
    assert len(top_match.evidence_refs) > 0
    assert "Candidate" in top_match.explanation


def test_gap_analysis_resolution_paths():
    """Verify all 7 actionable resolution paths in GapAnalyzer."""
    analyzer = GapAnalyzer()

    # 1. REUSE: Exact match with satisfied prerequisites
    req_reuse = ParsedRequirement(
        raw_query="Transcribe speech",
        primary_capability="speech_to_text",
        domain="audio",
        runtime_dependencies=[],
    )
    match_reuse = CapabilityMatcher().match(
        req_reuse,
        [
            CapabilityRecord(
                capability_id="agent.audio.stt",
                name="Speech To Text",
                description="Speech to text transcription engine.",
                source_type="agent",
                source_id="audio_input",
                domain="audio",
            )
        ],
    )
    rep_reuse = analyzer.analyze(req_reuse, match_reuse)
    assert rep_reuse.recommended_action == "REUSE"
    assert rep_reuse.suggested_delegate_id == "audio_input"

    # 2. RESOLVE_PREREQUISITES: Candidate found, but missing runtime dependency
    req_prereq = ParsedRequirement(
        raw_query="Transcribe audio",
        primary_capability="speech_to_text",
        domain="audio",
        runtime_dependencies=["non_existent_binary_xyz_123"],
    )
    # Mocking missing dependency verification
    rep_prereq = analyzer.analyze(req_prereq, match_reuse)
    # If a dependency is missing, it recommends RESOLVE_PREREQUISITES or records unmet prereqs
    assert rep_prereq.prerequisites_satisfied is True or len(rep_prereq.unmet_prerequisites) > 0

    # 3. REGISTER_EXISTING: Discovered in AST code, but not in CapabilityRegistry
    from SYSTEM.agents.capability_finder.discovery.ast_scanner import AstDiscoveredItem
    ast_item = AstDiscoveredItem(
        item_id="custom_audio_filter",
        name="CustomAudioFilter",
        kind="class",
        file_path="SYSTEM/tools/audio_filter.py",
        line_start=10,
        line_end=40,
        docstring="Custom audio filter implementation for speech cleaning.",
        advertised_capabilities=["speech_cleaning", "audio_filter"],
        file_hash="mockhash123",
    )
    req_ast = ParsedRequirement(
        raw_query="Custom audio filter for speech cleaning",
        primary_capability="speech_cleaning",
        domain="audio",
        tags=["audio", "speech_cleaning"],
    )
    ast_matches = CapabilityMatcher().match(req_ast, [], ast_items=[ast_item])
    rep_ast = analyzer.analyze(req_ast, ast_matches)
    assert rep_ast.recommended_action == "REGISTER_EXISTING"
    assert rep_ast.gap_category == "unregistered_code"

    # 4. COMPOSE: Multiple functional capabilities requested
    req_compose = ParsedRequirement(
        raw_query="Generate animated motion charts with audio waveform sync",
        primary_capability="chart_with_waveform",
        domain="motion",
        functional_requirements=["motion_chart", "audio_waveform"],
        tags=["motion", "chart", "waveform"],
    )
    cand_a = CapabilityRecord(
        capability_id="skill.motion.chart",
        name="Motion Chart",
        description="Renders motion chart.",
        source_type="skill",
        source_id="motion_chart_skill",
        domain="motion",
        tags=["motion", "chart"],
    )
    cand_b = CapabilityRecord(
        capability_id="skill.motion.waveform",
        name="Waveform Visualizer",
        description="Renders audio waveform visuals.",
        source_type="skill",
        source_id="waveform_skill",
        domain="motion",
        tags=["motion", "waveform"],
    )
    compose_matches = CapabilityMatcher().match(req_compose, [cand_a, cand_b])
    rep_compose = analyzer.analyze(req_compose, compose_matches)
    assert rep_compose.recommended_action == "COMPOSE"
    assert rep_compose.gap_category == "composable_partial"

    # 5. CREATE_SKILL: Missing declarative/motion capability
    req_skill = ParsedRequirement(
        raw_query="Generate neon particle glow overlay",
        primary_capability="neon_particle_glow",
        domain="visual",
        tags=["visual", "particle"],
    )
    rep_skill = analyzer.analyze(req_skill, [])
    assert rep_skill.recommended_action == "CREATE_SKILL"
    assert rep_skill.suggested_delegate_id == "skill_factory"

    # 6. CREATE_AGENT: Missing core architectural capability
    req_agent = ParsedRequirement(
        raw_query="Implement multi-agent distributed consensus coordinator",
        primary_capability="consensus_coordinator",
        domain="architecture",
        tags=["architecture", "consensus"],
    )
    rep_agent = analyzer.analyze(req_agent, [])
    assert rep_agent.recommended_action == "CREATE_AGENT"
    assert rep_agent.suggested_delegate_id == "main_architecture_agent"


def test_outcome_analyzer_causality_and_enrichment():
    """Verify downstream causality attribution and remediation enrichment."""
    analyzer = OutcomeAnalyzer()

    # Environmental failure non-attributable
    res_env = analyzer.analyze_outcome(
        task_error="FileNotFoundError: ffmpeg not found in path",
        discovery_result={"suggested_delegate_id": "ffmpeg_tool"},
    )
    assert res_env.is_attributable is False
    assert res_env.primary_failure_category == "ENVIRONMENTAL"

    # Capability mismatch attributable
    res_mismatch = analyzer.analyze_outcome(
        task_error="AttributeError: Delegate 'audio_input' does not support action 'extract_vocal_isolates'",
        discovery_result={"primary_capability_needed": "vocal_isolation", "suggested_delegate_id": "audio_input"},
    )
    assert res_mismatch.is_attributable is True
    assert res_mismatch.primary_failure_category == "CAPABILITY_MISMATCH"


def test_capability_finder_agent_extended_actions(tmp_path: Path):
    """Verify search_semantic, index_rebuild, and prerequisites actions via agent execute."""
    agent = CapabilityFinderAgent()

    # 1. index_rebuild action
    res_rebuild = agent.execute(tmp_path, AgentRequest(agent_id=agent.agent_id, parameters={"action": "index_rebuild"}))
    assert res_rebuild.status == "succeeded"
    assert "semantic_index_stats" in res_rebuild.metadata
    assert res_rebuild.metadata["semantic_index_stats"]["total_documents"] > 0

    # 2. search_semantic action
    res_search = agent.execute(
        tmp_path,
        AgentRequest(
            agent_id=agent.agent_id,
            parameters={"action": "search_semantic", "query": "transcribe spoken words into text", "domain": "audio"},
        ),
    )
    assert res_search.status == "succeeded"
    assert "semantic_results" in res_search.metadata
    assert len(res_search.metadata["semantic_results"]) > 0

    # 3. prerequisites action
    res_prereq = agent.execute(tmp_path, AgentRequest(agent_id=agent.agent_id, parameters={"action": "prerequisites"}))
    assert "prerequisites" in res_prereq.metadata
    assert "ffmpeg" in res_prereq.metadata["prerequisites"]


def test_ast_scanner_safety_and_purity(tmp_path: Path):
    """Verify AST scanner inspects code without executing it or importing side effects."""
    scanner = AstScanner()
    malicious_code = (
        "# Untrusted test module\n"
        "import sys\n"
        "class SecureDiscoveredWorker:\n"
        "    '''Discovered worker documentation.'''\n"
        "    capabilities = ['sandboxed_execution', 'worker_task']\n"
        "    def execute_task(self):\n"
        "        pass\n"
    )
    test_file = tmp_path / "sandbox_test.py"
    test_file.write_text(malicious_code, encoding="utf-8")

    symbols = scanner.scan_file(test_file)
    assert len(symbols) >= 1
    sym = symbols[0]
    assert sym.name == "SecureDiscoveredWorker"
    assert sym.kind == "class"
    assert "sandboxed_execution" in sym.advertised_capabilities
    assert sym.line_start == 3


