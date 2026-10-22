"""Backward-compatibility bridge for backend.timeline_gate.

Implementation is canonically located in VIDEO_ENGINE.stages.timeline_gate.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.timeline_gate as _canonical

sys.modules[__name__] = _canonical
