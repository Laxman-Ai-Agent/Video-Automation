"""Backward-compatibility bridge for backend.plan_input.

Implementation is canonically located in VIDEO_ENGINE.stages.plan_input.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.plan_input as _canonical

sys.modules[__name__] = _canonical
