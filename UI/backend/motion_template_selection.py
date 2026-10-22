"""Backward-compatibility bridge for backend.motion_template_selection.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_template_selection.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_template_selection as _canonical

sys.modules[__name__] = _canonical
