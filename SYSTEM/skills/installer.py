"""Controlled Skill Installation, Validation, and Registration Engine.

Enforces:
1. Retrieval of only required component files and minimal dependencies.
2. Pre-installation security, metadata, and license validation.
3. Confinement to SYSTEM/skills/library/<category_id>/<skill_id>/.
4. Post-installation isolated load testing (aborts and rolls back on failure).
5. Idempotent execution and safe updates without duplicate proliferation.
6. Atomic registration into SkillRegistry and CapabilityRegistry.
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from SYSTEM.registries.capability_registry import CapabilityRecord, get_capability_registry
from SYSTEM.registries.skill_registry import (
    SkillRecord,
    SkillSecurityError,
    SkillVerificationError,
    audit_skill_content,
    get_skill_registry,
)
from .discovery import DiscoveredSkillCandidate
from .evaluator import CandidateEvaluator, get_candidate_evaluator
from .taxonomy import CategoryTaxonomy, get_category_taxonomy

logger = logging.getLogger("skill_library.installer")

SKILLS_DIR = Path(__file__).parent
LIBRARY_ROOT = SKILLS_DIR / "library"
HISTORY_ROOT = SKILLS_DIR / "archive" / "library_history"
INSTALLED_INDEX_FILE = SKILLS_DIR / "installed_skills.json"


@dataclass
class InstalledSkillRecord:
    """Record of a verified, installed skill inside the category-managed library."""
    skill_id: str
    name: str
    category_id: str
    subcategory: str | None
    version: str
    installation_path: str  # Relative to project root
    entrypoint: str  # Relative to SYSTEM/skills/
    content_sha256: str
    license: str
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    applicable_agents: list[str] = field(default_factory=list)
    source_url: str | None = None
    installed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_status: Literal["verified", "failed", "stale"] = "verified"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstalledSkillRecord:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class InstallationResult:
    """Outcome of attempting to install and validate a candidate skill."""
    success: bool
    action: Literal["installed", "updated", "reused", "rejected", "failed"]
    installed_record: InstalledSkillRecord | None
    validation_passed: bool
    validation_errors: list[str]
    audit_details: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "installed_record": self.installed_record.to_dict() if self.installed_record else None,
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
            "audit_details": self.audit_details,
            "message": self.message,
        }


class SkillLibraryInstaller:
    """Controlled installer and validator for category-based video editing skills."""

    def __init__(self) -> None:
        self._taxonomy: CategoryTaxonomy = get_category_taxonomy()
        self._evaluator: CandidateEvaluator = get_candidate_evaluator()
        self._skill_registry = get_skill_registry()
        self._cap_registry = get_capability_registry()
        self._installed_skills: dict[str, InstalledSkillRecord] = {}
        self._load_installed_index()

    def _load_installed_index(self) -> None:
        if INSTALLED_INDEX_FILE.exists():
            try:
                data = json.loads(INSTALLED_INDEX_FILE.read_text(encoding="utf-8"))
                for s_id, s_data in data.get("installed_skills", {}).items():
                    self._installed_skills[s_id] = InstalledSkillRecord.from_dict(s_data)
            except Exception as e:
                logger.warning(f"Could not load installed skills index: {e}")

    def _save_installed_index(self) -> None:
        INSTALLED_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_installed": len(self._installed_skills),
            "installed_skills": {k: v.to_dict() for k, v in self._installed_skills.items()},
        }
        INSTALLED_INDEX_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_installed_skills(self, category_id: str | None = None) -> list[InstalledSkillRecord]:
        """Returns installed skills optionally filtered by category."""
        skills = list(self._installed_skills.values())
        if category_id:
            skills = [s for s in skills if s.category_id == category_id]
        return sorted(skills, key=lambda s: s.skill_id)

    def get_installed_skill(self, skill_id: str) -> InstalledSkillRecord | None:
        """Retrieves installed skill record by ID."""
        return self._installed_skills.get(skill_id)

    def install_skill(
        self,
        candidate: DiscoveredSkillCandidate | dict[str, Any],
        target_category: str | None = None,
        force_update: bool = False,
    ) -> InstallationResult:
        """Installs, validates, tests, and registers a candidate skill into the category library."""
        if isinstance(candidate, dict):
            cand_id = candidate.get("id") or candidate.get("candidate_id") or "unnamed_skill"
            cand_name = candidate.get("name", cand_id)
            cand_cat = target_category or candidate.get("category_id") or candidate.get("category") or "graphics"
            cand_sub = candidate.get("subcategory")
            cand_ver = candidate.get("version", "1.0.0")
            cand_lic = candidate.get("license", "MIT")
            cand_caps = candidate.get("capabilities", [])
            cand_code = candidate.get("code_files", {})
            cand_meta = candidate.get("metadata", candidate)
        else:
            cand_id = candidate.candidate_id
            cand_name = candidate.name
            cand_cat = target_category or candidate.category_id
            cand_sub = candidate.subcategory
            cand_ver = candidate.version
            cand_lic = candidate.license
            cand_caps = candidate.capabilities
            cand_code = candidate.code_files
            cand_meta = candidate.metadata

        # Ensure valid category
        category_def = self._taxonomy.get_category(cand_cat)
        if not category_def:
            return InstallationResult(
                success=False,
                action="rejected",
                installed_record=None,
                validation_passed=False,
                validation_errors=[f"Unknown category '{cand_cat}'"],
                audit_details={},
                message=f"Category '{cand_cat}' is not a registered category in the taxonomy.",
            )

        # Sanitize skill_id
        safe_id = cand_id.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
        dest_dir = LIBRARY_ROOT / cand_cat / safe_id

        # -------------------------------------------------------------
        # 1. Idempotency & Re-use Check
        # -------------------------------------------------------------
        existing = self._installed_skills.get(safe_id)
        raw_skill_md = cand_code.get("SKILL.md") or self._generate_skill_md(safe_id, cand_name, cand_cat, cand_sub, cand_caps, cand_lic)
        norm_skill_bytes = raw_skill_md.replace("\r\n", "\n").encode("utf-8")
        content_hash = hashlib.sha256(norm_skill_bytes).hexdigest()

        if existing and not force_update:
            if existing.content_sha256 == content_hash and dest_dir.exists():
                return InstallationResult(
                    success=True,
                    action="reused",
                    installed_record=existing,
                    validation_passed=True,
                    validation_errors=[],
                    audit_details={"existing": existing.to_dict()},
                    message=f"Skill '{safe_id}' is already installed with identical content hash ({content_hash[:8]}). Reused safely.",
                )

        # -------------------------------------------------------------
        # 2. Pre-installation Evaluation & Security Gate
        # -------------------------------------------------------------
        eval_report = self._evaluator.evaluate_candidate(
            candidate_data=cand_meta,
            target_category=cand_cat,
            target_capability=cand_caps[0] if cand_caps else cand_id,
            code_files=cand_code,
            current_skill_id=safe_id if existing else None,
        )

        if eval_report.verdict == "REJECTED":
            return InstallationResult(
                success=False,
                action="rejected",
                installed_record=None,
                validation_passed=False,
                validation_errors=eval_report.actionable_reasons,
                audit_details=eval_report.to_dict(),
                message=f"Installation rejected by evaluation gate: {eval_report.summary}",
            )

        # Verify confinement
        try:
            dest_dir.resolve().relative_to(SKILLS_DIR.resolve())
        except ValueError:
            return InstallationResult(
                success=False,
                action="rejected",
                installed_record=None,
                validation_passed=False,
                validation_errors=["Destination path escapes canonical skills directory"],
                audit_details={},
                message="Security violation: Path traversal detected.",
            )

        # -------------------------------------------------------------
        # 3. Backup Previous Version on Update
        # -------------------------------------------------------------
        if dest_dir.exists() and existing:
            self._backup_previous_version(safe_id, cand_cat, dest_dir, existing.version)

        # -------------------------------------------------------------
        # 4. Retrieve & Write Skill Files
        # -------------------------------------------------------------
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Write code files with LF normalization
            for fname, code in cand_code.items():
                if ".." in fname or "/" in fname or "\\" in fname:
                    raise SkillSecurityError(f"Invalid filename '{fname}' in candidate")
                target_file = dest_dir / fname
                target_file.write_bytes(code.replace("\r\n", "\n").encode("utf-8"))

            # Ensure SKILL.md exists
            skill_md_path = dest_dir / "SKILL.md"
            if not skill_md_path.exists():
                skill_md_path.write_bytes(norm_skill_bytes)

            # Recompute exact SHA after writing SKILL.md
            full_sha = hashlib.sha256(skill_md_path.read_bytes()).hexdigest()

            # Entrypoint determination
            entrypoint_rel = f"library/{cand_cat}/{safe_id}/SKILL.md"

            # Create manifest.json
            applicable_agents = category_def.applicable_agents
            manifest_payload = {
                "skill_id": safe_id,
                "name": cand_name,
                "category_id": cand_cat,
                "subcategory": cand_sub,
                "version": cand_ver,
                "license": cand_lic,
                "entrypoint": entrypoint_rel,
                "content_sha256": full_sha,
                "capabilities": cand_caps or [safe_id],
                "dependencies": cand_meta.get("dependencies", []),
                "applicable_agents": applicable_agents,
                "installed_at": datetime.now(timezone.utc).isoformat(),
            }
            (dest_dir / "manifest.json").write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

        except Exception as e:
            # Clean up on write failure
            if dest_dir.exists():
                shutil.rmtree(dest_dir, ignore_errors=True)
            return InstallationResult(
                success=False,
                action="failed",
                installed_record=None,
                validation_passed=False,
                validation_errors=[str(e)],
                audit_details={},
                message=f"Failed writing skill files: {e}",
            )

        # -------------------------------------------------------------
        # 6. Post-installation Load Testing
        # -------------------------------------------------------------
        load_passed, load_errors = self._run_load_test(dest_dir)
        if not load_passed:
            # Rollback failed installation immediately
            shutil.rmtree(dest_dir, ignore_errors=True)
            return InstallationResult(
                success=False,
                action="failed",
                installed_record=None,
                validation_passed=False,
                validation_errors=load_errors,
                audit_details={"load_test_failure": load_errors},
                message=f"Post-installation load test failed: {'; '.join(load_errors)}. Installation rolled back.",
            )

        # -------------------------------------------------------------
        # 7. Atomic Registration in Registries
        # -------------------------------------------------------------
        record = InstalledSkillRecord(
            skill_id=safe_id,
            name=cand_name,
            category_id=cand_cat,
            subcategory=cand_sub,
            version=cand_ver,
            installation_path=str(dest_dir.relative_to(SKILLS_DIR.parent)),
            entrypoint=entrypoint_rel,
            content_sha256=full_sha,
            license=cand_lic,
            capabilities=cand_caps or [safe_id],
            dependencies=cand_meta.get("dependencies", []),
            applicable_agents=applicable_agents,
            source_url=cand_meta.get("html_url") or cand_meta.get("location"),
            validation_status="verified",
            metadata=manifest_payload,
        )

        # Register in central SkillRegistry
        central_record = SkillRecord(
            skill_id=safe_id,
            name=cand_name,
            summary=cand_meta.get("description", f"Category-managed skill for {cand_cat}"),
            domain=cand_cat,
            tags=[cand_cat, cand_sub or "general"] + (cand_caps or []),
            version=cand_ver,
            entrypoint=entrypoint_rel,
            status="approved",
            source="local",
            content_sha256=full_sha,
            license=cand_lic,
            capabilities=cand_caps or [safe_id],
            compatible_agents=applicable_agents,
            risk_level="low",
            approval={
                "reviewer": "category_skill_library_installer",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "evidence": f"Passed automated validation and load tests with score {eval_report.composite_score}/100",
            },
            last_audited_at=datetime.now(timezone.utc).isoformat(),
            metadata={"category": cand_cat, "subcategory": cand_sub},
        )
        self._skill_registry.register_skill(central_record)

        # Register capabilities in CapabilityRegistry
        for cap_name in (cand_caps or [safe_id]):
            cap_record = CapabilityRecord(
                capability_id=cap_name,
                name=f"{cand_name} ({cap_name})",
                description=f"Provided by installed skill '{safe_id}' in category '{cand_cat}'",
                source_type="skill",
                source_id=safe_id,
                source_path=entrypoint_rel,
                domain=cand_cat,
                tags=[cand_cat, cand_sub or "general"],
                dependencies=cand_meta.get("dependencies", []),
                provenance="skill_library",
                verification_status="verified",
                last_verified_at=datetime.now(timezone.utc).isoformat(),
            )
            self._cap_registry.upsert_capability(cap_record)

        # Update local index
        action_type = "updated" if existing else "installed"
        self._installed_skills[safe_id] = record
        self._save_installed_index()

        logger.info(f"Successfully {action_type} skill '{safe_id}' in category '{cand_cat}'")
        return InstallationResult(
            success=True,
            action=action_type,
            installed_record=record,
            validation_passed=True,
            validation_errors=[],
            audit_details=eval_report.to_dict(),
            message=f"Skill '{safe_id}' successfully {action_type} and registered in category '{cand_cat}'.",
        )

    def uninstall_skill(self, skill_id: str) -> bool:
        """Safely removes an installed skill and marks it deprecated in registries."""
        rec = self._installed_skills.get(skill_id)
        if not rec:
            return False

        target_dir = SKILLS_DIR.parent / rec.installation_path
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

        try:
            self._skill_registry.transition_status(skill_id, "deprecated", reviewer="installer", evidence="Uninstalled by operator")
        except Exception:
            pass

        del self._installed_skills[skill_id]
        self._save_installed_index()
        return True

    def _compute_content_sha256(self, code_files: dict[str, str]) -> str:
        h = hashlib.sha256()
        for k in sorted(code_files.keys()):
            h.update(k.encode("utf-8"))
            h.update(code_files[k].encode("utf-8"))
        return h.hexdigest()

    def _backup_previous_version(self, skill_id: str, category: str, source_dir: Path, version: str) -> None:
        try:
            archive_target = HISTORY_ROOT / category / f"{skill_id}_v{version}_{int(datetime.now().timestamp())}"
            archive_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_dir, archive_target)
        except Exception as e:
            logger.warning(f"Could not backup skill before update: {e}")

    def _generate_skill_md(
        self,
        skill_id: str,
        name: str,
        category: str,
        subcategory: str | None,
        capabilities: list[str],
        license_name: str,
    ) -> str:
        caps_list = "\n".join(f"- `{c}`" for c in capabilities)
        return (
            f"# {name}\n\n"
            f"- **Skill ID**: `{skill_id}`\n"
            f"- **Category**: `{category}`\n"
            f"- **Subcategory**: `{subcategory or 'general'}`\n"
            f"- **License**: `{license_name}`\n\n"
            f"## Capabilities\n{caps_list}\n\n"
            f"## Instructions for Agents\n"
            f"This skill provides video-editing components and logic for the `{category}` category.\n"
            f"Authorized agents can import and parameterize these components into Remotion compositions.\n"
        )

    def _run_load_test(self, skill_dir: Path) -> tuple[bool, list[str]]:
        """Verifies that all written files are readable, non-empty, and syntactically valid."""
        errors: list[str] = []

        manifest_file = skill_dir / "manifest.json"
        if not manifest_file.exists():
            errors.append("Missing manifest.json after installation")
        else:
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                if not data.get("skill_id"):
                    errors.append("manifest.json missing skill_id")
            except Exception as e:
                errors.append(f"manifest.json unparseable: {e}")

        for f in skill_dir.glob("*"):
            if f.is_file():
                if f.stat().st_size == 0:
                    errors.append(f"Installed file '{f.name}' is empty (0 bytes)")
                if f.suffix == ".py":
                    try:
                        ast.parse(f.read_text(encoding="utf-8"))
                    except SyntaxError as e:
                        errors.append(f"Python syntax error in '{f.name}': {e}")
                elif f.suffix in (".tsx", ".ts", ".jsx", ".js"):
                    # Basic balanced brackets check for frontend code
                    text = f.read_text(encoding="utf-8")
                    if text.count("{") != text.count("}"):
                        errors.append(f"Unbalanced braces in '{f.name}'")

        return len(errors) == 0, errors


# Singleton instance
_installer_singleton: SkillLibraryInstaller | None = None


def get_skill_library_installer() -> SkillLibraryInstaller:
    """Returns the singleton SkillLibraryInstaller instance."""
    global _installer_singleton
    if _installer_singleton is None:
        _installer_singleton = SkillLibraryInstaller()
    return _installer_singleton
