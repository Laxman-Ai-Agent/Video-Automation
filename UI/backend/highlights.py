"""Backward-compatibility bridge for backend.highlights.

Implementation is canonically located in VIDEO_ENGINE.stages.highlights.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.highlights as _canonical

sys.modules[__name__] = _canonical
