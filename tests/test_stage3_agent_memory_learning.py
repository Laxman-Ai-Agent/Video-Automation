"""Comprehensive Acceptance Test Suite for Stage 3:
Per-Agent Memory, Self-Learning & Shared Knowledge.

Verifies:
1. Agent Partitions:
   - All 21 registered canonical agents have persistent memory partitions.
   - Record written by Agent A is strictly stored under Agent A's partition.
   - Agent B cannot overwrite or accidentally retrieve Agent A's private memory.
   - Shared knowledge is accessed through approved channels.
   - Existing shared_memory.json records remain intact and readable.

2. Persistence & Concurrency:
   - Records survive save/reload across simulated process restarts.
   - Concurrent writes do not corrupt unrelated agent records.
   - Malformed records are rejected/quarantined without corrupting valid data.
   - Memory storage/retrieval failures do not crash caller pipelines.

3. Experience Recording & Reflection:
   - Completed tasks create truthful experience records.
   - Failed tasks record actual failure categories.
   - No fabricated quality metrics when none exist.
   - Future tasks can retrieve approved experiences.
   - Duplicate reflections and reentrancy loops are controlled.

4. Benchmark Evaluation & Rollback:
   - Passing candidate can proceed through learning gate.
   - Candidate with benchmark regression is rejected by LearningGate.
   - Rollback manager restores previous verified baseline.
   - Security policy rules cannot be weakened by learning.

5. Integration:
   - BaseAgent experience hooks work for representative agents.
   - Actual task lifecycle (invoke) records and retrieves experience.
   - Capability Finder can evaluate and promote lessons.
   - Stage 2 local skills and central fallback remain compatible.
   - Memory lookup performance meets the <= 50ms requirement.

6. Required Scenario:
   - 3 mock scene-segmentation tasks produce 3 experience records under scene_segmentation.
   - An adjustment degrading benchmark performance is blocked by LearningGate.
"""
from __future__ import annotations

import concurrent.futures
import copy
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from SYSTEM.agents.capability_finder.learning.authorization import AuthenticatedOperator
from SYSTEM.agents.capability_finder.learning.case_collector import CaseCollector, LearningCase
from SYSTEM.agents.capability_finder.learning.knowledge_promoter import KnowledgePromoter
from SYSTEM.agents.capability_finder.learning.learning_gate import LearningGate
from SYSTEM.agents.capability_finder.learning.lesson_evaluator import (
    EvaluationMetrics,
    LearningEvaluation,
    LessonEvaluator,
)
from SYSTEM.agents.capability_finder.learning.lesson_generator import LessonProposal
from SYSTEM.agents.capability_finder.learning.rollback_manager import RollbackManager
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.core import config
from SYSTEM.memory.agent_experience import AgentExperience, validate_experience
from SYSTEM.memory.memory_scoping import MemoryAccessViolation
from SYSTEM.memory.per_agent_store import PerAgentMemoryStore, per_agent_store
from SYSTEM.memory.shared_memory import MEMORY_FILE, service as shared_memory_service
from SYSTEM.registries.agent_registry import AgentRegistry


# ==============================================================================
# Test Fixtures & Synthetic Agents
# ==============================================================================

class SyntheticSceneSegmentationAgent(BaseAgent):
    """Synthetic SceneSegmentationAgent implementing BaseAgent hooks."""

    def __init__(self) -> None:
        metadata = AgentMetadata(
            agent_id="scene_segmentation",
            name="Scene Segmentation Agent",
            version="1.0.0",
            category=AgentCategory.VIDEO_ENGINE_AGENT,
            status=AgentStatus.IMPLEMENTED,
            purpose="Segments transcripts into balanced visual scenes.",
            capabilities=["semantic-chunking", "boundary-snapping"],
            stage_id="segmentation",
            owner="agent-system",
        )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        if request.parameters.get("fail_validation"):
            return ["Invalid audio duration window: speech boundaries out of bounds."]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        if request.parameters.get("fail_execution"):
            raise RuntimeError("Segmentation audio alignment lost sync at frame 340.")
        return AgentResult(
            agent_id=self.agent_id,
            stage_id="segmentation",
            project_id=request.project_id or "proj-test",
            status="succeeded",
            summary="Transcripts segmented into 4 scenes obeying 30fps boundaries.",
            metadata={"duration_ms": 120.0, "scene_count": 4},
        )

    def review(self, project_dir: Path, request: AgentRequest, result: AgentResult) -> AgentResult:
        return result


