"""Backward-compatibility bridge for backend.resume.

Resume analysis is canonically located in
VIDEO_ENGINE.pipeline.resume.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.pipeline.resume as _canonical

sys.modules[__name__] = _canonical
