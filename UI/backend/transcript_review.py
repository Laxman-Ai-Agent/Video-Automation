"""Backward-compatibility bridge for backend.transcript_review.

Implementation is canonically located in VIDEO_ENGINE.stages.transcript_review.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.transcript_review as _canonical

sys.modules[__name__] = _canonical
