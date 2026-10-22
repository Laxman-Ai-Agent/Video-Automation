"""Backward-compatibility bridge for backend.transition_audit.

Implementation is canonically located in VIDEO_ENGINE.stages.transition_audit.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.transition_audit as _canonical

sys.modules[__name__] = _canonical
