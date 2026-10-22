"""Backward-compatibility bridge for backend.final_qc.

Implementation is canonically located in VIDEO_ENGINE.stages.final_qc.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.final_qc as _canonical

sys.modules[__name__] = _canonical
