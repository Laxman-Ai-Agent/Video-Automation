"""Backward-compatibility bridge for backend.fingerprint.

Implementation is canonically located in VIDEO_ENGINE.stages.fingerprint.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.fingerprint as _canonical

sys.modules[__name__] = _canonical
