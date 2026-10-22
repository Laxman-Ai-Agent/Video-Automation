"""Backward-compatibility bridge for backend.motion_animation.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_animation.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_animation as _canonical

sys.modules[__name__] = _canonical
