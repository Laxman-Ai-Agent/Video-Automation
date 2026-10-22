"""Backward-compatibility bridge for backend.cues.

Implementation is canonically located in VIDEO_ENGINE.stages.cues.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.cues as _canonical

sys.modules[__name__] = _canonical
