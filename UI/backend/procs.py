"""Backward-compatibility bridge for backend.procs.

Process tracking and termination logic is canonically located in
VIDEO_ENGINE.pipeline.procs.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.pipeline.procs as _canonical

sys.modules[__name__] = _canonical
