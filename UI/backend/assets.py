"""Bridge for assets in UI.backend, canonically located in VIDEO_ENGINE.stages.assets."""
from __future__ import annotations
import sys
import VIDEO_ENGINE.stages.assets as _canonical
sys.modules[__name__] = _canonical