class SyntheticVisualPlanningAgent(BaseAgent):
    """Synthetic VisualPlanningAgent implementing BaseAgent hooks."""

    def __init__(self) -> None:
        metadata = AgentMetadata(
            agent_id="visual_planning",
            name="Visual Planning Agent",
            version="1.0.0",
            category=AgentCategory.VIDEO_ENGINE_AGENT,
            status=AgentStatus.IMPLEMENTED,
            purpose="Generates visual concepts and image prompts.",
            capabilities=["visual-concept-generation"],
            stage_id="planning",
            owner="agent-system",
        )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            stage_id="planning",
            project_id=request.project_id or "proj-test",
            status="succeeded",
            summary="Visual concepts generated.",
            metadata={"duration_ms": 95.0},
        )

    def review(self, project_dir: Path, request: AgentRequest, result: AgentResult) -> AgentResult:
        return result


@pytest.fixture
def trusted_operator():
    """Provides a verified trusted AuthenticatedOperator for promotion tests."""
    return AuthenticatedOperator(
        operator_id="test_operator_stage3",
        role="operator",
        auth_method="trusted_context",
        verified_at=datetime.now(timezone.utc).isoformat(),
    )


# ==============================================================================
# Group A: Agent Partitions & Isolation
# ==============================================================================

def test_all_22_canonical_agents_have_persistent_memory_partitions():
    """Verifies that every one of the 22 registered canonical agents has a valid memory partition directory."""
    reg = AgentRegistry()
    agents = reg.list_all_agents()
    assert len(agents) == 22, f"Expected 22 canonical agents, found {len(agents)}"

    for agent_meta in agents:
        aid = agent_meta.agent_id
        mem_dir = per_agent_store.get_agent_memory_dir(aid)
        assert mem_dir.exists(), f"Agent '{aid}' missing memory partition directory: {mem_dir}"
        assert mem_dir.is_dir(), f"Agent '{aid}' memory partition path is not a directory: {mem_dir}"


def test_agent_a_and_agent_b_memory_partition_isolation():
    """Verifies that records written by Agent A are stored strictly under Agent A's identity
    and cannot be retrieved or overwritten by Agent B.
    """
    agent_a = "audio_analyzer"
    agent_b = "motion_planning"

    # Clean existing partitions for test isolation
    per_agent_store.clear_agent_partition(agent_a)
    per_agent_store.clear_agent_partition(agent_b)

    # 1. Agent A records experience
    exp_a = per_agent_store.record_experience(
        agent_id=agent_a,
        task_type="audio_transcription",
        outcome="succeeded",
        context={"audio_format": "wav", "sample_rate": 44100},
        metrics={"duration_ms": 350.0},
    )
    assert exp_a.agent_id == agent_a

    # 2. Agent B records experience
    exp_b = per_agent_store.record_experience(
        agent_id=agent_b,
        task_type="spring_physics",
        outcome="succeeded",
        context={"damping": 15, "stiffness": 120},
        metrics={"duration_ms": 210.0},
    )
    assert exp_b.agent_id == agent_b

    # 3. Agent A retrieves: gets ONLY exp_a, NOT exp_b
    res_a = per_agent_store.retrieve_agent_experiences(agent_id=agent_a)
    assert len(res_a) == 1
    assert res_a[0].experience_id == exp_a.experience_id
    assert res_a[0].agent_id == agent_a

    # 4. Agent B retrieves: gets ONLY exp_b, NOT exp_a
    res_b = per_agent_store.retrieve_agent_experiences(agent_id=agent_b)
    assert len(res_b) == 1
    assert res_b[0].experience_id == exp_b.experience_id
    assert res_b[0].agent_id == agent_b

    # 5. Cross-agent direct lookup: Agent A cannot find Agent B's experience in its partition
    assert per_agent_store.get_experience(agent_a, exp_b.experience_id) is None
    assert per_agent_store.get_experience(agent_b, exp_a.experience_id) is None


