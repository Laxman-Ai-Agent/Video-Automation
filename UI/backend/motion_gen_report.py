"""Backward-compatibility bridge for backend.motion_gen_report.

Implementation is canonically located in VIDEO_ENGINE.stages.motion_gen_report.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.motion_gen_report as _canonical

sys.modules[__name__] = _canonical
