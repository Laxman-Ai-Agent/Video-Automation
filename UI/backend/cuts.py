"""Backward-compatibility bridge for backend.cuts.

Implementation is canonically located in VIDEO_ENGINE.stages.cuts.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.cuts as _canonical

sys.modules[__name__] = _canonical