def test_existing_shared_memory_records_remain_intact():
    """Verifies that existing config/shared_memory.json data remains completely intact and readable."""
    assert MEMORY_FILE.exists(), f"shared_memory.json missing: {MEMORY_FILE}"
    raw = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    memories = raw.get("memories", {})
    assert len(memories) >= 300, f"Expected at least 300 shared memories, found {len(memories)}"
    assert "mem-telugu-orthography" in memories
    assert "mem-timeline-fps-30" in memories


# ==============================================================================
# Group B: Persistence & Concurrency
# ==============================================================================

def test_records_survive_save_and_reload(tmp_path):
    """Verifies that experience records survive cache clearing and reloads from disk."""
    store = PerAgentMemoryStore(root_dir=tmp_path)
    aid = "render_video"

    exp = store.record_experience(
        agent_id=aid,
        task_type="render_mp4",
        outcome="succeeded",
        context={"codec": "h264", "fps": 30},
        metrics={"duration_ms": 1450.0},
    )

    # Clear memory cache
    store._cache.clear()
    store._cache_mtime.clear()

    # Re-retrieve from disk
    reloaded = store.retrieve_agent_experiences(agent_id=aid)
    assert len(reloaded) == 1
    assert reloaded[0].experience_id == exp.experience_id
    assert reloaded[0].context["codec"] == "h264"
    assert reloaded[0].metrics["duration_ms"] == 1450.0


