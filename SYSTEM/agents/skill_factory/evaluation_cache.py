"""Content-Hash-Based Evaluation and Validation Cache for Skill Factory.

Prevents unnecessary repeated LLM calls, static audits, and behavioral tests by caching
evaluation outcomes keyed on:
1. Exact skill content SHA-256.
2. Skill specification signature.
3. Execution environment fingerprint (Python version + OS platform).
4. Security and sandbox policy version.

Any alteration to content, specification, environment, or policy strictly invalidates
the cache, guaranteeing cryptographic freshness and reproducibility.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SYSTEM.agents.skill_factory.sandbox_policy import SandboxPolicy
from SYSTEM.agents.skill_factory.specification import SkillSpecification

logger = logging.getLogger("skill_factory.evaluation_cache")

CACHE_DIR = Path(__file__).resolve().parent / "memory"
CACHE_FILE = CACHE_DIR / "evaluation_cache.json"


@dataclass
class CachedEvaluation:
    """Represents a cached evaluation record."""
    cache_key: str
    skill_id: str
    version: str
    content_sha256: str
    spec_hash: str
    policy_hash: str
    env_fingerprint: str
    cached_at: str
    result_type: str  # "test_result", "audit_result", "quality_result"
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvaluationCache:
    """Manages persistent content-hash caching for Skill Factory evaluations."""

    def __init__(self, cache_file: Path | None = None) -> None:
        self.cache_file = cache_file or CACHE_FILE
        self._cache: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Loads persistent cache from disk."""
        if self.cache_file.exists():
            try:
                raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._cache = raw
            except Exception as e:
                logger.warning(f"Could not load evaluation cache: {e}. Starting with empty cache.")
                self._cache = {}

    def _save(self) -> None:
        """Persists cache to disk atomically."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.cache_file.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
            tmp_file.replace(self.cache_file)
        except Exception as e:
            logger.warning(f"Failed to persist evaluation cache: {e}")

    @staticmethod
    def get_env_fingerprint() -> str:
        """Returns deterministic environment fingerprint (platform + python version)."""
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return f"{sys.platform}:{py_ver}"

    @staticmethod
    def compute_spec_hash(spec: SkillSpecification) -> str:
        """Calculates deterministic hash of the specification contract fields."""
        contract_data = {
            "skill_id": spec.skill_id,
            "version": spec.version,
            "domain": spec.domain,
            "capabilities": sorted(spec.capabilities),
            "inputs": spec.inputs,
            "outputs": spec.outputs,
            "dependencies": sorted(spec.dependencies),
            "risk_level": spec.risk_level,
        }
        raw = json.dumps(contract_data, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_policy_hash(policy: SandboxPolicy) -> str:
        """Calculates deterministic hash of sandbox governance policy."""
        raw = json.dumps(policy.to_dict(), sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def compute_cache_key(
        self,
        content_sha256: str,
        spec: SkillSpecification,
        policy: SandboxPolicy | None = None,
        result_type: str = "test_result",
    ) -> str:
        """Computes a unique composite cache key."""
        spec_hash = self.compute_spec_hash(spec)
        pol = policy or SandboxPolicy()
        policy_hash = self.compute_policy_hash(pol)
        env_fp = self.get_env_fingerprint()

        composite = f"{content_sha256}:{spec_hash}:{policy_hash}:{env_fp}:{result_type}"
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()

    def get(
        self,
        content_sha256: str,
        spec: SkillSpecification,
        policy: SandboxPolicy | None = None,
        result_type: str = "test_result",
    ) -> dict[str, Any] | None:
        """Retrieves cached result if content, spec, policy, and env are 100% matched."""
        key = self.compute_cache_key(content_sha256, spec, policy, result_type)
        entry = self._cache.get(key)
        if not entry:
            return None

        # Verify cryptographic invariants
        if entry.get("content_sha256") != content_sha256:
            return None
        if entry.get("spec_hash") != self.compute_spec_hash(spec):
            return None
        if entry.get("env_fingerprint") != self.get_env_fingerprint():
            return None

        logger.info(f"Evaluation cache HIT for skill '{spec.skill_id}' (key={key[:12]}).")
        return entry.get("data")

    def put(
        self,
        content_sha256: str,
        spec: SkillSpecification,
        data: dict[str, Any],
        policy: SandboxPolicy | None = None,
        result_type: str = "test_result",
    ) -> str:
        """Stores a fresh evaluation result under composite cryptographic key."""
        key = self.compute_cache_key(content_sha256, spec, policy, result_type)
        pol = policy or SandboxPolicy()

        record = CachedEvaluation(
            cache_key=key,
            skill_id=spec.skill_id,
            version=spec.version,
            content_sha256=content_sha256,
            spec_hash=self.compute_spec_hash(spec),
            policy_hash=self.compute_policy_hash(pol),
            env_fingerprint=self.get_env_fingerprint(),
            cached_at=datetime.now(timezone.utc).isoformat(),
            result_type=result_type,
            data=data,
        )
        self._cache[key] = record.to_dict()
        self._save()
        logger.info(f"Evaluation cached for skill '{spec.skill_id}' (key={key[:12]}).")
        return key

    def invalidate_skill(self, skill_id: str) -> int:
        """Invalidates all cached entries for a given skill_id."""
        to_del = [k for k, v in self._cache.items() if v.get("skill_id") == skill_id]
        for k in to_del:
            del self._cache[k]
        if to_del:
            self._save()
        return len(to_del)

    def clear(self) -> None:
        """Clears all cached evaluations."""
        self._cache.clear()
        self._save()


# Authoritative singleton
evaluation_cache = EvaluationCache()
