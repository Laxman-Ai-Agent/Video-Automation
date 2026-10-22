"""Bridge for media_probe in stages (canonically in VIDEO_ENGINE.ffmpeg.media_probe)."""
from __future__ import annotations

import sys
try:
    import VIDEO_ENGINE.ffmpeg.media_probe as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    import backend.media_probe as _canonical
    sys.modules[__name__] = _canonical
