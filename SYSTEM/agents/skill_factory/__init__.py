"""Skill Factory System Agent Package (Canonical).

Responsible for:
- Video-specialized skill specification intake and contract validation.
- Multi-variant parameterized reuse / adapt / create decision evaluation.
- Candidate skill authoring and adaptation.
- Static security, token leakage, and AST analysis.
- Domain-specific video quality evaluation (audio, visual, motion, typography, ffmpeg).
- Content-hash evaluation caching for deduplicated execution.
- Isolated behavioral testing and preflight detection.
- Windows Job Object resource governance and fail-closed sandbox policies.
- Approval integration, atomic versioned promotion, and safe rollback.
"""
from __future__ import annotations

from .agent import SkillFactoryAgent
from .decision_engine import DecisionEngine, SkillDecision, decision_engine
from .evaluation_cache import EvaluationCache, evaluation_cache
from .generator import (
    GenerationProviderUnavailableError,
    SkillDraft,
    SkillGenerationError,
    SkillGenerator,
    skill_generator,
)
from .lifecycle import (
    InvalidLifecycleTransitionError,
    LifecycleEvent,
    LifecycleState,
    SkillLifecycle,
)
from .publisher import (
    PromotionError,
    PromotionResult,
    RollbackError,
    RollbackResult,
    SkillPublisher,
    skill_publisher,
)
from .sandbox_policy import (
    DEFAULT_ENV_ALLOWLIST,
    FROZEN_PIPELINE_FILES,
    SandboxPolicy,
    SandboxSecurityError,
    compute_baseline_hashes,
    sanitize_environment,
    verify_baseline_hashes_unchanged,
    verify_no_symlink_escapes,
    verify_sandbox_path_confinement,
)
from .sandbox_preflight import (
    SandboxCapabilities,
    check_docker_runtime,
    check_windows_job_objects,
    probe_sandbox_capabilities,
)
from .security_validator import SecurityAuditResult, SecurityValidator, security_validator
from .specification import SkillSpecification, validate_specification
from .test_runner import (
    BehavioralTestResult,
    SkillTestRunner,
    WindowsJobObject,
    skill_test_runner,
)
from .video_quality_evaluator import (
    VideoQualityCheckResult,
    VideoQualityEvaluator,
    video_quality_evaluator,
)

__all__ = [
    "SkillFactoryAgent",
    "SkillSpecification",
    "validate_specification",
    "DecisionEngine",
    "decision_engine",
    "SkillDecision",
    "SkillGenerator",
    "skill_generator",
    "SkillDraft",
    "SkillGenerationError",
    "GenerationProviderUnavailableError",
    "SecurityValidator",
    "security_validator",
    "SecurityAuditResult",
    "SkillTestRunner",
    "skill_test_runner",
    "WindowsJobObject",
    "BehavioralTestResult",
    "SkillLifecycle",
    "LifecycleEvent",
    "LifecycleState",
    "InvalidLifecycleTransitionError",
    "SkillPublisher",
    "skill_publisher",
    "PromotionResult",
    "RollbackResult",
    "PromotionError",
    "RollbackError",
    "SandboxPolicy",
    "SandboxCapabilities",
    "SandboxSecurityError",
    "DEFAULT_ENV_ALLOWLIST",
    "FROZEN_PIPELINE_FILES",
    "probe_sandbox_capabilities",
    "check_docker_runtime",
    "check_windows_job_objects",
    "sanitize_environment",
    "verify_sandbox_path_confinement",
    "verify_no_symlink_escapes",
    "compute_baseline_hashes",
    "verify_baseline_hashes_unchanged",
    "EvaluationCache",
    "evaluation_cache",
    "VideoQualityEvaluator",
    "video_quality_evaluator",
    "VideoQualityCheckResult",
]
