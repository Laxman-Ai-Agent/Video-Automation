"""Bridge for transcribe in UI.backend, canonically located in VIDEO_ENGINE.stages.transcribe."""
from __future__ import annotations
import sys
import VIDEO_ENGINE.stages.transcribe as _canonical
sys.modules[__name__] = _canonical