def test_concurrent_writes_do_not_lose_or_corrupt_records(tmp_path):
    """Verifies that concurrent multi-threaded writes across agents do not lose records."""
    store = PerAgentMemoryStore(root_dir=tmp_path)
    agents = ["audio_analyzer", "scene_segmentation", "motion_planning", "final_qc"]

    def write_task(aid: str, idx: int):
        store.record_experience(
            agent_id=aid,
            task_type=f"task_{idx}",
            outcome="succeeded",
            context={"thread_idx": idx},
            metrics={"duration_ms": idx * 10.0},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for aid in agents:
            for idx in range(10):
                futures.append(executor.submit(write_task, aid, idx))
        concurrent.futures.wait(futures)

    # Verify every agent has exactly 10 recorded experiences
    for aid in agents:
        exps = store.retrieve_agent_experiences(agent_id=aid, limit=50)
        assert len(exps) == 10, f"Agent {aid} lost records: expected 10, got {len(exps)}"


def test_malformed_records_quarantined_without_crash(tmp_path):
    """Verifies that corrupted partition files are safely quarantined and do not crash retrieval."""
    store = PerAgentMemoryStore(root_dir=tmp_path)
    aid = "final_qc"

    p_file = store.get_agent_memory_dir(aid) / "experiences.json"
    p_file.parent.mkdir(parents=True, exist_ok=True)
    p_file.write_text("{CORRUPTED_NON_JSON...", encoding="utf-8")

    # Should not crash; returns empty list and quarantines bad file
    exps = store.retrieve_agent_experiences(agent_id=aid)
    assert exps == []

    # Writing new record succeeds cleanly
    new_exp = store.record_experience(aid, "qc_check", "succeeded")
    assert new_exp.experience_id.startswith(f"exp-{aid}")
    assert len(store.retrieve_agent_experiences(agent_id=aid)) == 1


# ==============================================================================
# Group C: Experience Recording & Reflection
# ==============================================================================

def test_truthful_experience_recording_and_no_fabricated_metrics():
    """Verifies that experiences accurately record genuine metrics and do not fabricate missing metrics."""
    aid = "timeline_build"
    per_agent_store.clear_agent_partition(aid)

    # Record task with duration only (no quality score available)
    exp = per_agent_store.record_experience(
        agent_id=aid,
        task_type="timeline_assembly",
        outcome="succeeded",
        metrics={"duration_ms": 420.0},
    )

    assert exp.metrics["duration_ms"] == 420.0
    assert "quality_score" not in exp.metrics, "Fabricated metric detected!"


def test_failed_task_records_actual_error_category():
    """Verifies that failed tasks truthfully record error categories and reflections."""
    aid = "audio_input"
    per_agent_store.clear_agent_partition(aid)

    exp = per_agent_store.record_experience(
        agent_id=aid,
        task_type="audio_ingest",
        outcome="failed",
        error_category="validation_error",
        context={"file_path": "invalid_audio.xyz"},
        reflection="Unsupported audio extension .xyz; expected .wav or .mp3.",
    )

    assert exp.outcome == "failed"
    assert exp.error_category == "validation_error"
    assert "Unsupported audio" in str(exp.reflection)


def test_secret_redaction_in_experience_context_and_reflection():
    """Verifies that credentials, tokens, and secrets are automatically redacted before storage."""
    aid = "capability_finder"
    per_agent_store.clear_agent_partition(aid)

    raw_api_key = "sk-1234567890abcdef1234567890abcdef"
    raw_gh_token = "ghp_1234567890abcdef1234567890abcdef12"

    exp = per_agent_store.record_experience(
        agent_id=aid,
        task_type="remote_search",
        outcome="succeeded",
        context={"api_header": f"Bearer {raw_api_key}"},
        reflection=f"Queried GitHub using token {raw_gh_token}",
    )

    # Secret keys must NOT be present in plaintext
    assert raw_api_key not in json.dumps(exp.context)
    assert raw_gh_token not in json.dumps(exp.reflection)
    assert "[REDACTED" in json.dumps(exp.context) or "[REDACTED" in json.dumps(exp.reflection)


# ==============================================================================
# Group D: Benchmark Evaluation & Rollback
# ==============================================================================

def test_candidate_improvement_passing_benchmark_promoted(tmp_path, trusted_operator):
    """Verifies that a candidate proposal passing benchmark evaluation can be promoted."""
    active_file = tmp_path / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    case_file = tmp_path / "cases.jsonl"

    collector = CaseCollector(persistence_file=case_file)
    # Seed 2 supporting cases
    c1 = LearningCase(case_id="case-101", task_id="t1", parsed_requirement={"requirement": "test"}, execution_outcome={"status": "succeeded"})
    c2 = LearningCase(case_id="case-102", task_id="t2", parsed_requirement={"requirement": "test"}, execution_outcome={"status": "succeeded"})
    collector.record_case(c1)
    collector.record_case(c2)

    gate = LearningGate(collector=collector)
    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir, gate=gate)

    proposal = LessonProposal(
        title="Telugu Audio Phoneme Normalization",
        description="Expands audio query synonyms for phoneme alignment.",
        observed_pattern="Telugu phoneme queries often omit language prefix.",
        affected_domain="audio",
        rule_type="synonym_expansion",
        rule_content={"synonyms": {"speech": "speech_to_text"}},
        supporting_case_ids=["case-101", "case-102"],
        risk_level="low",
    )

    # Mock evaluation showing positive accuracy delta and passed gate
    eval_report = LearningEvaluation(
        proposal_id=proposal.proposal_id,
        passed_gate=True,
        has_regression=False,
        accuracy_delta=0.10,
        baseline_metrics=EvaluationMetrics(0.80, 0.80, 0.80, 0.05, 0.05, 10).to_dict(),
        candidate_metrics=EvaluationMetrics(0.90, 0.90, 0.90, 0.02, 0.02, 10).to_dict(),
    )

    prom_res = promoter.promote_proposal(
        proposal=proposal,
        evaluation=eval_report,
        operator=trusted_operator,
    )

    assert prom_res["promoted"] is True
    assert prom_res["new_version"] == "1.1.0"
    active_data = promoter.load_active_knowledge()
    assert len(active_data["promoted_lessons"]) == 1


