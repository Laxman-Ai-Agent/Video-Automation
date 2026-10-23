"""Sandbox Security Policy and Resource Governance.

Enforces:
1. Strict Environment Allowlist (scrubbing all user credentials, tokens, API keys, and parent env vars).
2. Temporary Workspace Confinement and symlink escape prevention.
3. Protected Pipeline File and Registry invariant tracking.
4. Execution Resource Quotas (output byte caps, timeouts, memory bounds).
5. Explicit fail-closed policy when requested isolation backends are unavailable.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("skill_factory.sandbox_policy")

# Strict Environment Variable Allowlist
# Only system-essential variables are permitted into untrusted execution contexts.
DEFAULT_ENV_ALLOWLIST: frozenset[str] = frozenset({
    "SYSTEMROOT",
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "PYTHONPATH",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONIOENCODING",
    "PYTHONUNBUFFERED",
    "PYTHONUTF8",
    "LANG",
    "LC_ALL",
})

# Pipeline stage code that untrusted skills must never modify (the engine's own developers may)
PROTECTED_PIPELINE_DIR = "VIDEO_ENGINE/stages"

PROTECTED_SYSTEM_PATHS: tuple[str, ...] = (
    "SYSTEM/skills/catalog.json",
    "SYSTEM/skills/.catalog.lock",
    "SYSTEM/registries/",
    "SYSTEM/agents/capability_finder/learning/",
)


class SandboxSecurityError(Exception):
    """Raised when untrusted skill code attempts a sandbox boundary breach."""
    pass


@dataclass
class SandboxPolicy:
    """Security boundaries and governance rules for skill behavioral execution."""
    isolation_backend: str = "auto"
    require_container: bool = False
    fail_closed_on_missing_backend: bool = True
    timeout_seconds: float = 5.0
    max_output_bytes: int = 65536       # 64 KB stdout/stderr max capture
    memory_limit_mb: int = 512          # 512 MB memory quota
    env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST
    allow_network: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["env_allowlist"] = sorted(list(self.env_allowlist))
        return d


def sanitize_environment(
    workspace_path: Path,
    allowlist: frozenset[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Constructs an isolated environment containing ONLY allowlisted variables.

    Never copies un-allowlisted parent environment variables, preventing secret leakage.
    """
    keys = allowlist or DEFAULT_ENV_ALLOWLIST
    clean_env: dict[str, str] = {}

    for k in keys:
        if k in os.environ:
            clean_env[k] = os.environ[k]

    # Confine temporary directories inside the isolated workspace
    tmp_dir = workspace_path / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    clean_env["TEMP"] = str(tmp_dir)
    clean_env["TMP"] = str(tmp_dir)
    clean_env["PYTHONPATH"] = str(workspace_path)
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    clean_env["PYTHONUNBUFFERED"] = "1"
    clean_env["PYTHONUTF8"] = "1"

    if extra_env:
        for k, v in extra_env.items():
            if k in keys:
                clean_env[k] = v

    return clean_env


def verify_sandbox_path_confinement(target_path: Path, sandbox_root: Path) -> Path:
    """Ensures a path resolves strictly within the designated sandbox workspace root."""
    resolved_root = sandbox_root.resolve()
    resolved_target = target_path.resolve()

    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as e:
        raise SandboxSecurityError(
            f"Path confinement breach: '{target_path}' resolves to '{resolved_target}', "
            f"which escapes sandbox root '{resolved_root}'."
        ) from e

    return resolved_target


def verify_no_symlink_escapes(directory: Path, sandbox_root: Path) -> None:
    """Recursively checks that no symlink inside directory points outside sandbox_root."""
    resolved_root = sandbox_root.resolve()
    if not directory.exists():
        return

    for item in directory.rglob("*"):
        if item.is_symlink():
            resolved_link = item.resolve()
            try:
                resolved_link.relative_to(resolved_root)
            except ValueError as e:
                raise SandboxSecurityError(
                    f"Symlink escape detected: '{item}' points to '{resolved_link}' outside sandbox root."
                ) from e


def compute_baseline_hashes(base_dir: Path | None = None) -> dict[str, str]:
    """Calculates SHA-256 baseline hashes for every pipeline stage file."""
    root = base_dir or Path.cwd()
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / PROTECTED_PIPELINE_DIR).glob("*.py"))
    }


def verify_baseline_hashes_unchanged(baseline: dict[str, str], base_dir: Path | None = None) -> None:
    """Verifies that none of the pipeline stage files were altered during sandbox execution."""
    root = base_dir or Path.cwd()
    for rel_path, expected_hash in baseline.items():
        target = root / rel_path
        if not target.exists():
            raise SandboxSecurityError(f"Pipeline stage file was deleted: '{rel_path}'")
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise SandboxSecurityError(
                f"Pipeline stage file tampered during execution! '{rel_path}' "
                f"expected={expected_hash}, actual={actual_hash}"
            )
