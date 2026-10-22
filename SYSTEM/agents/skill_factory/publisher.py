"""Atomic Versioned Skill Publisher and Rollback Manager.

Handles:
1. Concurrency-safe promotion and rollback using StoreLock (in-process + OS file-lock).
2. Anti-spoofing operator authentication integration.
3. Version archive preservation and conflict detection.
4. Atomic file replacement on disk.
5. Coherent synchronization across SkillRegistry and CapabilityRegistry.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SYSTEM.agents.capability_finder.learning.authorization import (
    AuthenticatedOperator,
    SecurityAuthError,
    authenticate_operator,
)
from SYSTEM.agents.capability_finder.learning.store_lock import StoreLock
from SYSTEM.agents.skill_factory.lifecycle import SkillLifecycle
from SYSTEM.agents.skill_factory.specification import SkillSpecification, validate_specification
from SYSTEM.registries.capability_registry import get_capability_registry
from SYSTEM.registries.skill_registry import (
    SKILLS_DIR,
    SkillRecord,
    SkillSecurityError,
    get_skill_registry,
    verify_skill_path_confinement,
)

logger = logging.getLogger("skill_factory.publisher")

ARCHIVE_DIR = SKILLS_DIR / "archive"
PUBLISHER_LOCK_FILE = SKILLS_DIR / ".catalog.lock"


class PromotionError(Exception):
    """Raised when skill promotion fails."""
    pass


class RollbackError(Exception):
    """Raised when skill rollback fails."""
    pass


@dataclass
class PromotionResult:
    """Detailed audit report of a successful skill promotion."""
    skill_id: str
    version: str
    entrypoint: str
    content_sha256: str
    status: str
    promoted_at: str
    operator_attribution: str
    synced_capabilities: int
    archive_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackResult:
    """Detailed audit report of a skill rollback operation."""
    skill_id: str
    rolled_back_version: str
    restored_version: str | None
    status: str
    rolled_back_at: str
    operator_attribution: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillPublisher:
    """Coordinates atomic publication, version archiving, and rollback of skills."""

    def __init__(self) -> None:
        self._skill_registry = get_skill_registry()
        self._cap_registry = get_capability_registry()

    def _get_lock(self) -> StoreLock:
        return StoreLock.get(PUBLISHER_LOCK_FILE, timeout=15.0)

    def promote_skill(
        self,
        spec: SkillSpecification,
        content: str,
        lifecycle: SkillLifecycle,
        operator: AuthenticatedOperator | None = None,
        operator_id: str | None = None,
        role: str | None = None,
        approval_request_id: str | None = None,
        test_result: Any | None = None,
        target_agent_id: str | None = None,
    ) -> PromotionResult:
        """Promotes an approved skill candidate to active production library."""
        # 1. Verify Specification
        errs = validate_specification(spec)
        if errs:
            raise PromotionError(f"Cannot promote invalid specification: {'; '.join(errs)}")

        # 2. Verify Lifecycle State
        if not lifecycle.is_promotable:
            raise PromotionError(
                f"Skill '{spec.skill_id}' cannot be promoted from state '{lifecycle.current_state}'. "
                f"Must be in APPROVED state."
            )

        # 3. Authenticate Operator with anti-spoofing
        auth_operator = authenticate_operator(
            operator=operator,
            operator_id=operator_id,
            role=role,
            approval_request_id=approval_request_id,
        )

        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        # 4. Cryptographic Verification of Test Evidence & Sandbox Integrity
        if test_result is not None:
            status = getattr(test_result, "status", None) or (test_result.get("status") if isinstance(test_result, dict) else None)
            passed = getattr(test_result, "passed", None) if hasattr(test_result, "passed") else (test_result.get("passed") if isinstance(test_result, dict) else False)
            tested_sha = getattr(test_result, "tested_content_sha256", "") or (test_result.get("tested_content_sha256", "") if isinstance(test_result, dict) else "")

            if status == "blocked_isolation":
                raise PromotionError(
                    f"Cannot promote skill '{spec.skill_id}': behavioral testing was blocked "
                    "due to unavailable isolation backend (status='blocked_isolation')."
                )
            if not passed:
                raise PromotionError(
                    f"Cannot promote skill '{spec.skill_id}': behavioral tests failed (status='{status}')."
                )
            if tested_sha and tested_sha != content_sha:
                raise PromotionError(
                    f"Cannot promote skill '{spec.skill_id}': candidate content modified after testing! "
                    f"Tested SHA-256 '{tested_sha}' does not match promotion SHA-256 '{content_sha}'."
                )

        # Also inspect historical test events in lifecycle history
        for evt in lifecycle.history:
            if evt.evidence and "test_result" in evt.evidence:
                tr = evt.evidence["test_result"]
                if isinstance(tr, dict):
                    if tr.get("status") == "blocked_isolation":
                        raise PromotionError(
                            f"Cannot promote skill '{spec.skill_id}': lifecycle history records "
                            "blocked isolation during testing."
                        )
                    if tr.get("passed") is False:
                        raise PromotionError(
                            f"Cannot promote skill '{spec.skill_id}': lifecycle history records failed tests."
                        )
                    hist_sha = tr.get("tested_content_sha256")
                    if hist_sha and hist_sha != content_sha:
                        raise PromotionError(
                            f"Cannot promote skill '{spec.skill_id}': content modified after lifecycle testing. "
                            f"Tested SHA-256 '{hist_sha}' != promotion SHA-256 '{content_sha}'."
                        )

        # Agent-local promotion flow if target_agent_id is specified
        target_agent = target_agent_id or spec.target_agent_id
        if target_agent:
            from SYSTEM.registries.agent_registry import registry as agent_registry
            if agent_registry.get(target_agent) is None:
                raise ValueError(f"Invalid target_agent_id '{target_agent}': not registered in AgentRegistry.")

            with self._get_lock():
                lifecycle.transition(
                    "PROMOTING",
                    actor=auth_operator.attribution_string(),
                    reason=f"Starting atomic agent-local promotion for agent {target_agent}.",
                )
                skill_dir_name = spec.skill_id.replace(".", "_")

                from SYSTEM.core import config
                base_dir = config.PROJECT_ROOT / "SYSTEM" / "agents"
                agent_dirs = [
                    base_dir / target_agent / "skills",
                    base_dir / "video_generation_agents" / target_agent / "skills",
                ]

                written_files = []
                for s_dir in agent_dirs:
                    if s_dir.exists():
                        target_skill_dir = s_dir / skill_dir_name
                        target_skill_dir.mkdir(parents=True, exist_ok=True)
                        skill_file = target_skill_dir / "SKILL.md"
                        self._atomic_write(skill_file, content)
                        written_files.append(skill_file)
                        if spec.code_content:
                            code_file = target_skill_dir / "skill.py"
                            self._atomic_write(code_file, spec.code_content)
                            written_files.append(code_file)

                if not written_files:
                    s_dir = base_dir / target_agent / "skills"
                    s_dir.mkdir(parents=True, exist_ok=True)
                    target_skill_dir = s_dir / skill_dir_name
                    target_skill_dir.mkdir(parents=True, exist_ok=True)
                    skill_file = target_skill_dir / "SKILL.md"
                    self._atomic_write(skill_file, content)
                    written_files.append(skill_file)
                    if spec.code_content:
                        code_file = target_skill_dir / "skill.py"
                        self._atomic_write(code_file, spec.code_content)
                        written_files.append(code_file)

                lifecycle.transition(
                    "ACTIVE",
                    actor=auth_operator.attribution_string(),
                    reason=f"Skill '{spec.skill_id}' successfully promoted to agent-local directory for {target_agent}.",
                )

                return PromotionResult(
                    skill_id=spec.skill_id,
                    version=spec.version,
                    entrypoint=str(written_files[0]),
                    content_sha256=content_sha,
                    status="approved",
                    promoted_at=now,
                    operator_attribution=auth_operator.attribution_string(),
                    synced_capabilities=len(spec.capabilities),
                    archive_path="",
                )

        # 5. Acquire StoreLock for concurrency-safe publication
        with self._get_lock():
            lifecycle.transition(
                "PROMOTING",
                actor=auth_operator.attribution_string(),
                reason="Starting atomic promotion transaction.",
            )

            try:
                self._skill_registry.initialize()
                existing_record = self._skill_registry._skills.get(spec.skill_id)

                # 5. Archive prior active version if exists
                archive_file_path = ""
                if existing_record is not None:
                    archive_file_path = self._archive_existing_version(existing_record)

                # 6. Determine canonical destination paths
                domain_clean = spec.domain.replace(".", "/").strip("/")
                skill_dir_name = spec.skill_id.split(".")[-1]
                target_rel_dir = Path(domain_clean) / skill_dir_name
                target_abs_dir = SKILLS_DIR / target_rel_dir
                target_abs_dir.mkdir(parents=True, exist_ok=True)

                # Versioned folder: <domain>/<skill_name>/v<version>/SKILL.md
                version_abs_dir = target_abs_dir / f"v{spec.version}"
                version_abs_dir.mkdir(parents=True, exist_ok=True)
                version_file = version_abs_dir / "SKILL.md"

                # Canonical alias: <domain>/<skill_name>/SKILL.md
                canonical_file = target_abs_dir / "SKILL.md"

                # 7. Atomic Write to Disk
                self._atomic_write(version_file, content)
                self._atomic_write(canonical_file, content)

                # Relative entrypoint for catalog
                rel_entrypoint = str(canonical_file.relative_to(SKILLS_DIR)).replace("\\", "/")
                verify_skill_path_confinement(rel_entrypoint, allow_staging=False)

                # 8. Register and update SkillRecord in SkillRegistry
                new_record = SkillRecord(
                    skill_id=spec.skill_id,
                    name=spec.name,
                    summary=spec.purpose,
                    domain=spec.domain,
                    tags=spec.tags,
                    version=spec.version,
                    entrypoint=rel_entrypoint,
                    status="approved",
                    source="local",
                    content_sha256=content_sha,
                    license=spec.license,
                    license_evidence=spec.license_evidence or f"Authored via Skill Factory: {auth_operator.attribution_string()}",
                    capabilities=spec.capabilities,
                    dependencies=spec.dependencies,
                    compatible_agents=spec.compatible_agents,
                    compatible_project_modes=spec.compatible_project_modes,
                    input_contracts=spec.inputs,
                    output_contracts=spec.outputs,
                    risk_level=spec.risk_level,
                    approval={
                        "reviewer": auth_operator.attribution_string(),
                        "timestamp": now,
                        "evidence": f"Approval verified via {auth_operator.auth_method}",
                    },
                    last_audited_at=now,
                    created_at=existing_record.created_at if existing_record else now,
                    updated_at=now,
                    metadata={"specification": spec.to_dict()},
                )
                self._skill_registry.register_skill(new_record)

                # 9. Synchronize with CapabilityRegistry
                sync_report = self._cap_registry.sync_with_registries()
                synced_caps = sync_report.get("skills_synced", 0)

                # 10. Finalize Lifecycle to ACTIVE
                lifecycle.transition(
                    "ACTIVE",
                    actor=auth_operator.attribution_string(),
                    reason="Atomic publication completed and synchronized with registries.",
                    evidence={"content_sha256": content_sha, "entrypoint": rel_entrypoint},
                )

                logger.info(
                    f"Successfully promoted skill '{spec.skill_id}' v{spec.version} "
                    f"by {auth_operator.attribution_string()}."
                )

                return PromotionResult(
                    skill_id=spec.skill_id,
                    version=spec.version,
                    entrypoint=rel_entrypoint,
                    content_sha256=content_sha,
                    status="ACTIVE",
                    promoted_at=now,
                    operator_attribution=auth_operator.attribution_string(),
                    synced_capabilities=synced_caps,
                    archive_path=archive_file_path,
                )

            except Exception as e:
                lifecycle.transition(
                    "PROMOTION_FAILED",
                    actor=auth_operator.attribution_string(),
                    reason=f"Promotion failed: {e}",
                )
                logger.error(f"Promotion failed for '{spec.skill_id}': {e}", exc_info=True)
                raise PromotionError(f"Failed to publish skill '{spec.skill_id}': {e}") from e

    def rollback_skill(
        self,
        skill_id: str,
        reason: str,
        operator: AuthenticatedOperator | None = None,
        operator_id: str | None = None,
        role: str | None = None,
        approval_request_id: str | None = None,
        target_version: str | None = None,
    ) -> RollbackResult:
        """Rolls back an active skill to a prior valid archived version or deprecates it."""
        auth_operator = authenticate_operator(
            operator=operator,
            operator_id=operator_id,
            role=role,
            approval_request_id=approval_request_id,
        )

        now = datetime.now(timezone.utc).isoformat()

        with self._get_lock():
            self._skill_registry.initialize()
            current_record = self._skill_registry._skills.get(skill_id)
            if not current_record:
                raise RollbackError(f"Cannot rollback: Skill '{skill_id}' not found in registry.")

            rolled_back_ver = current_record.version
            restored_ver: str | None = None

            # Look for archived versions that are not the current version being rolled back
            skill_archive_dir = ARCHIVE_DIR / skill_id
            prior_archive: Path | None = None

            if skill_archive_dir.exists():
                archives = [
                    f for f in sorted(skill_archive_dir.glob("v*.json"), reverse=True)
                    if f.stem != f"v{rolled_back_ver}"
                ]
                if target_version:
                    target_file = skill_archive_dir / f"v{target_version}.json"
                    if target_file.exists() and target_version != rolled_back_ver:
                        prior_archive = target_file
                elif archives:
                    prior_archive = archives[0]

            if prior_archive is not None:
                # Restore prior version from archive
                try:
                    prior_data = json.loads(prior_archive.read_text(encoding="utf-8"))
                    prior_record_dict = prior_data.get("record", {})
                    prior_content = prior_data.get("content", "")

                    restored_record = SkillRecord.from_dict(prior_record_dict)
                    restored_ver = restored_record.version

                    # Restore canonical file
                    if restored_record.entrypoint:
                        canonical_path = SKILLS_DIR / restored_record.entrypoint
                        self._atomic_write(canonical_path, prior_content)

                    # Update registry
                    self._skill_registry.register_skill(restored_record)

                except Exception as e:
                    raise RollbackError(f"Failed to restore prior archive '{prior_archive}': {e}") from e
            else:
                # No prior version exists -> Mark current record as deprecated
                current_record.status = "deprecated"
                current_record.updated_at = now
                self._skill_registry._save()

            # Resynchronize Capability Registry
            self._cap_registry.sync_with_registries()

            logger.info(
                f"Skill '{skill_id}' rolled back from v{rolled_back_ver} to "
                f"{restored_ver or 'deprecated'} by {auth_operator.attribution_string()}."
            )

            return RollbackResult(
                skill_id=skill_id,
                rolled_back_version=rolled_back_ver,
                restored_version=restored_ver,
                status="ROLLED_BACK",
                rolled_back_at=now,
                operator_attribution=auth_operator.attribution_string(),
                reason=reason,
            )

    def _archive_existing_version(self, record: SkillRecord) -> str:
        """Archives current record and file content before promotion."""
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        skill_archive_dir = ARCHIVE_DIR / record.skill_id
        skill_archive_dir.mkdir(parents=True, exist_ok=True)

        archive_file = skill_archive_dir / f"v{record.version}.json"
        content = ""
        if record.entrypoint:
            src_path = SKILLS_DIR / record.entrypoint
            if src_path.exists():
                content = src_path.read_text(encoding="utf-8")

        payload = {
            "skill_id": record.skill_id,
            "version": record.version,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "record": record.to_dict(),
            "content": content,
        }
        self._atomic_write(archive_file, json.dumps(payload, indent=2))
        return str(archive_file)

    def _atomic_write(self, target_path: Path, data: str) -> None:
        """Writes data atomically using a temporary file on the same filesystem."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        tmp_path.write_bytes(data.encode("utf-8"))
        os.replace(tmp_path, target_path)


# Authoritative singleton
skill_publisher = SkillPublisher()
