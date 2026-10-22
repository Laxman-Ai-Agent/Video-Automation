"""Bridge for matcher in UI.backend, canonically located in VIDEO_ENGINE.stages.matcher."""
from __future__ import annotations
import sys
import VIDEO_ENGINE.stages.matcher as _canonical
sys.modules[__name__] = _canonical
