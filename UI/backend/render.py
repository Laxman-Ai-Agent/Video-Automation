"""Backward-compatibility bridge for backend.render.

Implementation is canonically located in VIDEO_ENGINE.stages.render.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.render as _canonical

sys.modules[__name__] = _canonical
