"""Backward-compatibility bridge for backend.review.

Implementation is canonically located in VIDEO_ENGINE.stages.review.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.review as _canonical

sys.modules[__name__] = _canonical
