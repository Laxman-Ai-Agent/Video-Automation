"""Authoritative Central Tool Registry for SYSTEM agents and execution components."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal

ToolPermissionLevel = Literal["read_only", "safe_write", "privileged", "admin"]


@dataclass
class ToolDefinition:
    """Metadata describing an executable tool or service available to agents."""
    tool_id: str
    name: str
    category: str  # e.g., 'media', 'ai', 'storage', 'system', 'governance'
    description: str
    capabilities: list[str] = field(default_factory=list)
    permission_level: ToolPermissionLevel = "read_only"
    allowed_agent_categories: list[str] = field(default_factory=lambda: ["*"])
    version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolRegistry:
    """Thread-safe registry of system tools, CLI wrappers, and execution utilities."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        defaults = [
            ToolDefinition(
                tool_id="ffmpeg",
                name="FFmpeg Media Processor",
                category="media",
                description="Audio downsampling, silence detection, normalization, and video muxing.",
                capabilities=["audio_normalize", "silence_detect", "mux_mp4"],
                permission_level="safe_write",
            ),
            ToolDefinition(
                tool_id="ffprobe",
                name="FFprobe Media Inspector",
                category="media",
                description="Extracts stream duration, sample rate, codec, and channels.",
                capabilities=["duration_probe", "audio_codec_probe", "fps_probe"],
                permission_level="read_only",
            ),
            ToolDefinition(
                tool_id="faster_whisper",
                name="Faster Whisper ASR Engine",
                category="ai",
                description="Local neural network speech-to-text inference with word-level timestamps.",
                capabilities=["speech_to_text", "word_timestamps", "telugu_transcription"],
                permission_level="read_only",
            ),
            ToolDefinition(
                tool_id="llm_gateway",
                name="Central LLM Gateway",
                category="ai",
                description="Unified multi-provider LLM interface with fallback and token tracking.",
                capabilities=["chat_completion", "json_structured_output", "stage_review"],
                permission_level="safe_write",
            ),
            ToolDefinition(
                tool_id="file_storage",
                name="Project Store Utilities",
                category="storage",
                description="Project directory confinement, artifact reads, writes, and JSON manifests.",
                capabilities=["confined_read", "confined_write", "atomic_json_save"],
                permission_level="safe_write",
            ),
            ToolDefinition(
                tool_id="skill_registry",
                name="Central Skill Catalog",
                category="governance",
                description="Discovers, audits, and loads approved agent skills.",
                capabilities=["skill_search", "skill_verification", "checksum_audit"],
                permission_level="read_only",
            ),
            ToolDefinition(
                tool_id="memory_service",
                name="Central Scoped Memory",
                category="system",
                description="Isolated agent private memory and project-scoped knowledge stores.",
                capabilities=["private_read", "private_write", "project_share"],
                permission_level="safe_write",
            ),
            ToolDefinition(
                tool_id="laxman_approvals",
                name="Laxman Approval Gatekeeper",
                category="governance",
                description="Human-in-the-loop approval requests.",
                capabilities=["submit_request", "check_status", "pin_verify"],
                permission_level="privileged",
            ),
            ToolDefinition(
                tool_id="evaluation_engine",
                name="Regression & Self-Learning Evaluator",
                category="governance",
                description="Evaluates benchmark test suites and candidate proposals against baselines.",
                capabilities=["run_suite", "diff_baseline", "propose_candidate"],
                permission_level="safe_write",
            ),
        ]
        for t in defaults:
            self._tools[t.tool_id] = t

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> ToolDefinition | None:
        return self._tools.get(tool_id)

    def list_tools(self, category: str | None = None) -> list[ToolDefinition]:
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def discover_for_agent(self, agent_id: str, allowed_tool_ids: list[str] | None = None) -> list[ToolDefinition]:
        """Discovers tools available to a specific agent based on permissions and allowed list."""
        if not allowed_tool_ids:
            return list(self._tools.values())
        return [t for t_id, t in self._tools.items() if t_id in allowed_tool_ids]


tool_registry = ToolRegistry()
