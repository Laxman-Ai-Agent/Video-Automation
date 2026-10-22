"""Backward-compatibility bridge for backend.visual_plan.

Implementation is canonically located in VIDEO_ENGINE.stages.visual_plan.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.visual_plan as _canonical

sys.modules[__name__] = _canonical
