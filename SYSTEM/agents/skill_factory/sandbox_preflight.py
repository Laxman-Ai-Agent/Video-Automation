"""Preflight Capability Detection for Isolation Backends.

Inspects the host platform and runtime environment to detect:
1. Docker container runtime availability and daemon responsiveness.
2. Windows Job Objects kernel support for process tree containment.
3. Operating system platform boundaries and resource limits.

Provides deterministic capability reporting for fail-closed sandbox policies.
"""
from __future__ import annotations

import ctypes
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("skill_factory.sandbox_preflight")


@dataclass
class SandboxCapabilities:
    """Detailed audit report of available isolation runtime mechanisms."""
    docker_available: bool
    docker_version: str
    docker_daemon_active: bool
    windows_job_objects_available: bool
    platform: str
    available_backends: list[str] = field(default_factory=list)
    recommended_backend: str = "none"
    diagnostics: list[str] = field(default_factory=list)
    probed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CACHED_CAPABILITIES: SandboxCapabilities | None = None


def check_docker_runtime() -> tuple[bool, str, bool, list[str]]:
    """Probes for Docker CLI executable and responsive container daemon."""
    diagnostics: list[str] = []
    docker_bin = shutil.which("docker")
    if not docker_bin:
        diagnostics.append("Docker CLI executable not found on PATH.")
        return False, "", False, diagnostics

    # 1. Check docker CLI version
    version_str = ""
    try:
        ver_proc = subprocess.run(
            [docker_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if ver_proc.returncode == 0:
            version_str = ver_proc.stdout.strip()
        else:
            diagnostics.append(f"Docker CLI returned non-zero exit code {ver_proc.returncode}: {ver_proc.stderr.strip()}")
            return False, "", False, diagnostics
    except Exception as e:
        diagnostics.append(f"Failed to query Docker CLI version: {e}")
        return False, "", False, diagnostics

    # 2. Check daemon responsiveness (docker info)
    daemon_active = False
    try:
        info_proc = subprocess.run(
            [docker_bin, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        if info_proc.returncode == 0 and info_proc.stdout.strip():
            daemon_active = True
        else:
            diagnostics.append("Docker daemon is not running or not responsive.")
    except Exception as e:
        diagnostics.append(f"Docker daemon connection check failed: {e}")

    docker_available = bool(version_str and daemon_active)
    return docker_available, version_str, daemon_active, diagnostics


def check_windows_job_objects() -> tuple[bool, list[str]]:
    """Probes Windows kernel for Job Object API support."""
    diagnostics: list[str] = []
    if sys.platform != "win32":
        diagnostics.append(f"Windows Job Objects not supported on non-Windows platform '{sys.platform}'.")
        return False, diagnostics

    try:
        kernel32 = ctypes.windll.kernel32
        if not hasattr(kernel32, "CreateJobObjectW"):
            diagnostics.append("kernel32.dll does not export CreateJobObjectW.")
            return False, diagnostics

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            diagnostics.append("kernel32.CreateJobObjectW returned NULL handle.")
            return False, diagnostics

        kernel32.CloseHandle(job)
        return True, diagnostics
    except Exception as e:
        diagnostics.append(f"Windows Job Objects probe raised exception: {e}")
        return False, diagnostics


def probe_sandbox_capabilities(force_refresh: bool = False) -> SandboxCapabilities:
    """Probes host execution environment and determines available isolation backends."""
    global _CACHED_CAPABILITIES
    if _CACHED_CAPABILITIES is not None and not force_refresh:
        return _CACHED_CAPABILITIES

    all_diagnostics: list[str] = []
    available_backends: list[str] = []

    # Probe Docker
    docker_ok, docker_ver, daemon_active, docker_diags = check_docker_runtime()
    all_diagnostics.extend(docker_diags)
    if docker_ok:
        available_backends.append("docker")

    # Probe Windows Job Objects
    job_ok, job_diags = check_windows_job_objects()
    all_diagnostics.extend(job_diags)
    if job_ok:
        available_backends.append("windows_job_object")

    # Recommend backend based on isolation fidelity
    if docker_ok:
        recommended = "docker"
    elif job_ok:
        recommended = "windows_job_object"
    else:
        recommended = "none"

    now_iso = datetime.now(timezone.utc).isoformat()
    caps = SandboxCapabilities(
        docker_available=docker_ok,
        docker_version=docker_ver,
        docker_daemon_active=daemon_active,
        windows_job_objects_available=job_ok,
        platform=sys.platform,
        available_backends=available_backends,
        recommended_backend=recommended,
        diagnostics=all_diagnostics,
        probed_at=now_iso,
    )

    _CACHED_CAPABILITIES = caps
    logger.info(
        f"Sandbox capabilities probed: platform={sys.platform}, docker={docker_ok}, "
        f"job_objects={job_ok}, recommended={recommended}"
    )
    return caps
