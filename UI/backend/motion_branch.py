"""Backward-compatibility bridge for backend.motion_branch.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_branch.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_branch as _canonical

sys.modules[__name__] = _canonical
