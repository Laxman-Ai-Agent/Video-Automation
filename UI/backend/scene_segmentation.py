"""Backward-compatibility bridge for backend.scene_segmentation.

Implementation is canonically located in VIDEO_ENGINE.stages.scene_segmentation.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.scene_segmentation as _canonical

sys.modules[__name__] = _canonical
