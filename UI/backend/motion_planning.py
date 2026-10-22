"""Backward-compatibility bridge for backend.motion_planning.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_planning.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_planning as _canonical

sys.modules[__name__] = _canonical
