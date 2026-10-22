"""Backward-compatibility bridge for backend.resource_library.

Implementation is canonically located in VIDEO_ENGINE.stages.resource_library.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.resource_library as _canonical

sys.modules[__name__] = _canonical