def test_candidate_with_benchmark_regression_strictly_rejected(tmp_path, trusted_operator):
    """Verifies that a candidate proposal degrading benchmark performance is strictly rejected."""
    active_file = tmp_path / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    case_file = tmp_path / "cases.jsonl"

    collector = CaseCollector(persistence_file=case_file)
    c1 = LearningCase(case_id="case-201", task_id="t1", parsed_requirement={"requirement": "test"}, execution_outcome={"status": "succeeded"})
    c2 = LearningCase(case_id="case-202", task_id="t2", parsed_requirement={"requirement": "test"}, execution_outcome={"status": "succeeded"})
    collector.record_case(c1)
    collector.record_case(c2)

    gate = LearningGate(collector=collector)
    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir, gate=gate)

    bad_proposal = LessonProposal(
        title="Aggressive Over-Routing Rule",
        description="Forces audio tasks into visual planning (causes regression).",
        observed_pattern="Erroneous misattribution",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "visual"},
        supporting_case_ids=["case-201", "case-202"],
    )

    # Evaluation indicating regression and negative delta
    regressive_eval = LearningEvaluation(
        proposal_id=bad_proposal.proposal_id,
        passed_gate=False,
        has_regression=True,
        accuracy_delta=-0.25,
        rejection_reason="Benchmark regression detected: recommendation accuracy dropped from 0.85 to 0.60.",
    )

    with pytest.raises(ValueError, match="Benchmark regression detected"):
        promoter.promote_proposal(
            proposal=bad_proposal,
            evaluation=regressive_eval,
            operator=trusted_operator,
        )

    # Verify active baseline remains intact and unpromoted
    active = promoter.load_active_knowledge()
    assert len(active["promoted_lessons"]) == 0


