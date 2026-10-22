"""Genuine cross-process concurrency and transactional locking tests for Knowledge Store.

Verifies that separate operating-system processes (independent Python interpreters with their
own PIDs and memory spaces) safely coordinate concurrent promotions and rollbacks using StoreLock.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def test_cross_process_concurrent_promotions_no_lost_updates(tmp_path: Path):
    """Separate OS processes concurrently promoting distinct lessons coordinate via StoreLock without lost updates."""
    active_file = tmp_path / "active" / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    num_processes = 4

    worker_script = tmp_path / "promotion_worker.py"
    worker_code = """import sys, json, os, time
from pathlib import Path
from SYSTEM.agents.capability_finder.learning.knowledge_promoter import KnowledgePromoter
from SYSTEM.agents.capability_finder.learning.lesson_generator import LessonProposal
from SYSTEM.agents.capability_finder.learning.lesson_evaluator import LearningEvaluation
from SYSTEM.agents.capability_finder.learning.authorization import AuthenticatedOperator

active_file = Path(sys.argv[1])
archive_dir = Path(sys.argv[2])
worker_id = int(sys.argv[3])

promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir)

hex_id = f"prop_{worker_id + 10:012x}"
prop = LessonProposal(
    proposal_id=hex_id,
    title=f"Worker Proposal {worker_id}",
    description="desc",
    observed_pattern="pattern",
    affected_domain=f"proc_domain_{worker_id}",
    rule_type="routing_preference",
    rule_content={"domain": f"proc_domain_{worker_id}", "worker_id": worker_id},
    supporting_case_ids=["c1", "c2"],
)
eval_rep = LearningEvaluation(
    proposal_id=hex_id,
    baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
    candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
    accuracy_delta=0.1,
    has_regression=False,
    passed_gate=True,
)
op = AuthenticatedOperator(
    operator_id=f"worker_proc_{worker_id}",
    role="lead_operator",
    auth_method="trusted_context",
    verified_at="2026-10-17T08:00:00Z",
)

# Concurrently promote
res = promoter.promote_proposal(prop, eval_rep, operator=op, check_case_existence=False)
print(f"SUCCESS worker {worker_id} version {res['new_version']}")
"""
    worker_script.write_text(worker_code, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    procs = [
        subprocess.Popen(
            [sys.executable, str(worker_script), str(active_file), str(archive_dir), str(i)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(num_processes)
    ]

    for p in procs:
        stdout, stderr = p.communicate(timeout=20)
        assert p.returncode == 0, f"Process failed with code {p.returncode}: {stderr}"
        assert "SUCCESS" in stdout

    # Verify final active knowledge
    assert active_file.exists()
    final_knowledge = json.loads(active_file.read_text(encoding="utf-8"))

    # Monotonic version bump: 1.0.0 + 4 updates = 1.4.0
    assert final_knowledge["version"] == f"1.{num_processes}.0"
    assert len(final_knowledge["promoted_lessons"]) == num_processes

    # All domains present without lost updates
    for i in range(num_processes):
        assert f"proc_domain_{i}" in final_knowledge["routing_preferences"]

    # All archive snapshots are valid JSON
    archives = list(archive_dir.glob("*.json"))
    assert len(archives) >= num_processes
    for a in archives:
        data = json.loads(a.read_text(encoding="utf-8"))
        assert "version" in data


def test_cross_process_promotion_vs_rollback_serialization(tmp_path: Path):
    """Separate OS processes performing promotions and rollbacks concurrently serialize cleanly."""
    active_file = tmp_path / "active" / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    worker_script = tmp_path / "lifecycle_worker.py"
    worker_code = """import sys, json, os, time
from pathlib import Path
from SYSTEM.agents.capability_finder.learning.knowledge_promoter import KnowledgePromoter
from SYSTEM.agents.capability_finder.learning.rollback_manager import RollbackManager
from SYSTEM.agents.capability_finder.learning.lesson_generator import LessonProposal
from SYSTEM.agents.capability_finder.learning.lesson_evaluator import LearningEvaluation
from SYSTEM.agents.capability_finder.learning.authorization import AuthenticatedOperator

active_file = Path(sys.argv[1])
archive_dir = Path(sys.argv[2])
action = sys.argv[3]
proc_id = int(sys.argv[4])

promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir)
rollback_mgr = RollbackManager(active_file=active_file, archive_dir=archive_dir, promoter=promoter)

op = AuthenticatedOperator(
    operator_id=f"lifecycle_proc_{proc_id}",
    role="system_admin",
    auth_method="trusted_context",
    verified_at="2026-10-17T08:00:00Z",
)

if action == "promote":
    hex_id = f"prop_{proc_id + 50:012x}"
    prop = LessonProposal(
        proposal_id=hex_id,
        title=f"Lifecycle Proposal {proc_id}",
        description="desc",
        observed_pattern="pattern",
        affected_domain=f"lifecycle_domain_{proc_id}",
        rule_type="routing_preference",
        rule_content={"domain": f"lifecycle_domain_{proc_id}"},
        supporting_case_ids=["c1", "c2"],
    )
    eval_rep = LearningEvaluation(
        proposal_id=hex_id,
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )
    res = promoter.promote_proposal(prop, eval_rep, operator=op, check_case_existence=False)
    print(f"PROMOTED version {res['new_version']}")
