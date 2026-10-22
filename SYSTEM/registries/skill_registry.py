"""Authoritative Central Skill Catalog and Registry for the Multi-Agent System.

Provides:
1. Versioned SkillRecord schema with metadata, provenance, checksums, and declarative capabilities.
2. Strict lifecycle transitions (discovered -> quarantined -> draft -> review_required -> approved -> deprecated).
3. Approved-only production retrieval with load-time checksum and schema verification.
4. Path-traversal confinement guards rejecting escape from the canonical skills/ directory.
5. Static security audit detecting prompt injection, dangerous shell execution, and token leakage.
6. Traceable Reuse / Adapt / Create / Block decision engine.
7. Atomic, thread-safe persistence in skills/catalog.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core.resilience import CREDENTIAL_KINDS, redact_secrets

from SYSTEM.core import config, integrations

SkillStatus = Literal[
    "discovered",
    "quarantined",
    "draft",
    "review_required",
    "approved",
    "deprecated",
    "rejected",
]

SkillRiskLevel = Literal["low", "medium", "high", "critical"]

SKILLS_DIR = (config.PROJECT_ROOT / "SYSTEM" / "skills") if (config.PROJECT_ROOT / "SYSTEM" / "skills" / "catalog.json").exists() else (config.PROJECT_ROOT / "skills")
CATALOG_FILE = SKILLS_DIR / "catalog.json"
STAGING_DIR = SKILLS_DIR / "staging"

LEGAL_TRANSITIONS: dict[SkillStatus, set[SkillStatus]] = {
    "discovered": {"quarantined", "draft", "rejected"},
    "quarantined": {"draft", "review_required", "rejected"},
    "draft": {"review_required", "rejected"},
    "review_required": {"approved", "rejected"},
    "approved": {"deprecated"},
    "deprecated": {"approved"},  # Reactivation allowed with audit
    "rejected": set(),          # Terminal
}


class SkillSecurityError(Exception):
    """Raised when a skill path traversal or security violation is detected."""
    pass


class InvalidSkillTransitionError(Exception):
    """Raised on invalid lifecycle transitions."""
    pass


class SkillVerificationError(Exception):
    """Raised when checksum or signature verification fails."""
    pass


@dataclass
class SkillRecord:
    skill_id: str
    name: str
    summary: str
    domain: str
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    entrypoint: str = ""  # Relative to skills/
    status: SkillStatus = "draft"
    source: Literal["local", "internal", "remote"] = "local"
    repository_url: str | None = None
    commit_sha: str | None = None
    content_sha256: str = ""
    license: str = "Apache-2.0"
    license_evidence: str = ""
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    compatible_agents: list[str] = field(default_factory=list)
    compatible_project_modes: list[str] = field(default_factory=lambda: ["motion_only"])
    input_contracts: dict[str, Any] = field(default_factory=dict)
    output_contracts: dict[str, Any] = field(default_factory=dict)
    risk_level: SkillRiskLevel = "low"
    approval: dict[str, Any] | None = None
    last_audited_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillRecord:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


def verify_skill_path_confinement(rel_path: str, allow_staging: bool = True) -> Path:
    """Ensures a given relative path resolves strictly inside skills/ or skills/staging.
    Rejects path traversal attacks (e.g. '../', '..\\').
    """
    if not rel_path or ".." in rel_path:
        raise SkillSecurityError(f"Path traversal detected in skill path: {rel_path!r}")

    if rel_path.startswith("/") or rel_path.startswith("\\") or Path(rel_path).is_absolute():
        raise SkillSecurityError(f"Absolute path disallowed for skill entrypoint: {rel_path!r}")

    normalized = Path(rel_path.replace("\\", "/"))

    target = (SKILLS_DIR / normalized).resolve()
    base_skills = SKILLS_DIR.resolve()

    try:
        target.relative_to(base_skills)
    except ValueError:
        raise SkillSecurityError(f"Skill path escapes canonical skills root: {target}")

    if not allow_staging and STAGING_DIR.resolve() in target.parents:
        raise SkillSecurityError(f"Access to quarantined staging area disallowed: {target}")

    return target


def compute_file_sha256(path: Path) -> str:
    """The ONE content hash of a skill file (registration, seeding and verification all use it): SHA-256 of its text with universal newlines, so a file checked out with CRLF (git on Windows)
    and the same file with LF have the same hash. (The raw-bytes hash used for registration and the text hash used for verification differed, so a CRLF checkout failed verification.)"""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def audit_skill_content(content: str, filename: str = "") -> dict[str, Any]:
    """Static security and content audit of skill markdown or code.
    Detects:
    - Prompt injections (jailbreaks, hidden instructions)
    - Dangerous system/shell execution commands
    - Token/secret exposure patterns
    - Path traversal attempts
    - Suspicious base64 obfuscation
    """
    findings: list[str] = []
    risk_level: SkillRiskLevel = "low"

    # 1. Prompt Injection Checks
    injection_patterns = [
        (r"(?i)ignore\s+all\s+(previous|prior)\s+instructions", "Prompt injection: ignore previous instructions"),
        (r"(?i)system\s+prompt\s+override", "Prompt injection: system prompt override attempt"),
        (r"(?i)you\s+are\s+now\s+in\s+developer\s+mode", "Prompt injection: developer mode escape"),
        (r"(?i)disregard\s+system\s+rules", "Prompt injection: disregard rules"),
    ]
    for pattern, desc in injection_patterns:
        if re.search(pattern, content):
            findings.append(desc)
            risk_level = "critical"

    # 2. Dangerous Execution / Shell Commands
    dangerous_patterns = [
        (r"(?i)\bos\.system\s*\(", "Dangerous call: os.system execution"),
        (r"(?i)\bsubprocess\.(Popen|run|call)\b.*shell\s*=\s*True", "Dangerous call: subprocess with shell=True"),
        (r"(?i)\beval\s*\(", "Dangerous call: eval() execution"),
        (r"(?i)\bexec\s*\(", "Dangerous call: exec() execution"),
        (r"(?i)\brm\s+-rf\b", "Dangerous command: rm -rf"),
        (r"(?i)\bformat\s+c:\b", "Dangerous command: format drive"),
        (r"(?i)\bcurl\s+.*\|\s*(bash|sh)\b", "Dangerous pattern: piping remote curl into shell"),
    ]
    for pattern, desc in dangerous_patterns:
        if re.search(pattern, content):
            findings.append(desc)
            if risk_level != "critical":
                risk_level = "high"

    # 3. Secret / Token Exposure
    for kind in sorted(CREDENTIAL_KINDS.intersection(redact_secrets(content)[1])):
        findings.append(f"Exposed secret: {kind} pattern")
        if risk_level != "critical":
            risk_level = "high"

    # 4. Path Traversal in references
    if "../" in content or "..\\" in content:
        findings.append("Suspicious path traversal reference (../ or ..\\)")
        if risk_level not in ("critical", "high"):
            risk_level = "medium"

    return {
        "passed": len(findings) == 0,
        "risk_level": risk_level,
        "findings": findings,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
    }


class SkillRegistry:
    """Canonical service managing registered skills, discovery, audits, and selection."""

    verify_skill_path_confinement = staticmethod(verify_skill_path_confinement)

    def __init__(self) -> None:
        self._skills: dict[str, SkillRecord] = {}
        self._lock = threading.RLock()
        self._initialized = False
        self._synced_seeds: object = None

    def initialize(self) -> None:
        """Loads catalog from disk or initializes defaults."""
        with self._lock:
            if self._initialized:
                self._sync_seed_provider()
                return

            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            STAGING_DIR.mkdir(parents=True, exist_ok=True)

            if CATALOG_FILE.exists():
                try:
                    data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
                    for s_id, s_data in data.get("skills", {}).items():
                        self._skills[s_id] = SkillRecord.from_dict(s_data)
                except Exception:
                    pass

            # Ensure canonical seed skills exist
            self._ensure_seed_skills()
            self._save()
            self._initialized = True

    def _sync_seed_provider(self) -> None:
        """Seed skills a domain project provides join the catalog whenever it connects (checked on every use after start-up)."""
        provided = integrations.get("skill_seeds")
        if provided is not None and provided is not self._synced_seeds:
            self._ensure_seed_skills()
            self._save()

    def _ensure_seed_skills(self) -> None:
        """Seeds the connected domain project's initial verified core skills if absent (the video project's 21); the Agent System has none of its own."""
        provided = integrations.get("skill_seeds")
        self._synced_seeds = provided
        seed_defs = provided or []

        now = datetime.now(timezone.utc).isoformat()
        for sid, name, domain, summary, rel_path, caps, tags, agents in seed_defs:
            if sid not in self._skills:
                full_path = SKILLS_DIR / rel_path
                sha = compute_file_sha256(full_path) if full_path.exists() else ""
                self._skills[sid] = SkillRecord(
                    skill_id=sid,
                    name=name,
                    summary=summary,
                    domain=domain,
                    tags=tags,
                    version="1.0.0",
                    entrypoint=rel_path,
                    status="approved",
                    source="local",
                    content_sha256=sha,
                    license="Apache-2.0",
                    license_evidence="Authored internally for Dark World Video Generation Agent.",
                    capabilities=caps,
                    compatible_agents=agents,
                    risk_level="low",
                    approval={
                        "reviewer": "system_bootstrap",
                        "timestamp": now,
                        "evidence": "Canonical core skill verification suite",
                    },
                    last_audited_at=now,
                    created_at=now,
                    updated_at=now,
                )

    def _save(self) -> None:
        """Atomically saves catalog to disk."""
        tmp = CATALOG_FILE.with_suffix(".json.tmp")
        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "skills": {k: v.to_dict() for k, v in sorted(self._skills.items())},
        }
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, CATALOG_FILE)

    def register_skill(self, record: SkillRecord) -> SkillRecord:
        """Registers a new skill record. Validates entrypoint path and status."""
        self.initialize()
        with self._lock:
            if not record.skill_id or not re.match(r"^[a-z0-9_.-]+$", record.skill_id):
                raise ValueError(f"Invalid path-safe skill_id: {record.skill_id!r}")

            if record.entrypoint:
                target_path = verify_skill_path_confinement(record.entrypoint)
                if target_path.exists():
                    actual_sha = compute_file_sha256(target_path)
                    if record.content_sha256 and record.content_sha256 != actual_sha:
                        raise SkillVerificationError(
                            f"Content SHA256 mismatch: declared {record.content_sha256} vs actual {actual_sha}"
                        )
                    record.content_sha256 = actual_sha

            now = datetime.now(timezone.utc).isoformat()
            if not record.created_at:
                record.created_at = now
            record.updated_at = now

            self._skills[record.skill_id] = record
            self._save()
            return record

    def get_skill(self, skill_id: str, version: str | None = None, load_content: bool = True) -> tuple[SkillRecord, str]:
        """Retrieves a skill and optionally loads its validated instruction content.
        Enforces approved-only status for production loading and verifies content hash.
        """
        self.initialize()
        with self._lock:
            skill = self._skills.get(skill_id)
            if not skill:
                if skill_id == "media_probe":
                    skill = self._skills.get("media.ffmpeg_operations")
                elif skill_id == "media.ffmpeg_operations":
                    skill = self._skills.get("media_probe")
            if not skill:
                raise KeyError(f"Skill not found in catalog: {skill_id}")

            if version and skill.version != version:
                raise ValueError(f"Skill version mismatch: requested {version}, available {skill.version}")

            if skill.status != "approved":
                raise SkillSecurityError(
                    f"Skill '{skill_id}' is not approved for execution (status: {skill.status})"
                )

            content = ""
            if load_content and skill.entrypoint:
                target_path = verify_skill_path_confinement(skill.entrypoint, allow_staging=False)
                if not target_path.exists():
                    raise FileNotFoundError(f"Skill entrypoint file missing: {skill.entrypoint}")

                content = target_path.read_text(encoding="utf-8")
                actual_sha = compute_file_sha256(target_path)
                if skill.content_sha256 and actual_sha != skill.content_sha256:
                    raise SkillVerificationError(
                        f"Skill '{skill_id}' content checksum failure: stored {skill.content_sha256} vs disk {actual_sha}"
                    )

            return skill, content

    def _get_agent_skills_dirs(self, agent_id: str) -> list[Path]:
        """Resolves existing private skill directory paths for a given agent ID."""
        dirs = []
        base_dir = config.PROJECT_ROOT / "SYSTEM" / "agents"
        candidates = [
            base_dir / "video_generation_agents" / agent_id / "skills",
            base_dir / "system_agents" / agent_id / "skills",
            base_dir / agent_id / "skills",
        ]
        for d in candidates:
            if d.exists() and d.is_dir():
                dirs.append(d)
        return dirs

    def _resolve_local_agent_skill(
        self,
        agent_id: str,
        skill_name: str,
        load_content: bool = True,
    ) -> tuple[SkillRecord, str] | None:
        """Attempts to resolve a private skill strictly from the owning agent's directory."""
        if not re.match(r"^[a-z0-9_.-]+$", skill_name):
            return None

        for s_dir in self._get_agent_skills_dirs(agent_id):
            candidates = [
                s_dir / skill_name / "SKILL.md",
                s_dir / f"{skill_name}.md",
                s_dir / skill_name / "skill.py",
                s_dir / f"{skill_name}.py",
            ]
            for target in candidates:
                if target.exists() and target.is_file():
                    # Strict confinement check
                    resolved = target.resolve()
                    if s_dir.resolve() not in resolved.parents and resolved != s_dir.resolve():
                        raise SkillSecurityError(f"Path traversal detected in local skill: {target}")

                    content = ""
                    if load_content:
                        try:
                            content = target.read_text(encoding="utf-8")
                        except Exception:
                            continue

                    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else ""
                    
                    title = skill_name
                    domain = "agent_local"
                    summary = f"Agent-local private skill for {agent_id}"
                    version = "1.0.0"
                    tags = ["local", agent_id]
                    caps = [skill_name]
                    
                    if target.suffix == ".md" and content.startswith("---"):
                        try:
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                fm_text = parts[1]
                                for line in fm_text.splitlines():
                                    if ":" in line and not line.strip().startswith("-"):
                                        k, v = line.split(":", 1)
                                        k = k.strip()
                                        v = v.strip().strip("'\"")
                                        if k == "name":
                                            title = v
                                        elif k == "domain":
                                            domain = v
                                        elif k == "version":
                                            version = v
                                        elif k == "summary":
                                            summary = v
                        except Exception:
                            pass

                    rec = SkillRecord(
                        skill_id=skill_name,
                        name=title,
                        summary=summary,
                        domain=domain,
                        tags=tags,
                        version=version,
                        entrypoint=str(target),
                        status="approved",
                        source="local",
                        content_sha256=content_sha,
                        license="Internal-Proprietary",
                        license_evidence=f"Private skill owned by agent {agent_id}",
                        capabilities=caps,
                        compatible_agents=[agent_id],
                        risk_level="low",
                        last_audited_at=datetime.now(timezone.utc).isoformat(),
                        metadata={"scope": "local", "owner_agent_id": agent_id, "is_local": True},
                    )
                    return rec, content
        return None

    def get_agent_skill(
        self,
        agent_id: str,
        skill_name: str,
        version: str | None = None,
        load_content: bool = True,
    ) -> tuple[SkillRecord, str]:
        """Scoped skill resolution:
        1. Resolve the requested agent's installed private skill when it exists and is valid.
        2. Otherwise fall back to the appropriate central shared skill.
        3. If neither exists, raise KeyError.
        """
        self.initialize()
        # 1. Check local private skill
        local_res = self._resolve_local_agent_skill(agent_id, skill_name, load_content=load_content)
        if local_res is not None:
            rec, content = local_res
            if version and rec.version != version:
                raise ValueError(f"Local skill version mismatch: requested {version}, found {rec.version}")
            return rec, content

        # 2. Central shared skill fallback
        with self._lock:
            skill = self._skills.get(skill_name)
            if not skill:
                if skill_name == "media_probe":
                    skill = self._skills.get("media.ffmpeg_operations")
                elif skill_name == "media.ffmpeg_operations":
                    skill = self._skills.get("media_probe")
            if not skill:
                raise KeyError(
                    f"Skill '{skill_name}' not found for agent '{agent_id}' in local directory or central library."
                )

            # Check authorization if compatible_agents is defined and not wildcard
            if skill.compatible_agents and agent_id not in skill.compatible_agents:
                raise SkillSecurityError(
                    f"Unauthorized access: Agent '{agent_id}' is not permitted to access central skill '{skill_name}'. "
                    f"Authorized agents: {skill.compatible_agents}"
                )

            rec, content = self.get_skill(skill_name, version=version, load_content=load_content)
            rec_dict = rec.to_dict()
            rec_dict["metadata"] = dict(rec.metadata)
            rec_dict["metadata"]["scope"] = "central"
            scoped_rec = SkillRecord.from_dict(rec_dict)
            return scoped_rec, content

    def resolve_agent_skill(self, agent_id: str, skill_name: str) -> dict[str, Any]:
        """Returns structured capability resolution result without throwing KeyError."""
        try:
            rec, content = self.get_agent_skill(agent_id, skill_name, load_content=False)
            return {
                "status": "resolved",
                "scope": rec.metadata.get("scope", "local"),
                "skill_id": rec.skill_id,
                "version": rec.version,
                "record": rec.to_dict(),
            }
        except KeyError as e:
            return {
                "status": "missing_capability",
                "agent_id": agent_id,
                "skill_name": skill_name,
                "reason": str(e),
            }
        except SkillSecurityError as e:
            return {
                "status": "blocked_security",
                "agent_id": agent_id,
                "skill_name": skill_name,
                "reason": str(e),
            }

    def search_skills(
        self,
        query: str = "",
        agent_id: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        status: SkillStatus | None = "approved",
    ) -> list[SkillRecord]:
        """Deterministic search and filter over registered skills."""
        self.initialize()
        with self._lock:
            results: list[SkillRecord] = []
            q = query.lower().strip()

            for skill in self._skills.values():
                if status and skill.status != status:
                    continue
                if domain and skill.domain.lower() != domain.lower():
                    continue
                if tag and tag.lower() not in [t.lower() for t in skill.tags]:
                    continue
                if agent_id and agent_id not in skill.compatible_agents:
                    continue

                if q:
                    matched = (
                        q in skill.skill_id.lower()
                        or q in skill.name.lower()
                        or q in skill.summary.lower()
                        or any(q in t.lower() for t in skill.tags)
                        or any(q in c.lower() for c in skill.capabilities)
                    )
                    if not matched:
                        continue

                results.append(skill)

            # If agent_id provided, also search that agent's private directory (local overrides central)
            if agent_id:
                seen_local = set()
                for s_dir in self._get_agent_skills_dirs(agent_id):
                    for item in s_dir.iterdir():
                        if item.name.startswith("."):
                            continue
                        skill_name = item.stem if item.is_file() else item.name
                        if skill_name in seen_local:
                            continue
                        local_res = self._resolve_local_agent_skill(agent_id, skill_name, load_content=False)
                        if local_res:
                            l_rec, _ = local_res
                            seen_local.add(l_rec.skill_id)
                            if domain and l_rec.domain.lower() != domain.lower():
                                continue
                            if tag and tag.lower() not in [t.lower() for t in l_rec.tags]:
                                continue
                            if q:
                                matched = (
                                    q in l_rec.skill_id.lower()
                                    or q in l_rec.name.lower()
                                    or q in l_rec.summary.lower()
                                    or any(q in t.lower() for t in l_rec.tags)
                                    or any(q in c.lower() for c in l_rec.capabilities)
                                )
                                if not matched:
                                    continue
                            # Local shadows central on collision
                            results = [r for r in results if r.skill_id != l_rec.skill_id]
                            results.append(l_rec)

            return sorted(results, key=lambda s: s.skill_id)

    def list_skills(self, status: SkillStatus | None = "approved") -> list[SkillRecord]:
        """Returns all registered skills, optionally filtered by status."""
        self.initialize()
        with self._lock:
            if status is None:
                return list(self._skills.values())
            return [s for s in self._skills.values() if s.status == status]

    @staticmethod
    def audit_skill_content(content: str, filename: str = "") -> dict[str, Any]:
        """Performs static security and safety audit on skill content."""
        return audit_skill_content(content, filename=filename)

    def transition_status(
        self,
        skill_id: str,
        new_status: SkillStatus,
        reviewer: str = "",
        evidence: str = "",
    ) -> SkillRecord:
        """Transitions skill lifecycle status adhering strictly to allowed progressions."""
        self.initialize()
        with self._lock:
            skill = self._skills.get(skill_id)
            if not skill:
                raise KeyError(f"Skill not found: {skill_id}")

            current = skill.status
            if new_status not in LEGAL_TRANSITIONS.get(current, set()):
                raise InvalidSkillTransitionError(
                    f"Illegal skill transition for '{skill_id}': cannot transition from '{current}' to '{new_status}'"
                )

            now = datetime.now(timezone.utc).isoformat()
            if new_status == "approved":
                if not reviewer or not evidence:
                    raise SkillSecurityError("Approval requires explicit non-empty reviewer and evidence")
                skill.approval = {
                    "reviewer": reviewer,
                    "timestamp": now,
                    "evidence": evidence,
                }
                skill.last_audited_at = now

            skill.status = new_status
            skill.updated_at = now
            self._save()
            return skill

    def resolve_skill_decision(
        self,
        objective: str,
        agent_id: str,
        domain: str | None = None,
        tags: list[str] | None = None,
        allow_adapt: bool = True,
    ) -> dict[str, Any]:
        """Evaluates Reuse / Adapt / Create / Block decision for an agent's task objective."""
        self.initialize()
        tags = tags or []
        candidates = self.search_skills(
            query=objective,
            agent_id=agent_id,
            domain=domain,
            status="approved",
        )

        # 1. Exact or High-Relevance Reuse
        if candidates:
            best = candidates[0]
            return {
                "action": "reuse",
                "skill_id": best.skill_id,
                "version": best.version,
                "reason": f"Approved compatible skill '{best.skill_id}' fully covers objective.",
                "provenance": {
                    "source": best.source,
                    "content_sha256": best.content_sha256,
                    "license": best.license,
                },
                "alternatives": [c.skill_id for c in candidates[1:3]],
            }

        # 2. Check for Adaptable Skills in same domain
        if allow_adapt and domain:
            domain_skills = self.search_skills(domain=domain, status="approved")
            for cand in domain_skills:
                # Permissive license check for adaptation
                if cand.license in ("Apache-2.0", "MIT", "BSD-3-Clause", "CC-BY-4.0"):
                    return {
                        "action": "adapt",
                        "base_skill_id": cand.skill_id,
                        "suggested_version": f"{cand.version}-adapted",
                        "reason": f"Skill '{cand.skill_id}' in domain '{domain}' can be safely adapted with permissive license {cand.license}.",
                        "provenance": {"source_skill_id": cand.skill_id, "license": cand.license},
                        "alternatives": [],
                    }

        # 3. Create or Block
        return {
            "action": "create",
            "reason": f"No approved existing skill covers objective '{objective}'. Creating a new skill is justified.",
            "recommended_domain": domain or "general",
            "rejected_alternatives": [s.skill_id for s in self.search_skills(status="approved")[:3]],
        }

    def stage_external_candidate(
        self,
        filename: str,
        raw_content: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Safely writes external content into skills/staging/ and runs static security audit.
        Never auto-approves external content.
        """
        self.initialize()
        if ".." in filename or "/" in filename or "\\" in filename:
            raise SkillSecurityError("Invalid filename for staging: directory traversal characters rejected")

        staged_path = STAGING_DIR / filename
        staged_path.write_bytes(raw_content.encode("utf-8"))

        audit_result = audit_skill_content(raw_content, filename=filename)
        sha = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

        skill_id = metadata.get("skill_id", f"staged.{filename.split('.')[0]}")
        rec = SkillRecord(
            skill_id=skill_id,
            name=metadata.get("name", filename),
            summary=metadata.get("summary", "External candidate under quarantine"),
            domain=metadata.get("domain", "external"),
            version=metadata.get("version", "0.1.0"),
            entrypoint=f"staging/{filename}",
            status="quarantined",
            source="remote",
            repository_url=metadata.get("repository_url"),
            commit_sha=metadata.get("commit_sha"),
            content_sha256=sha,
            license=metadata.get("license", "Unknown"),
            risk_level=audit_result["risk_level"],
            metadata={"audit": audit_result},
        )
        self.register_skill(rec)
        return {
            "skill_id": skill_id,
            "status": "quarantined",
            "staged_path": str(staged_path),
            "content_sha256": sha,
            "audit": audit_result,
            "note": "Content quarantined. Cannot be used in production without manual review and promotion.",
        }


# Authoritative singleton
registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """Returns the authoritative SkillRegistry singleton instance."""
    return registry
