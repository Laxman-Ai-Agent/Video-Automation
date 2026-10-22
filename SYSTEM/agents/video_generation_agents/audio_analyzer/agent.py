"""Dedicated implementation module for Audio Analyzer Agent.
Agent ID: audio_analyzer
Stage ID: analyzer
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.memory import store


class AudioAnalyzerAgent(BaseAgent):
    """A03: Audio Analyzer Agent (Frozen Implementation Wrapper). Wraps existing faster-whisper transcribe and audio analysis without ASR re-runs."""

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        audio = next(iter(project_dir.glob("audio.*")), None)
        if not audio:
            return ["No audio file found in project directory"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        tf = project_dir / "transcript.json"
        cf = project_dir / "cuts.json"
        af = project_dir / "audio_analysis.json"

        if not tf.exists():
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="analyzer",
                project_id=project_dir.name,
                status="blocked",
                summary="Missing canonical transcript.json. Silent ASR regeneration is prohibited.",
            )

        from SYSTEM.core.artifact_contracts import _file_sha256, validate_analyzer_artifacts
        try:
            validate_analyzer_artifacts(project_dir)
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="analyzer",
                project_id=project_dir.name,
                status="failed",
                summary=f"Audio analysis artifact validation failed: {e}",
            )

        outputs = [
            ArtifactRef(path=str(tf), description="Transcript JSON"),
        ]
        if cf.exists():
            outputs.append(ArtifactRef(path=str(cf), description="Audio Cuts JSON"))
        if af.exists():
            outputs.append(ArtifactRef(path=str(af), description="Audio Analysis Summary JSON"))

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="analyzer",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary="Audio analysis and transcript verified without ASR re-run",
            metadata={"transcript_sha256": _file_sha256(tf)},
        )


# Backward-compatibility alias
AudioAnalyzerAdapter = AudioAnalyzerAgent
