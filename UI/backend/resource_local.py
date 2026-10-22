"""Backward-compatibility bridge for backend.resource_local.

Implementation is canonically located in VIDEO_ENGINE.stages.resource_local.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.resource_local as _canonical

sys.modules[__name__] = _canonical
