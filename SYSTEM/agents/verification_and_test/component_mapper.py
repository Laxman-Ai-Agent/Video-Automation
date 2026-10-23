"""Component and Requirement Mapper for Verification & Test Agent.

Maps change sets, component identifiers, and acceptance criteria to authoritative
verification checks, test targets, and unverified requirement gaps.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Authoritative component-to-test mapping for the AI video generation system
COMPONENT_TEST_MAP: dict[str, list[str]] = {
    "agent_registry": [
        "tests/test_phase1_system_agents_restructuring.py",
        "tests/test_agent_architecture_reorg.py",
    ],
    "architecture_validator": [
        "tests/test_phase5_architecture_validator.py",
        "SYSTEM/agents/architecture_validator/tests/",
    ],
    "capability_finder": [
        "tests/test_phase2_capability_system.py",
        "tests/test_phase3_capability_learning.py",
        "SYSTEM/agents/capability_finder/tests/",
    ],
    "skill_factory": [
        "SYSTEM/agents/skill_factory/tests/",
    ],
    "main_architecture_agent": [
        "tests/test_agent_architecture_reorg.py",
        "tests/test_phase1_system_agents_restructuring.py",
    ],
    "verification_and_test": [
        "SYSTEM/agents/verification_and_test/tests/",
        "tests/test_phase6_verification_and_test.py",
    ],
    "security_policy": [
        "SYSTEM/agents/security_policy/tests/",
        "tests/test_phase7_security_policy.py",
    ],
    "autonomous_execution": [
        "SYSTEM/agents/autonomous_execution/tests/",
        "tests/test_phase8_autonomous_execution.py",
    ],
    "video_pipeline": [
        "tests/test_agent_architecture_reorg.py",
    ],
}

# Path patterns to component mapping
PATH_COMPONENT_PATTERNS: list[tuple[str, str]] = [
    ("SYSTEM/registries/agent_registry.py", "agent_registry"),
    ("SYSTEM/registries/", "agent_registry"),
    ("SYSTEM/agents/architecture_validator/", "architecture_validator"),
    ("SYSTEM/agents/capability_finder/", "capability_finder"),
    ("SYSTEM/agents/skill_factory/", "skill_factory"),
    ("SYSTEM/agents/main_architecture_agent/", "main_architecture_agent"),
    ("SYSTEM/agents/verification_and_test/", "verification_and_test"),
    ("SYSTEM/agents/security_policy/", "security_policy"),
    ("SYSTEM/agents/autonomous_execution/", "autonomous_execution"),
    ("SYSTEM/agents/system_agents/", "agent_registry"),
    ("VIDEO_ENGINE/", "video_pipeline"),
]


class ComponentMapper:
    """Resolves changed files and requirements into concrete verification check targets."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]

    def map_changed_files_to_components(self, changed_files: list[str]) -> set[str]:
        """Infers affected system components from a list of modified file paths."""
        components: set[str] = set()
        for raw_path in changed_files:
            norm_path = raw_path.replace("\\", "/").lstrip("/")
            matched = False
            for pattern, comp in PATH_COMPONENT_PATTERNS:
                if pattern in norm_path or norm_path.startswith(pattern):
                    components.add(comp)
                    matched = True
            if not matched:
                file_name = Path(norm_path).name.lower()
                if file_name.startswith("test_") or file_name.endswith("_test.py"):
                    components.add("verification_and_test")
                elif "video" in file_name:
                    components.add("video_pipeline")
        return components

    def resolve_test_targets(
        self,
        components: list[str] | set[str],
        changed_files: list[str] | None = None,
    ) -> list[str]:
        """Resolves affected components into unique, ordered test command targets."""
        all_components = set(components)
        if changed_files:
            all_components.update(self.map_changed_files_to_components(changed_files))

        targets: list[str] = []
        for comp in all_components:
            for target in COMPONENT_TEST_MAP.get(comp, []):
                if target not in targets:
                    targets.append(target)

        return targets

    def analyze_requirements(
        self,
        requirements: list[str],
        available_tools: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Separates verifiable requirements from unverified/unsupported requirements."""
        available = set(available_tools or ["pytest_runner", "hash_verifier", "agent_registry"])
        verifiable: list[str] = []
        unverified: list[str] = []

        for req in requirements:
            req_lower = req.lower()
            # Requirements that require unavailable external platforms or human sign-off
            if "human sign-off" in req_lower or "external cloud" in req_lower or "manual review" in req_lower:
                unverified.append(f"{req} (Reason: Requires interactive human sign-off or unavailable external cloud platform)")
            elif "unrestricted network" in req_lower or "live internet" in req_lower:
                unverified.append(f"{req} (Reason: Live unrestricted network access prohibited by security policy)")
            else:
                verifiable.append(req)

        return verifiable, unverified
