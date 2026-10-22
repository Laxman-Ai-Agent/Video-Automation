"""Capability Finder System Agent Package (Canonical).

Discovers and evaluates existing agents, skills, tools, and system runtime prerequisites.
Includes RequirementParser, AstScanner, CapabilityMatcher, GapAnalyzer, and the
Phase 3 Self-Learning Subsystem (CaseCollector, OutcomeAnalyzer, FeedbackProcessor,
LessonGenerator, LessonEvaluator, LearningGate, KnowledgePromoter, RollbackManager).
"""
from __future__ import annotations

from .agent import CapabilityFinderAgent
from .discovery.ast_scanner import AstDiscoveredItem, AstScanner, ast_scanner
from .discovery.gap_analyzer import GapAnalysisReport, GapAnalyzer, gap_analyzer
from .discovery.matcher import CapabilityMatch, CapabilityMatcher, capability_matcher
from .discovery.requirement_parser import ParsedRequirement, RequirementParser, requirement_parser
from .learning.case_collector import CaseCollector, LearningCase, case_collector
from .learning.feedback_processor import FeedbackProcessor, feedback_processor
from .learning.knowledge_promoter import KnowledgePromoter, knowledge_promoter
from .learning.learning_gate import LearningGate, learning_gate
from .learning.lesson_evaluator import (
    BENCHMARK_V1,
    BENCHMARK_VERSION,
    EvaluationMetrics,
    LearningEvaluation,
    LessonEvaluator,
    lesson_evaluator,
)
from .learning.lesson_generator import LessonGenerator, LessonProposal, lesson_generator
from .learning.outcome_analyzer import OutcomeAnalyzer, outcome_analyzer
from .learning.rollback_manager import RollbackManager, rollback_manager

__all__ = [
    "CapabilityFinderAgent",
    "AstDiscoveredItem",
    "AstScanner",
    "ast_scanner",
    "GapAnalysisReport",
    "GapAnalyzer",
    "gap_analyzer",
    "CapabilityMatch",
    "CapabilityMatcher",
    "capability_matcher",
    "ParsedRequirement",
    "RequirementParser",
    "requirement_parser",
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
    "knowledge_promoter",
    "RollbackManager",
    "rollback_manager",
]
