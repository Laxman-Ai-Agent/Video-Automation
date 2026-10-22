"""Learning Subsystem for Capability Finder Agent.

Provides experience collection, outcome attribution, feedback ingestion,
lesson generation, offline evaluation, promotion gates, authorization,
and rollback management.
"""
from __future__ import annotations

from .authorization import (
    ELEVATED_SECURITY_ROLES,
    TRUSTED_OPERATOR_ROLES,
    AuthenticatedOperator,
    SecurityAuthError,
    authenticate_operator,
    verify_elevated_role,
)
from .case_collector import CaseCollector, LearningCase, case_collector
from .feedback_processor import FeedbackProcessor, feedback_processor
from .knowledge_promoter import KnowledgePromoter, _KNOWLEDGE_LOCK, knowledge_promoter
from .learning_gate import LearningGate, learning_gate
from .lesson_evaluator import (
    BENCHMARK_V1,
    BENCHMARK_VERSION,
    EvaluationMetrics,
    LearningEvaluation,
    LessonEvaluator,
    lesson_evaluator,
)
from .lesson_generator import LessonGenerator, LessonProposal, lesson_generator
from .outcome_analyzer import OutcomeAnalyzer, outcome_analyzer
from .rollback_manager import RollbackManager, rollback_manager
from .store_lock import StoreLock

__all__ = [
    "AuthenticatedOperator",
    "SecurityAuthError",
    "authenticate_operator",
    "verify_elevated_role",
    "TRUSTED_OPERATOR_ROLES",
    "ELEVATED_SECURITY_ROLES",
    "StoreLock",
    "CaseCollector",
    "LearningCase",
    "case_collector",
    "OutcomeAnalyzer",
    "outcome_analyzer",
    "FeedbackProcessor",
    "feedback_processor",
    "LessonGenerator",
    "LessonProposal",
    "lesson_generator",
    "LessonEvaluator",
    "LearningEvaluation",
    "EvaluationMetrics",
    "BENCHMARK_V1",
    "BENCHMARK_VERSION",
    "lesson_evaluator",
    "LearningGate",
    "learning_gate",
    "KnowledgePromoter",
    "_KNOWLEDGE_LOCK",
    "knowledge_promoter",
    "RollbackManager",
    "rollback_manager",
]
