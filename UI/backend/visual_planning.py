"""Backward-compatibility bridge for backend.visual_planning.

Implementation is canonically located in VIDEO_ENGINE.stages.visual_planning.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.visual_planning as _canonical

sys.modules[__name__] = _canonical
