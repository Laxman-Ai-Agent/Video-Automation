"""Backward-compatibility bridge for backend.motion_validation_preview.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_validation_preview.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_validation_preview as _canonical

sys.modules[__name__] = _canonical