elif action == "rollback":
    try:
        res = rollback_mgr.rollback(operator=op)
        print(f"ROLLED_BACK restored {res['restored_version']}")
    except FileNotFoundError:
        print("NO_ARCHIVES_YET")
"""
    worker_script.write_text(worker_code, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    # 1. Initialize baseline promotion v1.1.0 in process 0
    init_proc = subprocess.Popen(
        [sys.executable, str(worker_script), str(active_file), str(archive_dir), "promote", "0"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = init_proc.communicate(timeout=15)
    assert init_proc.returncode == 0
    assert "PROMOTED version 1.1.0" in stdout

    # 2. Concurrently run 2 promoters and 2 rollbacks as separate OS processes
    commands = [
        ("promote", 1),
        ("rollback", 2),
        ("promote", 3),
        ("rollback", 4),
    ]

    procs = [
        subprocess.Popen(
            [sys.executable, str(worker_script), str(active_file), str(archive_dir), action, str(proc_id)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for action, proc_id in commands
    ]

    for p in procs:
        stdout, stderr = p.communicate(timeout=25)
        assert p.returncode == 0, f"Process exited with error {p.returncode}: {stderr}"

    # 3. Verify state integrity
    assert active_file.exists()
    final_data = json.loads(active_file.read_text(encoding="utf-8"))
    assert "version" in final_data
    assert isinstance(final_data["promoted_lessons"], list)

    archives = list(archive_dir.glob("*.json"))
    assert len(archives) >= 2
    for a in archives:
        arc_data = json.loads(a.read_text(encoding="utf-8"))
        assert "version" in arc_data


def test_cross_process_failed_operation_preserves_valid_active_state(tmp_path: Path):
    """If an operation fails in a separate OS process, the active store remains in its prior valid state."""
    active_file = tmp_path / "active" / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    worker_script = tmp_path / "fail_worker.py"
    worker_code = """import sys, json, os
from pathlib import Path
from SYSTEM.agents.capability_finder.learning.knowledge_promoter import KnowledgePromoter
from SYSTEM.agents.capability_finder.learning.lesson_generator import LessonProposal
from SYSTEM.agents.capability_finder.learning.lesson_evaluator import LearningEvaluation
from SYSTEM.agents.capability_finder.learning.authorization import AuthenticatedOperator

active_file = Path(sys.argv[1])
archive_dir = Path(sys.argv[2])
mode = sys.argv[3]

promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir)

if mode == "valid":
    prop = LessonProposal(
        proposal_id="prop_000000000099",
        title="Valid Proposal",
        description="desc",
        observed_pattern="pat",
        affected_domain="valid_domain",
        rule_type="routing_preference",
        rule_content={"domain": "valid_domain"},
        supporting_case_ids=["c1", "c2"],
    )
    eval_rep = LearningEvaluation(
        proposal_id="prop_000000000099",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )
    op = AuthenticatedOperator(
        operator_id="admin_valid",
        role="system_admin",
        auth_method="trusted_context",
        verified_at="2026-10-17T08:00:00Z",
    )
    res = promoter.promote_proposal(prop, eval_rep, operator=op, check_case_existence=False)
    print("VALID_PROMOTED")

elif mode == "spoof_fail":
    # Attempt unauthorized role-spoofing without credentials -> MUST FAIL
    prop_bad = LessonProposal(
        proposal_id="prop_000000000098",
        title="Bad Proposal",
        description="desc",
        observed_pattern="pat",
        affected_domain="bad_domain",
        rule_type="routing_preference",
        rule_content={"domain": "bad_domain"},
        supporting_case_ids=["c1", "c2"],
    )
    eval_bad = LearningEvaluation(
        proposal_id="prop_000000000098",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )
    try:
        promoter.promote_proposal(prop_bad, eval_bad, authorized_by="system_admin", check_case_existence=False)
        print("UNEXPECTED_SUCCESS")
    except ValueError as e:
        print(f"EXPECTED_FAILURE: {e}")
        sys.exit(42)
"""
    worker_script.write_text(worker_code, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    # 1. Step 1: Valid promotion establishes state v1.1.0
    p1 = subprocess.Popen(
        [sys.executable, str(worker_script), str(active_file), str(archive_dir), "valid"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout1, _ = p1.communicate(timeout=15)
    assert p1.returncode == 0
    assert "VALID_PROMOTED" in stdout1

    data_v1 = json.loads(active_file.read_text(encoding="utf-8"))
    assert data_v1["version"] == "1.1.0"
    archives_v1_count = len(list(archive_dir.glob("*.json")))

    # 2. Step 2: Failing/rejected process in separate OS process
    p2 = subprocess.Popen(
        [sys.executable, str(worker_script), str(active_file), str(archive_dir), "spoof_fail"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout2, _ = p2.communicate(timeout=15)
    assert p2.returncode == 42
    assert "EXPECTED_FAILURE" in stdout2

    # 3. Step 3: Verify active state is unchanged and uncorrupted
    data_after = json.loads(active_file.read_text(encoding="utf-8"))
    assert data_after["version"] == "1.1.0"
    assert "valid_domain" in data_after["routing_preferences"]
    assert "bad_domain" not in data_after["routing_preferences"]
    assert len(list(archive_dir.glob("*.json"))) == archives_v1_count
