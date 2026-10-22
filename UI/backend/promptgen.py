"""Backward-compatibility bridge for backend.promptgen.

Implementation is canonically located in VIDEO_ENGINE.stages.promptgen.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.promptgen as _canonical

sys.modules[__name__] = _canonical
