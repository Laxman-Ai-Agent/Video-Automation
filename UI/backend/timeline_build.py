"""Backward-compatibility bridge for backend.timeline_build.

Implementation is canonically located in VIDEO_ENGINE.stages.timeline_build.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.timeline_build as _canonical

sys.modules[__name__] = _canonical
