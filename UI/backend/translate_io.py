"""Backward-compatibility bridge for backend.translate_io.

Implementation is canonically located in VIDEO_ENGINE.stages.translate_io.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.translate_io as _canonical

sys.modules[__name__] = _canonical
