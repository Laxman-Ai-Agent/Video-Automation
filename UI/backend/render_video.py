"""Backward-compatibility bridge for backend.render_video.

Implementation is canonically located in VIDEO_ENGINE.stages.render_video.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.render_video as _canonical

sys.modules[__name__] = _canonical
