"""Backward-compatibility bridge for backend.audio_analysis.

Implementation is canonically located in VIDEO_ENGINE.stages.audio_analysis.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.audio_analysis as _canonical

sys.modules[__name__] = _canonical
