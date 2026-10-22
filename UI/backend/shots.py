"""Backward-compatibility bridge for backend.shots.

Implementation is canonically located in VIDEO_ENGINE.stages.shots.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.shots as _canonical

sys.modules[__name__] = _canonical
