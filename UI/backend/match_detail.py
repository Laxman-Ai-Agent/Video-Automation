"""Backward-compatibility bridge for backend.match_detail.

Implementation is canonically located in VIDEO_ENGINE.stages.match_detail.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.match_detail as _canonical

sys.modules[__name__] = _canonical
