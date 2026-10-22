"""Backward-compatibility bridge for backend.motion_scenes.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_scenes.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_scenes as _canonical

sys.modules[__name__] = _canonical
