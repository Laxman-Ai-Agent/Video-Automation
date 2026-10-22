"""Bridge for audio_utils in UI.backend, canonically located in VIDEO_ENGINE.stages.audio_utils."""
from __future__ import annotations
import sys
import VIDEO_ENGINE.stages.audio_utils as _canonical
sys.modules[__name__] = _canonical
duration = _canonical.duration
