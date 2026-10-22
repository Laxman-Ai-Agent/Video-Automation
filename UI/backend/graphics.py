"""Backward-compatibility bridge for backend.graphics.

Implementation is canonically located in VIDEO_ENGINE.stages.graphics.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.graphics as _canonical

sys.modules[__name__] = _canonical
