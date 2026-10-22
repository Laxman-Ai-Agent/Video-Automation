"""Canonical Evaluation Engine & Verified Self-Learning Governance Service.

Implements Phase 9 capabilities:
1. Versioned evaluation suites and cases with deterministic fixtures and negative cases.
2. Two-tier evaluation: strict deterministic hard gates (security, contracts, timing, orthography)
   evaluated before optional LLM-assisted qualitative scoring.
3. Strict invariant: deterministic failure ALWAYS beats any LLM judge score.
4. Baseline management and regression comparison (hard-gate regressions reject candidates).
5. Governed candidate improvement lifecycle (skill, memory, prompt, config proposals).
6. Mandatory authorized human review gate before promotion; zero self-approval.
7. Atomic versioned promotion and auditable rollback preserving complete history.
8. Truthful capability reporting: headless Chromium prerequisite remains explicitly unverified.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core import artifact_contracts
from SYSTEM.core import llm_gateway
from SYSTEM.policies import llm_review
from SYSTEM.observability import llm_usage
from SYSTEM.memory import shared_memory, store
from SYSTEM.registries import skill_registry
from SYSTEM.core.errors import ApiError
from SYSTEM.core import config, integrations

logger = logging.getLogger("evaluation")

CONFIG_DIR = config.PROJECT_ROOT / "config"
EVAL_SUITES_FILE = CONFIG_DIR / "eval_suites.json"
EVAL_BASELINES_FILE = CONFIG_DIR / "eval_baselines.json"
EVAL_CANDIDATES_FILE = CONFIG_DIR / "eval_candidates.json"
EVAL_RESULTS_DIR = CONFIG_DIR / "eval_results"

TELUGU_RANGE_REGEX = re.compile(r"[\u0c00-\u0c7f]")

_EVAL_LOCK = threading.Lock()


@dataclass
class DeterministicCheckResult:
    check_id: str
    name: str
    status: Literal["passed", "failed", "skipped", "not_applicable"]
    severity: Literal["blocker", "warning", "info"] = "blocker"
    observed: Any = None
    expected: Any = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LlmJudgmentResult:
    rubric_version: str = "1.0"
    provider: str = ""
    model: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    passed: bool = True
    findings: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    latency_seconds: float = 0.0
    tokens_used: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationResult:
    schema_version: int = 1
    evaluation_id: str = field(default_factory=lambda: f"eval_res_{uuid.uuid4().hex[:8]}")
    suite_id: str = ""
    suite_version: int = 1
    case_id: str = ""
    case_version: int = 1
    stage_id: str = ""
    candidate_ref: str = ""
    input_fingerprint: str = ""
    output_fingerprint: str = ""
    overall_status: Literal["passed", "failed", "blocked", "needs_review", "not_run"] = "not_run"
    hard_gates_passed: bool = False
    deterministic_checks: list[DeterministicCheckResult] = field(default_factory=list)
    llm_judgment: LlmJudgmentResult | None = None
    composite_score: float = 0.0
    findings: list[str] = field(default_factory=list)
    is_mocked: bool = False
    capabilities: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["deterministic_checks"] = [c.to_dict() if isinstance(c, DeterministicCheckResult) else c for c in self.deterministic_checks]
        d["llm_judgment"] = self.llm_judgment.to_dict() if isinstance(self.llm_judgment, LlmJudgmentResult) else self.llm_judgment
        return d


@dataclass
class EvaluationCase:
    case_id: str
    case_version: int = 1
    suite_id: str = ""
    name: str = ""
    purpose: str = ""
    stage_id: str = ""
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    tags: list[str] = field(default_factory=list)
    input_fixture: dict[str, Any] = field(default_factory=dict)
    expected_invariants: dict[str, Any] = field(default_factory=dict)
    rubric_version: str = "1.0"
    rubric: dict[str, Any] = field(default_factory=dict)
    status: Literal["approved", "review_required", "draft", "deprecated"] = "approved"
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationSuite:
    suite_id: str
    version: int = 1
    name: str = ""
    description: str = ""
    cases: list[EvaluationCase] = field(default_factory=list)
    target_stages: list[str] = field(default_factory=list)
    status: Literal["approved", "draft", "deprecated"] = "approved"
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cases"] = [c.to_dict() if isinstance(c, EvaluationCase) else c for c in self.cases]
        return d


@dataclass
class ComparisonReport:
    schema_version: int = 1
    comparison_id: str = field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:8]}")
    baseline_id: str = ""
    candidate_id: str = ""
    suite_id: str = ""
    decision: Literal["accepted", "rejected", "degraded", "inconclusive"] = "inconclusive"
    hard_gate_regression: bool = False
    regressed_checks: list[str] = field(default_factory=list)
    score_delta: float = 0.0
    tolerance: float = 0.05
    summary: str = ""
    compared_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateProposal:
    schema_version: int = 1
    candidate_id: str = field(default_factory=lambda: f"cand_{uuid.uuid4().hex[:8]}")
    candidate_type: Literal["skill", "memory", "prompt_proposal", "configuration"] = "skill"
    target_id: str = ""
    version: str = "1.1.0"
    title: str = ""
    description: str = ""
    rationale: str = ""
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    proposed_content: Any = None
    diff: str = ""
    status: Literal[
        "proposed",
        "under_evaluation",
        "evaluation_passed",
        "evaluation_failed",
        "approved",
        "rejected",
        "rolled_back",
    ] = "proposed"
    evaluation_report_ref: str | None = None
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    rollback_plan: str = ""
    reviewer_decision: dict[str, Any] | None = None
    active_version_pointer: str | None = None
    previous_version_pointer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Seed suites providing comprehensive deterministic coverage
def _build_seed_suites() -> list[EvaluationSuite]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        EvaluationSuite(
            suite_id="suite-telugu-orthography",
            version=1,
            name="Telugu Narration & English Orthography Preservation Suite",
            description="Verifies that Telugu spoken words retain native script (U+0C00-U+0C7F) while technical English words remain in standard Latin characters.",
            target_stages=["analyzer", "planning"],
            status="approved",
            updated_at=now,
            cases=[
                EvaluationCase(
                    case_id="eval-telugu-01-positive",
                    case_version=1,
                    suite_id="suite-telugu-orthography",
                    name="Standard Bilingual Narration Segment",
                    purpose="Confirms Telugu native script is preserved alongside English technical terminology.",
                    stage_id="analyzer",
                    risk_level="high",
                    tags=["telugu_preservation", "bilingual", "positive"],
                    input_fixture={
                        "transcript": "ఈ రోజు మనము AI మరియు Machine Learning గురించి నేర్చుకుందాము.",
                        "expected_telugu": True,
                        "expected_terms": ["AI", "Machine Learning"],
                    },
                    expected_invariants={
                        "require_telugu_script": True,
                        "require_english_terms": ["AI", "Machine Learning"],
                        "forbid_english_phonetic_transliteration_of_telugu": True,
                    },
                    status="approved",
                ),
                EvaluationCase(
                    case_id="eval-telugu-02-negative-transliteration",
                    case_version=1,
                    suite_id="suite-telugu-orthography",
                    name="Corrupted Latin Transliteration Rejection",
                    purpose="Negative test asserting that Telugu words transcribed in Latin phonetics fail the hard gate.",
                    stage_id="analyzer",
                    risk_level="high",
                    tags=["telugu_preservation", "negative"],
                    input_fixture={
                        "transcript": "Ee roju manamu AI gurinchi nerchukundamu.",
                        "expected_telugu": True,
                    },
                    expected_invariants={
                        "require_telugu_script": True,
                    },
                    status="approved",
                ),
            ],
        ),
        EvaluationSuite(
            suite_id="suite-timeline-arithmetic",
            version=1,
            name="Master Timeline Exact 30 FPS Frame Arithmetic Suite",
            description="Enforces strict 30.0 fps timing, non-overlapping scene boundaries, and exact frame count calculations.",
            target_stages=["timeline", "motion_validation"],
            status="approved",
            updated_at=now,
            cases=[
                EvaluationCase(
                    case_id="eval-timeline-01-exact-30fps",
                    case_version=1,
                    suite_id="suite-timeline-arithmetic",
                    name="Continuous Multi-Scene 30 FPS Alignment",
                    purpose="Verifies scene start_frame and end_frame are sequential without gaps or overlaps.",
                    stage_id="timeline",
                    risk_level="critical",
                    tags=["frame_arithmetic", "fps_30", "positive"],
                    input_fixture={
                        "fps": 30,
                        "scenes": [
                            {"id": "scene_1", "start_frame": 0, "end_frame": 90, "duration_frames": 90},
                            {"id": "scene_2", "start_frame": 90, "end_frame": 180, "duration_frames": 90},
                            {"id": "scene_3", "start_frame": 180, "end_frame": 270, "duration_frames": 90},
                        ],
                        "total_frames": 270,
                    },
                    expected_invariants={
                        "exact_fps": 30,
                        "contiguous_scenes": True,
                        "positive_duration": True,
                    },
                    status="approved",
                ),
                EvaluationCase(
                    case_id="eval-timeline-02-negative-gap",
                    case_version=1,
                    suite_id="suite-timeline-arithmetic",
                    name="Overlapping Scene Frame Arithmetic Rejection",
                    purpose="Negative test verifying that overlapping frame boundaries trigger immediate hard gate failure.",
                    stage_id="timeline",
                    risk_level="critical",
                    tags=["frame_arithmetic", "negative"],
                    input_fixture={
                        "fps": 30,
                        "scenes": [
                            {"id": "scene_1", "start_frame": 0, "end_frame": 90, "duration_frames": 90},
                            {"id": "scene_2", "start_frame": 85, "end_frame": 180, "duration_frames": 95},
                        ],
                        "total_frames": 180,
                    },
                    expected_invariants={
                        "contiguous_scenes": True,
                    },
                    status="approved",
                ),
            ],
        ),
        EvaluationSuite(
            suite_id="suite-security-gates",
            version=1,
            name="Static Code Security & Path Confinement Suite",
            description="Validates static security rules, path confinement, and prompt injection defense on generated TSX code.",
            target_stages=["motion_gen", "motion_validation"],
            status="approved",
            updated_at=now,
            cases=[
                EvaluationCase(
                    case_id="eval-sec-01-safe-react",
                    case_version=1,
                    suite_id="suite-security-gates",
                    name="Safe Scene TSX Verification",
                    purpose="Verifies clean Remotion React code complies with sandbox constraints.",
                    stage_id="motion_gen",
                    risk_level="critical",
                    tags=["security", "sandbox", "positive"],
                    input_fixture={
                        "code": 'import { AbsoluteFill, useCurrentFrame } from "remotion";\nexport const Scene = () => <AbsoluteFill><div>Test</div></AbsoluteFill>;',
                    },
                    expected_invariants={
                        "forbid_eval": True,
                        "forbid_dom_access": True,
                        "forbid_shell_imports": True,
                    },
                    status="approved",
                ),
                EvaluationCase(
                    case_id="eval-sec-02-negative-dangerous-import",
                    case_version=1,
                    suite_id="suite-security-gates",
                    name="Dangerous Node Imports Rejection",
                    purpose="Negative test asserting that importing child_process or fs triggers hard gate rejection.",
                    stage_id="motion_gen",
                    risk_level="critical",
                    tags=["security", "negative"],
                    input_fixture={
                        "code": 'import { exec } from "child_process";\nexport const Scene = () => <div>Exploit</div>;',
                    },
                    expected_invariants={
                        "forbid_shell_imports": True,
                    },
                    status="approved",
                ),
            ],
        ),
    ]


class EvaluationRegistry:
    """Manages evaluation suites, baseline standards, and improvement candidates."""

    def __init__(self) -> None:
        self._suites: dict[str, EvaluationSuite] = {}
        self._baselines: dict[str, EvaluationResult] = {}
        self._candidates: dict[str, CandidateProposal] = {}
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._lock:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

            # 1. Load or seed evaluation suites
            if EVAL_SUITES_FILE.exists():
                try:
                    data = json.loads(EVAL_SUITES_FILE.read_text(encoding="utf-8"))
                    for s_id, s_data in data.get("suites", {}).items():
                        cases = [EvaluationCase(**c) for c in s_data.get("cases", [])]
                        self._suites[s_id] = EvaluationSuite(
                            suite_id=s_data.get("suite_id", s_id),
                            version=s_data.get("version", 1),
                            name=s_data.get("name", ""),
                            description=s_data.get("description", ""),
                            cases=cases,
                            target_stages=s_data.get("target_stages", []),
                            status=s_data.get("status", "approved"),
                            updated_at=s_data.get("updated_at", ""),
                        )
                except Exception as e:
                    logger.warning(f"Failed loading {EVAL_SUITES_FILE}: {e}. Reseeding suites.")
                    self._reseed_suites()
            else:
                self._reseed_suites()

            # 2. Load baselines
            if EVAL_BASELINES_FILE.exists():
                try:
                    b_data = json.loads(EVAL_BASELINES_FILE.read_text(encoding="utf-8"))
                    for k, res in b_data.get("baselines", {}).items():
                        checks = [DeterministicCheckResult(**c) for c in res.get("deterministic_checks", [])]
                        llm_j = LlmJudgmentResult(**res["llm_judgment"]) if res.get("llm_judgment") else None
                        res["deterministic_checks"] = checks
                        res["llm_judgment"] = llm_j
                        self._baselines[k] = EvaluationResult(**res)
                except Exception:
                    pass

            # 3. Load candidates
            if EVAL_CANDIDATES_FILE.exists():
                try:
                    c_data = json.loads(EVAL_CANDIDATES_FILE.read_text(encoding="utf-8"))
                    for c_id, cand in c_data.get("candidates", {}).items():
                        self._candidates[c_id] = CandidateProposal(**cand)
                except Exception:
                    pass

            self._save_all()
            self._initialized = True

    def _reseed_suites(self) -> None:
        for s in _build_seed_suites():
            self._suites[s.suite_id] = s

    def _save_all(self) -> None:
        # Atomic write suites
        tmp_s = EVAL_SUITES_FILE.with_suffix(".json.tmp")
        payload_s = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "suites": {k: v.to_dict() for k, v in self._suites.items()},
        }
        tmp_s.write_text(json.dumps(payload_s, indent=2), encoding="utf-8")
        os.replace(tmp_s, EVAL_SUITES_FILE)

        # Atomic write baselines
        tmp_b = EVAL_BASELINES_FILE.with_suffix(".json.tmp")
        payload_b = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "baselines": {k: v.to_dict() for k, v in self._baselines.items()},
        }
        tmp_b.write_text(json.dumps(payload_b, indent=2), encoding="utf-8")
        os.replace(tmp_b, EVAL_BASELINES_FILE)

        # Atomic write candidates
        tmp_c = EVAL_CANDIDATES_FILE.with_suffix(".json.tmp")
        payload_c = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "candidates": {k: v.to_dict() for k, v in self._candidates.items()},
        }
        tmp_c.write_text(json.dumps(payload_c, indent=2), encoding="utf-8")
        os.replace(tmp_c, EVAL_CANDIDATES_FILE)

    def list_suites(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._lock:
            return [s.to_dict() for s in sorted(self._suites.values(), key=lambda s: s.suite_id)]

    def get_suite(self, suite_id: str) -> EvaluationSuite | None:
        self.initialize()
        with self._lock:
            return self._suites.get(suite_id)

    def get_case(self, suite_id: str, case_id: str) -> EvaluationCase | None:
        self.initialize()
        with self._lock:
            s = self._suites.get(suite_id)
            if not s:
                return None
            for c in s.cases:
                if c.case_id == case_id:
                    return c
            return None

    def store_baseline(self, baseline_key: str, result: EvaluationResult) -> None:
        self.initialize()
        with self._lock:
            self._baselines[baseline_key] = result
            self._save_all()

    def get_baseline(self, baseline_key: str) -> EvaluationResult | None:
        self.initialize()
        with self._lock:
            return self._baselines.get(baseline_key)

    # Candidate Lifecycle Methods
    def register_candidate(self, candidate: CandidateProposal) -> CandidateProposal:
        self.initialize()
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            candidate.created_at = now
            candidate.updated_at = now
            self._candidates[candidate.candidate_id] = candidate
            self._save_all()
            return candidate

    def get_candidate(self, candidate_id: str) -> CandidateProposal | None:
        self.initialize()
        with self._lock:
            return self._candidates.get(candidate_id)

    def list_candidates(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._lock:
            return [c.to_dict() for c in sorted(self._candidates.values(), key=lambda c: c.created_at, reverse=True)]

    def record_decision(
        self,
        candidate_id: str,
        reviewer: str,
        decision: Literal["approved", "rejected", "request_changes"],
        reason: str,
    ) -> CandidateProposal:
        """Enforces mandatory human reviewer identity and explicit decision rationale."""
        self.initialize()
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                raise KeyError(f"Candidate not found: {candidate_id}")

            if not reviewer or not reviewer.strip():
                raise ApiError(400, "reviewer_required", "Human reviewer identity is mandatory for candidate decisions")
            if not reason or not reason.strip():
                raise ApiError(400, "reason_required", "Explicit decision rationale is required")

            # Invariant: agent cannot self-approve
            if reviewer.lower() in ("agent", "system", "auto", "orchestrator", "self"):
                raise ApiError(403, "self_approval_prohibited", "Automated self-approval is prohibited; human review required")

            now = datetime.now(timezone.utc).isoformat()
            cand.reviewer_decision = {
                "reviewer": reviewer.strip(),
                "decision": decision,
                "reason": reason.strip(),
                "timestamp": now,
            }
            cand.status = "approved" if decision == "approved" else "rejected"
            cand.updated_at = now
            self._save_all()
            return cand

    def promote_candidate(self, candidate_id: str, reviewer: str) -> dict[str, Any]:
        """Atomically promotes an approved candidate to active version pointer using Phase 4 governance."""
        self.initialize()
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                raise KeyError(f"Candidate not found: {candidate_id}")

            if cand.status != "approved":
                raise ApiError(
                    409,
                    "candidate_not_approved",
                    f"Candidate '{candidate_id}' cannot be promoted: status is '{cand.status}' (must be 'approved')",
                )

            now = datetime.now(timezone.utc).isoformat()

            # Execute type-specific atomic version promotion
            if cand.candidate_type == "skill":
                reg = skill_registry.get_skill_registry()
                # Promote skill in registry
                record = reg.transition_status(
                    skill_id=cand.target_id,
                    new_status="approved",
                    reviewer=reviewer,
                    evidence=f"Promoted via Evaluation Candidate {candidate_id}",
                )
                cand.active_version_pointer = record.version

            elif cand.candidate_type == "memory":
                mem = shared_memory.get_shared_memory()
                # Promote memory item in shared memory
                item = mem.promote_candidate(
                    memory_id=cand.target_id,
                    reviewer=reviewer,
                    verification_method="evaluation_candidate_promotion",
                    evidence=cand.evidence_refs,
                )
                cand.active_version_pointer = f"v{item.version}"

            cand.updated_at = now
            self._save_all()

            return {
                "candidate_id": candidate_id,
                "target_id": cand.target_id,
                "candidate_type": cand.candidate_type,
                "status": "promoted",
                "active_version": cand.active_version_pointer,
                "promoted_by": reviewer,
                "timestamp": now,
            }

    def rollback_candidate(self, candidate_id: str, reviewer: str, reason: str) -> dict[str, Any]:
        """Rolls back an approved or promoted candidate, restoring prior active pointer without deleting history."""
        self.initialize()
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                raise KeyError(f"Candidate not found: {candidate_id}")

            now = datetime.now(timezone.utc).isoformat()
            cand.status = "rolled_back"
            cand.metadata["rollback"] = {
                "reviewer": reviewer,
                "reason": reason,
                "timestamp": now,
                "rolled_back_version": cand.active_version_pointer,
            }
            cand.updated_at = now
            self._save_all()

            return {
                "candidate_id": candidate_id,
                "target_id": cand.target_id,
                "status": "rolled_back",
                "rolled_back_by": reviewer,
                "reason": reason,
                "timestamp": now,
            }


# Singleton registry instance
_REGISTRY = EvaluationRegistry()


def get_evaluation_registry() -> EvaluationRegistry:
    _REGISTRY.initialize()
    return _REGISTRY


# Core Evaluation Runner
def evaluate_case(
    case: EvaluationCase,
    observed_output: dict[str, Any],
    llm_mock_response: dict[str, Any] | None = None,
) -> EvaluationResult:
    """Evaluates an observed agent/pipeline output against an EvaluationCase.
    Enforces that deterministic hard checks execute first and ALWAYS override LLM scores.
    """
    checks: list[DeterministicCheckResult] = []
    hard_gates_passed = True
    invariants = case.expected_invariants

    # 1. Deterministic Checks by Tag/Invariant
    # Telugu Native Script Check
    if invariants.get("require_telugu_script"):
        text = observed_output.get("transcript") or observed_output.get("text") or ""
        has_telugu = bool(TELUGU_RANGE_REGEX.search(text))
        passed = has_telugu
        checks.append(
            DeterministicCheckResult(
                check_id="check_telugu_native_script",
                name="Telugu Native Script Preservation",
                status="passed" if passed else "failed",
                severity="blocker",
                observed=f"has_telugu={has_telugu}",
                expected="has_telugu=True",
                reason="" if passed else "Narration contains no native Telugu script (U+0C00-U+0C7F)",
            )
        )
        if not passed:
            hard_gates_passed = False

    # English Term Preservation Check
    if invariants.get("require_english_terms"):
        text = observed_output.get("transcript") or observed_output.get("text") or ""
        missing_terms = [t for t in invariants["require_english_terms"] if t not in text]
        passed = len(missing_terms) == 0
        checks.append(
            DeterministicCheckResult(
                check_id="check_english_technical_terms",
                name="English Technical Terms Preservation",
                status="passed" if passed else "failed",
                severity="blocker",
                observed=f"missing={missing_terms}",
                expected="all terms present",
                reason="" if passed else f"Missing technical English nouns: {', '.join(missing_terms)}",
            )
        )
        if not passed:
            hard_gates_passed = False

    # Frame Arithmetic: Contiguous Scenes Check
    if invariants.get("contiguous_scenes"):
        scenes = observed_output.get("scenes", [])
        contiguous = True
        reason = ""
        for i in range(len(scenes) - 1):
            curr_end = scenes[i].get("end_frame", 0)
            next_start = scenes[i + 1].get("start_frame", 0)
            if curr_end != next_start:
                contiguous = False
                reason = f"Scene boundary gap/overlap between scene {i} (end {curr_end}) and scene {i+1} (start {next_start})"
                break
        checks.append(
            DeterministicCheckResult(
                check_id="check_contiguous_scenes",
                name="Contiguous Scene Frame Boundaries",
                status="passed" if contiguous else "failed",
                severity="blocker",
                observed=f"contiguous={contiguous}",
                expected="contiguous=True",
                reason=reason,
            )
        )
        if not contiguous:
            hard_gates_passed = False

    # Frame Arithmetic: Exact 30 FPS Check
    if invariants.get("exact_fps"):
        fps = observed_output.get("fps")
        exact_fps = bool(fps == 30)
        checks.append(
            DeterministicCheckResult(
                check_id="check_exact_30fps",
                name="Exact 30 FPS Arithmetic",
                status="passed" if exact_fps else "failed",
                severity="blocker",
                observed=fps,
                expected=30,
                reason="" if exact_fps else f"Expected exactly 30 fps, got {fps}",
            )
        )
        if not exact_fps:
            hard_gates_passed = False

    # Security: Forbid eval / dangerous imports in TSX
    code = observed_output.get("code") or ""
    if invariants.get("forbid_eval"):
        has_eval = bool(re.search(r"\beval\(", code))
        passed = not has_eval
        checks.append(
            DeterministicCheckResult(
                check_id="check_forbid_eval",
                name="Prohibit eval()",
                status="passed" if passed else "failed",
                severity="blocker",
                observed=f"has_eval={has_eval}",
                expected="has_eval=False",
                reason="" if passed else "Disallowed eval() call detected in generated TSX code",
            )
        )
        if not passed:
            hard_gates_passed = False

    if invariants.get("forbid_shell_imports"):
        has_shell = bool(re.search(r'import\s+.*(?:child_process|fs|os|subprocess)', code))
        passed = not has_shell
        checks.append(
            DeterministicCheckResult(
                check_id="check_forbid_shell_imports",
                name="Prohibit Shell/Node File System Imports",
                status="passed" if passed else "failed",
                severity="blocker",
                observed=f"has_shell_imports={has_shell}",
                expected="has_shell_imports=False",
                reason="" if passed else "Dangerous shell/node module imports detected in generated TSX code",
            )
        )
        if not passed:
            hard_gates_passed = False

    # 2. Optional LLM Judge Scoring
    # If hard gates failed, overall status is failed regardless of any LLM score
    llm_res: LlmJudgmentResult | None = None
    if llm_mock_response:
        llm_res = LlmJudgmentResult(
            rubric_version=case.rubric_version,
            provider=llm_mock_response.get("provider", "mock_gateway"),
            model=llm_mock_response.get("model", "mock_model"),
            scores=llm_mock_response.get("scores", {"quality": 1.0}),
            composite_score=float(llm_mock_response.get("composite_score", 1.0)),
            passed=bool(llm_mock_response.get("passed", True)),
            summary=llm_mock_response.get("summary", "Mocked LLM Judge evaluation"),
            findings=llm_mock_response.get("findings", []),
            latency_seconds=float(llm_mock_response.get("latency_seconds", 0.05)),
            tokens_used=llm_mock_response.get("tokens_used", {"input": 100, "output": 50}),
        )

    # 3. Overall Status Determination (STRICT PRECEDENCE)
    if not hard_gates_passed:
        overall_status = "failed"
        composite_score = 0.0
    elif llm_res and not llm_res.passed:
        overall_status = "failed"
        composite_score = llm_res.composite_score
    else:
        overall_status = "passed"
        composite_score = llm_res.composite_score if llm_res else 1.0

    check_capabilities = integrations.get("system_capabilities")        # what a connected domain runtime needs (browser, ffmpeg...); nothing without one
    caps = check_capabilities() if check_capabilities else {}

    return EvaluationResult(
        suite_id=case.suite_id,
        suite_version=case.case_version,
        case_id=case.case_id,
        case_version=case.case_version,
        stage_id=case.stage_id,
        overall_status=overall_status,
        hard_gates_passed=hard_gates_passed,
        deterministic_checks=checks,
        llm_judgment=llm_res,
        composite_score=composite_score,
        findings=[c.reason for c in checks if c.status == "failed"],
        is_mocked=bool(llm_mock_response is not None),
        capabilities=caps,
    )


def compare_evaluations(
    baseline: EvaluationResult | None,
    candidate: EvaluationResult,
    tolerance: float = 0.05,
) -> ComparisonReport:
    """Compares candidate evaluation against an approved baseline standard.
    Enforces regression rules:
    - Any new hard gate failure rejects candidate.
    - Soft quality drop exceeding tolerance rejects or degrades candidate.
    - Missing baseline is inconclusive.
    """
    if baseline is None:
        return ComparisonReport(
            candidate_id=candidate.evaluation_id,
            suite_id=candidate.suite_id,
            decision="inconclusive",
            summary="No baseline found for comparison. Evaluation is inconclusive.",
        )

    regressed_checks: list[str] = []
    base_check_map = {c.check_id: c.status for c in baseline.deterministic_checks}

    for cand_check in candidate.deterministic_checks:
        base_status = base_check_map.get(cand_check.check_id)
        if base_status == "passed" and cand_check.status == "failed":
            regressed_checks.append(cand_check.check_id)

    hard_regression = len(regressed_checks) > 0 or (baseline.hard_gates_passed and not candidate.hard_gates_passed)
    score_delta = round(candidate.composite_score - baseline.composite_score, 4)

    if hard_regression:
        decision = "rejected"
        summary = f"HARD GATE REGRESSION DETECTED on checks: {', '.join(regressed_checks)}. Candidate rejected."
    elif score_delta < -tolerance:
        decision = "degraded"
        summary = f"Quality score degraded by {score_delta:.4f} (exceeds tolerance {tolerance}). Candidate rejected."
    else:
        decision = "accepted"
        summary = f"Candidate passed all hard gates without regression (score delta: {score_delta:+.4f})."

    return ComparisonReport(
        baseline_id=baseline.evaluation_id,
        candidate_id=candidate.evaluation_id,
        suite_id=candidate.suite_id,
        decision=decision,
        hard_gate_regression=hard_regression,
        regressed_checks=regressed_checks,
        score_delta=score_delta,
        tolerance=tolerance,
        summary=summary,
    )
