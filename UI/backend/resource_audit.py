"""Backward-compatibility bridge for backend.resource_audit.

Implementation is canonically located in VIDEO_ENGINE.stages.resource_audit.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.resource_audit as _canonical

sys.modules[__name__] = _canonical
