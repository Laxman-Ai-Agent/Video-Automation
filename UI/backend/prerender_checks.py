"""Backward-compatibility bridge for backend.prerender_checks.

Implementation is canonically located in VIDEO_ENGINE.stages.prerender_checks.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.prerender_checks as _canonical

sys.modules[__name__] = _canonical
