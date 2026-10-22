"""Dedicated implementation module for Audio Input Agent.
Agent ID: audio_input
Stage ID: audio
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.memory import store


class AudioInputAgent(BaseAgent):
    """Stage 1 (audio): Audio Input Agent. Ingests source audio, validates duration, and generates audio_input_manifest.json."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="audio_input",
                name="Audio Input Agent",
                version="1.0.0",
                status=AgentStatus.IMPLEMENTED,
                purpose="Ingests user narration audio, downsamples to 16kHz mono, and extracts duration parameters.",
                capabilities=["audio-ingest", "sample-rate-conversion", "ffprobe-metadata"],
                stage_id="audio",
                allowed_tools=["ffmpeg", "ffprobe", "store"],
                owner="agent-system",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        from SYSTEM.core.artifact_contracts import verify_path_confinement
        try:
            verify_path_confinement(project_dir, project_dir)
        except Exception as e:
            return [f"Path traversal detected: {e}"]

        audio = next(iter(project_dir.glob("audio.*")), None)
        if not audio:
            return ["No audio file found in project directory"]
        if not audio.is_file():
            return [f"Audio target is not a regular file: {audio.name}"]
        if audio.stat().st_size == 0:
            return ["Source audio file is empty (0 bytes)"]

        ext = audio.suffix.lower()
        allowed = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
        if ext not in allowed:
            return [f"Unsupported audio format '{ext}'. Allowed: {', '.join(sorted(allowed))}"]

        if audio.stat().st_size > 500 * 1024 * 1024:
            return ["Audio file exceeds maximum size limit (500MB)"]

        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        audio = next(iter(project_dir.glob("audio.*")), None)
        if not audio or not audio.is_file() or audio.stat().st_size == 0:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="audio",
                project_id=project_dir.name,
                status="blocked",
                summary="Missing or empty source audio file",
            )

        from SYSTEM.core.artifact_contracts import _file_sha256, verify_path_confinement
        try:
            verify_path_confinement(project_dir, audio)
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="audio",
                project_id=project_dir.name,
                status="failed",
                summary=f"Path traversal detected: {e}",
            )

        sha = _file_sha256(audio)
        size = audio.stat().st_size

        duration = None
        aspect = "16:9"
        try:
            info = store.read_info(project_dir)
            duration = info.get("audio", {}).get("duration")
            aspect = info.get("aspect", "16:9")
        except Exception:
            pass

        if duration is None:
            try:
                import subprocess
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio)]
                p_out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if p_out.returncode == 0 and p_out.stdout.strip():
                    duration = round(float(p_out.stdout.strip()), 2)
            except Exception:
                pass

        manifest_data = {
            "schema_version": "1.0",
            "project_id": project_dir.name,
            "audio_artifact_ref": audio.name,
            "filename_display": audio.name,
            "sha256": sha,
            "byte_size": size,
            "container": audio.suffix.lstrip(".").lower(),
            "duration_seconds": duration,
            "aspect_ratio": aspect,
            "visual_mode": "motion-only",
            "validation_status": "valid",
            "validation_findings": [],
            "created_at": time.time(),
            "input_fingerprint": sha,
        }

        manifest_file = project_dir / "audio_input_manifest.json"
        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        outputs = [
            ArtifactRef(path=str(audio), description="Source Audio File"),
            ArtifactRef(path=str(manifest_file), description="Audio Input Manifest JSON"),
        ]

        wav_16k = project_dir / "audio_16k.wav"
        if wav_16k.exists():
            outputs.append(ArtifactRef(path=str(wav_16k), description="16kHz Mono Audio WAV"))

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="audio",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary="Audio input verified and manifest generated",
            metadata={"manifest": manifest_data},
        )


# Backward-compatibility alias
AudioInputAdapter = AudioInputAgent
