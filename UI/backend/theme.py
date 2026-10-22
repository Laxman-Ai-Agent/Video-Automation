"""Backward-compatibility bridge for backend.theme.

Implementation is canonically located in VIDEO_ENGINE.stages.theme.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.theme as _canonical

sys.modules[__name__] = _canonical
