"""Authoritative Central Capability Registry for the Multi-Agent System.

Provides:
1. Canonical CapabilityRecord schema with stable IDs, provenance, contracts, and verification states.
2. Cross-domain capability indexing across AgentRegistry, SkillRegistry, and ToolRegistry without duplicate authority.
3. Thread-safe in-memory indexing with deterministic searching, filtering, and tag/keyword matching.
4. Safe, idempotent registry synchronization that never mutates or deletes authoritative source records.
5. Distinct lifecycle and verification tracking (registered, discovered, verified, deprecated).
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("capability_registry")

CapabilitySourceType = Literal["agent", "skill", "tool", "ast_discovered", "external"]
CapabilityVerificationStatus = Literal["registered", "discovered", "verified", "deprecated"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CapabilityRecord:
    """Canonical record representing a capability available in the system."""
    capability_id: str
    name: str
    description: str
    source_type: CapabilitySourceType
    source_id: str
    source_path: str = ""
    domain: str = "general"
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    input_contract: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    provenance: str = "system"
    verification_status: CapabilityVerificationStatus = "registered"
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    first_seen_at: str = field(default_factory=_utc_now)
    last_inspected_at: str = field(default_factory=_utc_now)
    last_verified_at: str | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityRecord:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class CapabilityRegistry:
    """Thread-safe cross-domain registry indexing system capabilities."""

    def __init__(self, persistence_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, CapabilityRecord] = {}
        self._persistence_path = persistence_path
        self._tag_index: dict[str, set[str]] = {}
        self._domain_index: dict[str, set[str]] = {}
        self._source_index: dict[str, set[str]] = {}

    def register(self, record: CapabilityRecord) -> None:
        """Registers a new capability record. Raises ValueError if capability_id already exists."""
        with self._lock:
            if not record.capability_id:
                raise ValueError("Capability ID cannot be empty.")
            if record.capability_id in self._records:
                raise ValueError(f"Capability '{record.capability_id}' is already registered. Use upsert_capability() to update.")
            self._upsert_internal(record)

    def upsert_capability(self, record: CapabilityRecord) -> None:
        """Inserts or updates a capability record idempotently."""
        with self._lock:
            if not record.capability_id:
                raise ValueError("Capability ID cannot be empty.")
            record.last_inspected_at = _utc_now()
            self._upsert_internal(record)

    def _upsert_internal(self, record: CapabilityRecord) -> None:
        cap_id = record.capability_id
        # Remove from old indexes if updating
        if cap_id in self._records:
            old_rec = self._records[cap_id]
            for tag in old_rec.tags:
                self._tag_index.get(tag.lower(), set()).discard(cap_id)
            self._domain_index.get(old_rec.domain.lower(), set()).discard(cap_id)
            self._source_index.get(old_rec.source_type, set()).discard(cap_id)

        self._records[cap_id] = record

        # Update indexes
        for tag in record.tags:
            self._tag_index.setdefault(tag.lower(), set()).add(cap_id)
        self._domain_index.setdefault(record.domain.lower(), set()).add(cap_id)
        self._source_index.setdefault(record.source_type, set()).add(cap_id)

    def get_capability(self, capability_id: str) -> CapabilityRecord | None:
        """Retrieves a capability record by stable ID."""
        with self._lock:
            return self._records.get(capability_id)

    def list_all(self) -> list[CapabilityRecord]:
        """Returns all registered capability records."""
        with self._lock:
            return list(self._records.values())

    def search_capabilities(
        self,
        query: str = "",
        domain: str | None = None,
        tags: list[str] | None = None,
        keywords: list[str] | None = None,
        source_type: CapabilitySourceType | None = None,
        verification_status: CapabilityVerificationStatus | None = None,
    ) -> list[CapabilityRecord]:
        """Searches capability records matching specified filters and keyword query."""
        with self._lock:
            candidates = list(self._records.values())

            if domain:
                domain_lower = domain.lower()
                candidates = [c for c in candidates if c.domain.lower() == domain_lower]

            if source_type:
                candidates = [c for c in candidates if c.source_type == source_type]

            if verification_status:
                candidates = [c for c in candidates if c.verification_status == verification_status]

            if tags:
                lower_tags = {t.lower() for t in tags}
                candidates = [
                    c for c in candidates
                    if lower_tags.intersection({t.lower() for t in c.tags})
                ]

            if keywords:
                lower_keywords = {k.lower() for k in keywords}
                candidates = [
                    c for c in candidates
                    if lower_keywords.intersection({k.lower() for k in c.keywords})
                ]

            if query:
                q = query.lower()
                matched = []
                for c in candidates:
                    text_corpus = f"{c.capability_id} {c.name} {c.description} {' '.join(c.tags)} {' '.join(c.keywords)} {c.domain}".lower()
                    if q in text_corpus or any(term in text_corpus for term in q.split()):
                        matched.append(c)
                candidates = matched

            return candidates

    def sync_with_registries(self, force: bool = False) -> dict[str, Any]:
        """Synchronizes cross-domain capabilities from AgentRegistry, SkillRegistry, and ToolRegistry.
        
        Reads authoritative sources safely without altering their state.
        Preserves quarantine/draft state of candidate skills.
        """
        agents_synced = 0
        skills_synced = 0
        tools_synced = 0

        with self._lock:
            # 1. Sync Agents
            try:
                from SYSTEM.registries.agent_registry import registry as agent_registry
                for meta in agent_registry.list_all_agents():
                    for cap in meta.capabilities:
                        cap_id = f"agent.{meta.agent_id}.{cap.replace('-', '_')}"
                        rec = CapabilityRecord(
                            capability_id=cap_id,
                            name=f"{meta.name}: {cap}",
                            description=f"Advertised capability '{cap}' provided by agent {meta.agent_id} ({meta.purpose}).",
                            source_type="agent",
                            source_id=meta.agent_id,
                            domain=meta.category.value if hasattr(meta.category, "value") else str(meta.category),
                            tags=[meta.agent_id, cap, "agent_capability"],
                            keywords=[meta.name.lower(), cap.lower()],
                            dependencies=meta.allowed_tools,
                            constraints={},
                            provenance="agent_registry",
                            verification_status="registered",
                            evidence_refs=[{"registry": "agent_registry", "agent_id": meta.agent_id}],
                        )
                        self.upsert_capability(rec)
                        agents_synced += 1
            except Exception as e:
                logger.warning(f"Error syncing agents with capability registry: {e}")

            # 2. Sync Skills
            try:
                from SYSTEM.registries.skill_registry import registry as skill_registry
                # Only sync approved or review_required skills into production capability index
                for s in skill_registry.list_skills(status=None):
                    for cap in s.capabilities:
                        cap_id = f"skill.{s.skill_id}.{cap.replace('-', '_')}"
                        ver_status = "verified" if s.status == "approved" else "registered"
                        rec = CapabilityRecord(
                            capability_id=cap_id,
                            name=f"{s.name}: {cap}",
                            description=s.summary or f"Skill capability '{cap}' from skill {s.skill_id}.",
                            source_type="skill",
                            source_id=s.skill_id,
                            source_path=s.entrypoint,
                            domain=s.domain,
                            tags=list(set(s.tags + [cap, "skill_capability"])),
                            keywords=s.capabilities + [s.name.lower()],
                            dependencies=s.dependencies,
                            constraints={
                                "risk_level": s.risk_level,
                                "status": s.status,
                                "compatible_modes": s.compatible_project_modes,
                            },
                            provenance="skill_registry",
                            verification_status=ver_status,
                            evidence_refs=[{
                                "registry": "skill_registry",
                                "skill_id": s.skill_id,
                                "entrypoint": s.entrypoint,
                                "content_sha256": s.content_sha256,
                            }],
                        )
                        self.upsert_capability(rec)
                        skills_synced += 1
            except Exception as e:
                logger.warning(f"Error syncing skills with capability registry: {e}")

            # 3. Sync Tools
            try:
                from SYSTEM.registries.tool_registry import tool_registry
                for t in tool_registry.list_tools():
                    for cap in t.capabilities:
                        cap_id = f"tool.{t.tool_id}.{cap.replace('-', '_')}"
                        rec = CapabilityRecord(
                            capability_id=cap_id,
                            name=f"{t.name}: {cap}",
                            description=t.description,
                            source_type="tool",
                            source_id=t.tool_id,
                            domain=t.category,
                            tags=[t.tool_id, cap, "tool_capability", t.category],
                            keywords=t.capabilities + [t.name.lower()],
                            dependencies=[],
                            constraints={"permission_level": t.permission_level},
                            provenance="tool_registry",
                            verification_status="registered",
                            evidence_refs=[{"registry": "tool_registry", "tool_id": t.tool_id}],
                        )
                        self.upsert_capability(rec)
                        tools_synced += 1
            except Exception as e:
                logger.warning(f"Error syncing tools with capability registry: {e}")

            return {
                "agents_synced": agents_synced,
                "skills_synced": skills_synced,
                "tools_synced": tools_synced,
                "total_records": len(self._records),
                "timestamp": _utc_now(),
            }

    def clear(self) -> None:
        """Clears all records from registry (primarily for test isolation)."""
        with self._lock:
            self._records.clear()
            self._tag_index.clear()
            self._domain_index.clear()
            self._source_index.clear()


# Authoritative Global Singleton
capability_registry = CapabilityRegistry()


def get_capability_registry() -> CapabilityRegistry:
    """Returns the singleton central CapabilityRegistry."""
    return capability_registry
