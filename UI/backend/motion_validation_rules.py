"""Backward-compatibility bridge for backend.motion_validation_rules.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_validation_rules.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_validation_rules as _canonical

sys.modules[__name__] = _canonical
