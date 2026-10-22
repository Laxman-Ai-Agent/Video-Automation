"""VIDEO_ENGINE FFmpeg Package.

Contains FFprobe and FFmpeg media probing, inspection, and processing utilities.
"""
from __future__ import annotations

from .media_probe import (
    ProbeError,
    probe,
    rate,
    sha256_file,
    tool_version,
)
