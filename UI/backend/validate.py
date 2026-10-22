"""Backward-compatibility bridge for backend.validate.

Implementation is canonically located in VIDEO_ENGINE.stages.validate.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.validate as _canonical

sys.modules[__name__] = _canonical