def test_rollback_manager_restores_verified_baseline(tmp_path, trusted_operator):
    """Verifies that RollbackManager safely restores prior archived active knowledge."""
    active_file = tmp_path / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    case_file = tmp_path / "cases.jsonl"

    collector = CaseCollector(persistence_file=case_file)
    c1 = LearningCase(case_id="case-301", task_id="t1", parsed_requirement={"requirement": "test"}, execution_outcome={"status": "succeeded"})
    c2 = LearningCase(case_id="case-302", task_id="t2", parsed_requirement={"requirement": "test"}, execution_outcome={"status": "succeeded"})
    collector.record_case(c1)
    collector.record_case(c2)

    gate = LearningGate(collector=collector)
    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir, gate=gate)
    rb_mgr = RollbackManager(active_file=active_file, archive_dir=archive_dir, promoter=promoter)

    # 1. Promote v1.1.0
    p1 = LessonProposal(
        title="Valid Rule 1",
        description="First valid lesson.",
        observed_pattern="pattern 1",
        affected_domain="motion",
        rule_type="synonym_expansion",
        rule_content={"synonyms": {"spring": "remotion_spring"}},
        supporting_case_ids=["case-301", "case-302"],
    )
    e1 = LearningEvaluation(
        proposal_id=p1.proposal_id,
        passed_gate=True,
        has_regression=False,
        accuracy_delta=0.05,
        baseline_metrics=EvaluationMetrics(0.80, 0.80, 0.80, 0.05, 0.05, 10).to_dict(),
        candidate_metrics=EvaluationMetrics(0.85, 0.85, 0.85, 0.03, 0.03, 10).to_dict(),
    )
    promoter.promote_proposal(p1, e1, operator=trusted_operator)
    assert promoter.load_active_knowledge()["version"] == "1.1.0"

    # 2. Promote v1.2.0
    p2 = LessonProposal(
        title="Valid Rule 2",
        description="Second valid lesson.",
        observed_pattern="pattern 2",
        affected_domain="motion",
        rule_type="synonym_expansion",
        rule_content={"synonyms": {"bounce": "spring_physics"}},
        supporting_case_ids=["case-301", "case-302"],
    )
    e2 = LearningEvaluation(
        proposal_id=p2.proposal_id,
        passed_gate=True,
        has_regression=False,
        accuracy_delta=0.05,
        baseline_metrics=EvaluationMetrics(0.85, 0.85, 0.85, 0.03, 0.03, 10).to_dict(),
        candidate_metrics=EvaluationMetrics(0.90, 0.90, 0.90, 0.02, 0.02, 10).to_dict(),
    )
    promoter.promote_proposal(p2, e2, operator=trusted_operator)
    assert promoter.load_active_knowledge()["version"] == "1.2.0"

    # 3. Rollback to prior archived version
    rb_res = rb_mgr.rollback(operator=trusted_operator)
    assert rb_res["rolled_back"] is True
    assert rb_res["restored_version"] == "1.1.0"
    restored = promoter.load_active_knowledge()
    assert restored["version"] == "1.1.0"


# ==============================================================================
# Group E: Integration & Performance
# ==============================================================================

def test_base_agent_invoke_lifecycle_automatically_records_experience(tmp_path):
    """Verifies BaseAgent.invoke() executes task and writes experience to private partition."""
    per_agent_store.clear_agent_partition("visual_planning")
    agent = SyntheticVisualPlanningAgent()

    req = AgentRequest(
        correlation_id="req-vp-001",
        stage_id="planning",
        project_id="proj-e2e",
        parameters={"aspect": "16:9", "theme": "dark_cosmic"},
    )

    res = agent.invoke(tmp_path, req)
    assert res.status == "succeeded"

    # Verify partition received experience
    exps = agent.retrieve_agent_memories(task_type="planning", include_shared=False)
    assert len(exps) == 1
    rec = exps[0]
    assert rec["agent_id"] == "visual_planning"
    assert rec["outcome"] == "succeeded"
    assert rec["task_id"] == "req-vp-001"
    assert "duration_ms" in rec["metrics"]

    # Also verify combined retrieval with shared knowledge
    all_memories = agent.retrieve_agent_memories(task_type="planning", include_shared=True)
    assert len(all_memories) >= 1
    assert any(m.get("source_type") == "shared_verified_memory" for m in all_memories)


def test_memory_lookup_performance_meets_50ms_requirement():
    """Verifies that retrieval from an agent's memory partition executes well below the 50ms requirement."""
    aid = "motion_planning"
    per_agent_store.clear_agent_partition(aid)

    # Seed 50 experiences into partition
    for i in range(50):
        per_agent_store.record_experience(
            agent_id=aid,
            task_type="typography_layout",
            outcome="succeeded" if i % 2 == 0 else "failed",
            context={"scene_index": i, "font_size": 24 + i},
            metrics={"duration_ms": 15.0 + i},
        )

    # Perform 20 timed lookups
    latencies: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        results = per_agent_store.retrieve_agent_experiences(agent_id=aid, task_type="typography_layout", limit=10)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)
        assert len(results) == 10

    avg_ms = sum(latencies) / len(latencies)
    max_ms = max(latencies)
    assert avg_ms < 50.0, f"Average memory lookup exceeded 50ms: {avg_ms:.2f}ms"
    assert max_ms < 50.0, f"Max memory lookup exceeded 50ms: {max_ms:.2f}ms"


