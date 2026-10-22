"""Backward-compatibility bridge for backend.prompt_review.

Implementation is canonically located in VIDEO_ENGINE.stages.prompt_review.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.prompt_review as _canonical

sys.modules[__name__] = _canonical
