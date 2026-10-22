"""Backward-compatibility bridge for backend.plan_preview.

Implementation is canonically located in VIDEO_ENGINE.stages.plan_preview.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.plan_preview as _canonical

sys.modules[__name__] = _canonical
