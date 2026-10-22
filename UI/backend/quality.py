"""Backward-compatibility bridge for backend.quality.

Implementation is canonically located in VIDEO_ENGINE.stages.quality.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.quality as _canonical

sys.modules[__name__] = _canonical
