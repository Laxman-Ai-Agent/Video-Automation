"""Backward-compatibility bridge for backend.show_transcript.

Implementation is canonically located in VIDEO_ENGINE.stages.show_transcript.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.show_transcript as _canonical

sys.modules[__name__] = _canonical
