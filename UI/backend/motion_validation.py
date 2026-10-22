"""Backward-compatibility bridge for backend.motion_validation.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_validation.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_validation as _canonical

sys.modules[__name__] = _canonical
