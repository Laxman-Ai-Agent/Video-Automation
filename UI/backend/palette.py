"""Backward-compatibility bridge for backend.palette.

Implementation is canonically located in VIDEO_ENGINE.stages.palette.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.palette as _canonical

sys.modules[__name__] = _canonical
