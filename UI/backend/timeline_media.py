"""Backward-compatibility bridge for backend.timeline_media.

Implementation is canonically located in VIDEO_ENGINE.stages.timeline_media.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.timeline_media as _canonical

sys.modules[__name__] = _canonical
