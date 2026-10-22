"""Backward-compatibility bridge for backend.resource_verify.

Implementation is canonically located in VIDEO_ENGINE.stages.resource_verify.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.resource_verify as _canonical

sys.modules[__name__] = _canonical
