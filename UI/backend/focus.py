"""Backward-compatibility bridge for backend.focus.

Implementation is canonically located in VIDEO_ENGINE.stages.focus.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.focus as _canonical

sys.modules[__name__] = _canonical
