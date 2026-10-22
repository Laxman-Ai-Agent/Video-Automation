"""Backward-compatibility bridge for backend.stock.

Implementation is canonically located in VIDEO_ENGINE.stages.stock.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.stock as _canonical

sys.modules[__name__] = _canonical
