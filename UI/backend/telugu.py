"""Backward-compatibility bridge for backend.telugu.

Implementation is canonically located in VIDEO_ENGINE.stages.telugu.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.telugu as _canonical

sys.modules[__name__] = _canonical
