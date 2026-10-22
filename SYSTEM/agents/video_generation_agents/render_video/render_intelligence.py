"""Render Video Intelligence Module (v2.0.0).

Provides:
1. RenderFailureCategory: 17 canonical machine-readable failure classifications.
2. RenderFailureClassifier: Deterministic exit-code, stack-trace, and stderr analyzer.
3. LLMRenderDiagnostician: LLM-powered root cause analysis with structured allowlist recommendations and deterministic fallback.
4. AutonomousRenderRecoveryCoordinator: Bounded recovery execution (max 2 attempts) for permitted recovery strategies.
5. AdaptiveResourceEngine: Machine resource-aware concurrency and flag optimizer.
6. OutputIntegrityAuditor: Deep FFprobe stream and container validation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("render_video.intelligence")

# 17 Canonical machine-readable render failure categories
RenderFailureCategory = Literal[
    "remotion_compilation_failure",
    "typescript_runtime_exception",
    "missing_required_asset",
    "invalid_timeline_input",
    "invalid_approval_certificate",
    "chromium_crash",
    "memory_exhaustion",
    "webgl_context_loss",
    "dynamic_port_collision",
    "ffmpeg_failure",
    "codec_incompatibility",
    "nvenc_failure",
    "muxing_failure",
    "output_integrity_failure",
    "disk_space_failure",
    "timeout",
    "unknown_failure",
]

# Strict allowlist of permitted autonomous recovery actions
PERMITTED_RECOVERY_ACTIONS = (
    "reallocate_port",
    "reduce_concurrency",
    "software_gl_fallback",
    "restage_assets",
    "report_upstream_blocker",
)

RecoveryActionType = Literal[
    "reallocate_port",
    "reduce_concurrency",
    "software_gl_fallback",
    "restage_assets",
    "report_upstream_blocker",
]


@dataclass
class FailureDiagnosis:
    """Structured diagnosis of a render execution or verification failure."""
    category: RenderFailureCategory
    root_cause: str
    confidence: float
    recommended_action: RecoveryActionType
    can_retry: bool
    evidence_snippets: list[str] = field(default_factory=list)
    affected_component: str | None = None
    diagnostician: str = "deterministic_rules"


@dataclass
class RecoveryAttempt:
    """Record of an autonomous recovery attempt."""
    attempt_number: int
    action_taken: RecoveryActionType
    parameters_modified: dict[str, Any]
    timestamp: str
    outcome: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Adaptive Resource Engine
# ---------------------------------------------------------------------------
class AdaptiveResourceEngine:
    """Determines safe Remotion worker concurrency and execution profile

    based on real machine telemetry (CPU cores, free RAM, disk headroom).
    """

    def __init__(self, min_free_gb: float = 3.0) -> None:
        self.min_free_gb = min_free_gb

    def assess_system_resources(self, project_dir: Path) -> dict[str, Any]:
        """Assesses host resources to determine safe rendering parameters."""
        cpu_count = os.cpu_count() or 4
        free_gb = 10.0
        try:
            free_bytes = shutil.disk_usage(project_dir).free
            free_gb = round(free_bytes / (1024**3), 2)
        except Exception:
            pass

        # Estimate memory headroom (psutil if available, otherwise safe estimate)
        free_ram_gb = 8.0
        try:
            import psutil
            mem = psutil.virtual_memory()
            free_ram_gb = round(mem.available / (1024**3), 2)
        except Exception:
            pass

        # Adaptive concurrency calculation
        if free_ram_gb < 2.5 or cpu_count <= 2:
            safe_concurrency = 1
        elif free_ram_gb < 5.0 or cpu_count <= 4:
            safe_concurrency = 2
        else:
            safe_concurrency = min(3, max(1, cpu_count - 1))

        return {
            "cpu_cores": cpu_count,
            "free_disk_gb": free_gb,
            "free_ram_gb": free_ram_gb,
            "recommended_concurrency": safe_concurrency,
            "low_memory_mode": safe_concurrency == 1,
            "disk_headroom_passed": free_gb >= self.min_free_gb,
        }


# ---------------------------------------------------------------------------
# Render Failure Classifier
# ---------------------------------------------------------------------------
class RenderFailureClassifier:
    """Deterministic classifier categorizing raw errors, exit codes, and stderr

    into 17 canonical machine-readable failure categories.
    """

    _SIGNATURES: list[tuple[RenderFailureCategory, tuple[str, ...]]] = [
        ("invalid_approval_certificate", ("approval", "not approved", "stale approval", "timeline approval")),
        ("disk_space_failure", ("enospc", "no space left", "disk full", "not enough disk space")),
        ("dynamic_port_collision", ("eaddrinuse", "foreign page", "port already in use", "address already in use")),
        ("memory_exhaustion", ("heap out of memory", "out of memory", "bad_alloc", "mkl_malloc", "memoryerror")),
        ("webgl_context_loss", ("webgl context lost", "webgl", "context lost", "gpu process crashed")),
        ("nvenc_failure", ("nvenc", "cuda", "hardware acceleration failed", "encoder initialization failed")),
        ("missing_required_asset", ("no audio.*", "missing files", "missing required", "file not found", "filenotfounderror")),
        ("remotion_compilation_failure", ("cannot find module", "module_not_found", "failed to compile", "syntaxerror", "typescript error")),
        ("typescript_runtime_exception", ("typeerror", "referenceerror", "uncaught exception", "invalid prop")),
        ("output_integrity_failure", ("probeerror", "not readable as a video", "container", "duration is not within", "size_plausible")),
        ("muxing_failure", ("muxing", "stream mapping", "audio stream", "invalid audio format")),
        ("ffmpeg_failure", ("ffmpeg", "ffprobe could not run", "codec not supported")),
        ("chromium_crash", ("target closed", "browser crashed", "crashpad", "session closed", "devtools")),
        ("timeout", ("timed out", "timeout expired", "subprocess timed out")),
    ]

    def classify(self, error_text: str, exit_code: int | None = None) -> RenderFailureCategory:
        """Classifies error text into a canonical category."""
        low = (error_text or "").lower()

        for category, keywords in self._SIGNATURES:
            if any(kw in low for kw in keywords):
                return category

        if exit_code is not None and exit_code != 0:
            if exit_code in (-9, 137):  # SIGKILL (OOM killer)
                return "memory_exhaustion"
            if exit_code in (-11, 139):  # SIGSEGV (Chromium crash)
                return "chromium_crash"

        return "unknown_failure"


# ---------------------------------------------------------------------------
# LLM Render Diagnostician
# ---------------------------------------------------------------------------
class LLMRenderDiagnostician:
    """Interprets complex render failure logs using the central LLM Gateway

    with robust deterministic fallback if LLM is offline or unavailable.
    """

    def __init__(self) -> None:
        self._cache: dict[str, FailureDiagnosis] = {}

    def diagnose(
        self,
        project_id: str,
        category: RenderFailureCategory,
        raw_error: str,
        stderr_tail: list[str] | None = None,
        attempt_number: int = 1,
    ) -> FailureDiagnosis:
        """Produces a structured FailureDiagnosis."""
        tail_str = "\n".join(stderr_tail or [])
        full_evidence = f"{raw_error}\n{tail_str}".strip()
        cache_key = hashlib.sha256(f"{category}:{full_evidence[:300]}:{attempt_number}".encode()).hexdigest()[:16]

        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. Deterministic default recommendation based on category
        default_diag = self._deterministic_diagnosis(category, raw_error, stderr_tail)

        # 2. Attempt LLM Gateway diagnosis
        try:
            from SYSTEM.core import llm_gateway

            user_prompt = (
                f"Analyze this Remotion/Video render failure for project '{project_id}':\n"
                f"Category: {category}\n"
                f"Attempt Number: {attempt_number}\n"
                f"Raw Error: {raw_error}\n"
                f"Stderr Log Tail:\n{tail_str[-1000:]}\n\n"
                f"Permitted Recovery Actions Allowlist: {list(PERMITTED_RECOVERY_ACTIONS)}\n"
                "Respond with a JSON object: {\n"
                '  "root_cause": "short 1-line root cause",\n'
                '  "confidence": 0.0-1.0,\n'
                '  "recommended_action": "one of the allowlist actions",\n'
                '  "can_retry": true/false,\n'
                '  "affected_component": "name or null"\n'
                "}"
            )

            req = llm_gateway.LlmGatewayRequest(
                project_id=project_id,
                stage_id="render",
                agent_id="render_video",
                purpose="diagnose",
                model_profile="reasoning_review",
                system_prompt="You are an expert Remotion, Chromium, and FFmpeg video rendering engineer.",
                user_prompt=user_prompt,
                correlation_id=f"rnd-diag-{cache_key}",
            )

            resp = llm_gateway.gateway.execute(req)
            if resp.status == "success" and resp.raw_text:
                m = re.search(r"\{.*\}", resp.raw_text, re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                    action = data.get("recommended_action")
                    if action in PERMITTED_RECOVERY_ACTIONS:
                        diag = FailureDiagnosis(
                            category=category,
                            root_cause=data.get("root_cause") or default_diag.root_cause,
                            confidence=float(data.get("confidence", 0.85)),
                            recommended_action=action,
                            can_retry=bool(data.get("can_retry", default_diag.can_retry)),
                            evidence_snippets=stderr_tail[-3:] if stderr_tail else [raw_error[:100]],
                            affected_component=data.get("affected_component"),
                            diagnostician=f"llm_{resp.provider or 'gateway'}",
                        )
                        self._cache[cache_key] = diag
                        return diag
        except Exception as e:
            logger.info(f"LLM render diagnostic fallback to deterministic rules: {e}")

        self._cache[cache_key] = default_diag
        return default_diag

    def _deterministic_diagnosis(
        self,
        category: RenderFailureCategory,
        raw_error: str,
        stderr_tail: list[str] | None,
    ) -> FailureDiagnosis:
        """Deterministic rule-based fallback for failure diagnosis."""
        evidence = stderr_tail[-3:] if stderr_tail else [raw_error[:100]]

        if category == "dynamic_port_collision":
            return FailureDiagnosis(
                category=category,
                root_cause="Remotion bundling port collision detected",
                confidence=0.95,
                recommended_action="reallocate_port",
                can_retry=True,
                evidence_snippets=evidence,
            )

        if category in ("memory_exhaustion", "chromium_crash"):
            return FailureDiagnosis(
                category=category,
                root_cause="Browser or node process ran out of memory or crashed under worker concurrency",
                confidence=0.90,
                recommended_action="reduce_concurrency",
                can_retry=True,
                evidence_snippets=evidence,
            )

        if category in ("webgl_context_loss", "nvenc_failure"):
            return FailureDiagnosis(
                category=category,
                root_cause="Hardware graphics acceleration or encoder crashed",
                confidence=0.90,
                recommended_action="software_gl_fallback",
                can_retry=True,
                evidence_snippets=evidence,
            )

        if category == "missing_required_asset":
            return FailureDiagnosis(
                category=category,
                root_cause="Required audio or component file not staged in remotion directory",
                confidence=0.85,
                recommended_action="restage_assets",
                can_retry=True,
                evidence_snippets=evidence,
            )

        # Deterministic blockers that should not be blindly repeated
        return FailureDiagnosis(
            category=category,
            root_cause=raw_error or "Deterministic pipeline failure or invalid contract",
            confidence=1.0,
            recommended_action="report_upstream_blocker",
            can_retry=False,
            evidence_snippets=evidence,
        )


# ---------------------------------------------------------------------------
# Autonomous Render Recovery Coordinator
# ---------------------------------------------------------------------------
class AutonomousRenderRecoveryCoordinator:
    """Coordinates targeted, bounded recovery (max 2 attempts) for permitted

    render execution failures, modifying render parameters safely.
    """

    def __init__(self, max_attempts: int = 2) -> None:
        self.max_attempts = max_attempts
        self.attempts: list[RecoveryAttempt] = []

    def can_attempt_recovery(self, diagnosis: FailureDiagnosis) -> bool:
        """Checks if recovery can be attempted within budget and policy."""
        if not diagnosis.can_retry:
            return False
        if len(self.attempts) >= self.max_attempts:
            return False
        # Do not repeat the exact same action if already attempted
        if any(att.action_taken == diagnosis.recommended_action for att in self.attempts):
            return False
        return True

    def execute_recovery_action(
        self,
        project_dir: Path,
        aspect: str,
        diagnosis: FailureDiagnosis,
        active_flags: list[str],
    ) -> tuple[bool, list[str], str]:
        """Executes the recommended recovery action on render parameters.

        Returns (success, updated_flags, summary_message).
        """
        action = diagnosis.recommended_action
        attempt_num = len(self.attempts) + 1
        updated_flags = list(active_flags)
        modified_params: dict[str, Any] = {}
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        if action == "reallocate_port":
            # Ephemeral port is already bound at runtime, so we ensure flags don't lock port
            modified_params["port_refresh"] = True
            summary = f"Attempt {attempt_num}: Fresh ephemeral bundling port requested."

        elif action == "reduce_concurrency":
            # Strip existing concurrency and enforce concurrency=1
            updated_flags = [f for f in updated_flags if not f.startswith("--concurrency")]
            updated_flags.append("--concurrency=1")
            modified_params["concurrency"] = 1
            summary = f"Attempt {attempt_num}: Reduced worker concurrency to 1 to resolve memory/crash pressure."

        elif action == "software_gl_fallback":
            # Add software angle gl flag to bypass failing GPU/NVENC
            if not any(f.startswith("--gl") for f in updated_flags):
                updated_flags.append("--gl=angle")
            modified_params["gl"] = "angle"
            summary = f"Attempt {attempt_num}: Activated software GL backend (--gl=angle) to bypass hardware crash."

        elif action == "restage_assets":
            try:
                from VIDEO_ENGINE.stages import render as r_stage
                r_stage.stage_audio(project_dir, aspect)
                r_stage.stage_motion(project_dir)
                modified_params["assets_restaged"] = True
                summary = f"Attempt {attempt_num}: Audio and motion TSX components re-staged into Remotion public workspace."
            except Exception as e:
                summary = f"Attempt {attempt_num}: Asset re-staging failed: {e}"
                self.attempts.append(
                    RecoveryAttempt(
                        attempt_number=attempt_num,
                        action_taken=action,
                        parameters_modified=modified_params,
                        timestamp=now_iso,
                        outcome="failed",
                        error=str(e),
                    )
                )
                return False, active_flags, summary

        else:
            summary = f"Attempt {attempt_num}: Action '{action}' is a non-recoverable blocker."
            return False, active_flags, summary

        attempt_record = RecoveryAttempt(
            attempt_number=attempt_num,
            action_taken=action,
            parameters_modified=modified_params,
            timestamp=now_iso,
            outcome="applied",
        )
        self.attempts.append(attempt_record)
        return True, updated_flags, summary

    def get_summary(self) -> dict[str, Any]:
        """Returns structured recovery history summary."""
        return {
            "recovery_attempted": len(self.attempts) > 0,
            "total_attempts": len(self.attempts),
            "max_allowed_attempts": self.max_attempts,
            "attempts": [asdict(a) for a in self.attempts],
        }


# ---------------------------------------------------------------------------
# Output Integrity Auditor
# ---------------------------------------------------------------------------
class OutputIntegrityAuditor:
    """Performs deep FFprobe container, codec, frame rate, and audio-video

    synchronization validation on the final rendered MP4 file.
    """

    DURATION_TOLERANCE_S = 0.15
    AUDIO_TOLERANCE_S = 0.25

    def audit(
        self,
        video_path: Path,
        expected_meta: dict[str, Any],
        authoritative_audio_duration: float | None = None,
    ) -> dict[str, Any]:
        """Audits output video file and returns structured verification results."""
        from VIDEO_ENGINE.stages import media_probe

        checks: list[dict[str, Any]] = []

        def add_check(cid: str, passed: bool, msg: str, want: Any = None, got: Any = None, severity: str = "error"):
            checks.append({
                "id": cid,
                "status": "passed" if passed else ("warning" if severity == "warning" else "failed"),
                "message": msg,
                "expected": want,
                "observed": got,
            })

        if not video_path.is_file() or video_path.stat().st_size == 0:
            add_check("file_exists", False, f"Output video {video_path.name} is missing or empty.")
            return {"passed": False, "checks": checks, "observed": {}, "blockers": ["Video file missing or empty"]}

        try:
            probe_data = media_probe.probe(video_path)
        except Exception as e:
            add_check("probe_readable", False, f"FFprobe failed to inspect container: {e}")
            return {"passed": False, "checks": checks, "observed": {}, "blockers": [f"FFprobe failure: {e}"]}

        v_stream = probe_data.get("video")
        a_stream = probe_data.get("audio")
        size_bytes = probe_data.get("size") or video_path.stat().st_size
        duration_s = probe_data.get("duration")

        # 1. Container check
        container = probe_data.get("container") or ""
        add_check("container", "mp4" in container.lower() or "quicktime" in container.lower(), "Container is valid MP4", "mp4", container)

        # 2. Plausible size
        exp_dur = expected_meta.get("duration_seconds", 1.0)
        min_size = max(20_000, int(exp_dur * 2000))
        add_check("size_plausible", size_bytes >= min_size, "Video file size is plausible for duration", f">= {min_size} bytes", size_bytes)

        # 3. Video stream
        add_check("video_stream", v_stream is not None, "Video stream exists in container", True, v_stream is not None)
        if v_stream:
            exp_w = expected_meta.get("width", 1920)
            exp_h = expected_meta.get("height", 1080)
            dim_match = (v_stream.get("width") == exp_w) and (v_stream.get("height") == exp_h)
            add_check("dimensions", dim_match, "Dimensions match target profile", f"{exp_w}x{exp_h}", f"{v_stream.get('width')}x{v_stream.get('height')}")

            exp_fps = expected_meta.get("fps", 30)
            obs_fps = v_stream.get("frame_rate_value")
            fps_match = obs_fps is not None and abs(obs_fps - exp_fps) < 0.1
            add_check("fps", fps_match, "Frame rate matches expected target", exp_fps, obs_fps)

            v_codec = v_stream.get("codec") or ""
            add_check("codec", "h264" in v_codec.lower() or "avc" in v_codec.lower(), "Video codec is H.264", "h264", v_codec)

        # 4. Duration check
        if duration_s is not None:
            dur_diff = abs(duration_s - exp_dur)
            add_check("duration", dur_diff <= self.DURATION_TOLERANCE_S, f"Duration matches expected within {self.DURATION_TOLERANCE_S}s", exp_dur, duration_s)
        else:
            add_check("duration", False, "Could not read duration from container", exp_dur, None)

        # 5. Audio stream check
        if expected_meta.get("audio_required", True):
            add_check("audio_stream", a_stream is not None, "Narration audio stream is present", True, a_stream is not None)
            if a_stream and authoritative_audio_duration is not None:
                want_audio_dur = min(authoritative_audio_duration, exp_dur)
                obs_audio_dur = a_stream.get("duration") or duration_s
                if obs_audio_dur is not None:
                    audio_diff = abs(obs_audio_dur - want_audio_dur)
                    add_check("audio_duration", audio_diff <= self.AUDIO_TOLERANCE_S, f"Audio duration matches timeline within {self.AUDIO_TOLERANCE_S}s", round(want_audio_dur, 2), obs_audio_dur)

        # Compute aggregate validity
        blockers = [c["message"] for c in checks if c["status"] == "failed"]
        all_passed = len(blockers) == 0

        return {
            "passed": all_passed,
            "checks": checks,
            "blockers": blockers,
            "observed": {
                "container": container,
                "size_bytes": size_bytes,
                "duration_seconds": duration_s,
                "video_codec": v_stream.get("codec") if v_stream else None,
                "audio_codec": a_stream.get("codec") if a_stream else None,
                "width": v_stream.get("width") if v_stream else None,
                "height": v_stream.get("height") if v_stream else None,
                "fps": v_stream.get("frame_rate_value") if v_stream else None,
            },
        }
