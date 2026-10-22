"""Backward-compatibility bridge for backend.media_probe.

Media probing logic is canonically located in VIDEO_ENGINE.ffmpeg.media_probe.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.ffmpeg.media_probe as _canonical

sys.modules[__name__] = _canonical
