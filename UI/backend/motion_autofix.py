"""Backward-compatibility bridge for backend.motion_autofix.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_autofix.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_autofix as _canonical

sys.modules[__name__] = _canonical
