"""Backward-compatibility bridge for backend.video_qc.

Implementation is canonically located in VIDEO_ENGINE.stages.video_qc.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.video_qc as _canonical

sys.modules[__name__] = _canonical