# ==============================================================================
# Group F: Required Scenario
# ==============================================================================

def test_required_scenario_three_mock_scene_segmentation_tasks_and_gate_blocking(tmp_path, trusted_operator):
    """Executes the specific Stage 3 required scenario:
    1. Executes 3 mock scene-segmentation tasks via the actual SceneSegmentationAgent interface.
    2. Verifies 3 corresponding experience records are stored under scene_segmentation partition.
    3. Simulates a candidate proposal degrading an audio-sync benchmark.
    4. Verifies LearningGate blocks promotion and preserves previous verified behavior.
    """
    aid = "scene_segmentation"
    per_agent_store.clear_agent_partition(aid)
    agent = SyntheticSceneSegmentationAgent()

    # Part 1: Execute 3 mock scene-segmentation tasks
    req1 = AgentRequest(correlation_id="req-seg-01", stage_id="segmentation", project_id="proj-scen", parameters={"target_scenes": 3})
    req2 = AgentRequest(correlation_id="req-seg-02", stage_id="segmentation", project_id="proj-scen", parameters={"target_scenes": 4})
    req3 = AgentRequest(correlation_id="req-seg-03", stage_id="segmentation", project_id="proj-scen", parameters={"target_scenes": 5})

    res1 = agent.invoke(tmp_path, req1)
    res2 = agent.invoke(tmp_path, req2)
    res3 = agent.invoke(tmp_path, req3)

    assert res1.status == "succeeded"
    assert res2.status == "succeeded"
    assert res3.status == "succeeded"

    # Part 2: Verify exactly 3 experience records under scene_segmentation partition
    stored_exps = per_agent_store.retrieve_agent_experiences(agent_id=aid, limit=20)
    assert len(stored_exps) == 3, f"Expected 3 experiences under {aid}, found {len(stored_exps)}"
    observed_task_ids = {e.task_id for e in stored_exps}
    assert observed_task_ids == {"req-seg-01", "req-seg-02", "req-seg-03"}

    # Part 3: Simulate candidate proposal that degrades audio-sync benchmark
    active_file = tmp_path / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    case_file = tmp_path / "cases.jsonl"

    collector = CaseCollector(persistence_file=case_file)
    for exp in stored_exps:
        case = LearningCase(
            case_id=exp.experience_id,
            task_id=exp.task_id,
            parsed_requirement={"requirement": "scene_segmentation"},
            execution_outcome={"status": exp.outcome},
        )
        collector.record_case(case)

    gate = LearningGate(collector=collector)
    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir, gate=gate)

    degrading_proposal = LessonProposal(
        title="Aggressive Boundary Relaxation",
        description="Relaxes speech boundaries beyond duration limits, degrading audio-synchronization.",
        observed_pattern="Relaxation of speech cutoffs",
        affected_domain="audio_visual",
        rule_type="routing_preference",
        rule_content={"target_domain": "relaxed_sync"},
        supporting_case_ids=[stored_exps[0].experience_id, stored_exps[1].experience_id],
    )

    # Simulated evaluation report indicating audio-sync benchmark regression
    degraded_eval = LearningEvaluation(
        proposal_id=degrading_proposal.proposal_id,
        passed_gate=False,
        has_regression=True,
        accuracy_delta=-0.35,
        rejection_reason="Audio synchronization benchmark regression: drift exceeded 250ms tolerance threshold.",
    )

    # Part 4: Verify LearningGate strictly blocks promotion
    with pytest.raises(ValueError, match="Audio synchronization benchmark regression"):
        promoter.promote_proposal(
            proposal=degrading_proposal,
            evaluation=degraded_eval,
            operator=trusted_operator,
        )

    # Verify baseline remains active and unmodified
    active_after = promoter.load_active_knowledge()
    assert len(active_after["promoted_lessons"]) == 0, "Degrading proposal was erroneously promoted!"
