"""Backward-compatibility bridge for backend.autoplan.

Implementation is canonically located in VIDEO_ENGINE.stages.autoplan.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.autoplan as _canonical

sys.modules[__name__] = _canonical
