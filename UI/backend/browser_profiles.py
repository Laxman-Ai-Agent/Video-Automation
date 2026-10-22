"""Backward-compatibility bridge for backend.browser_profiles.

Chrome temporary profile cleanup is canonically located in
VIDEO_ENGINE.pipeline.browser_profiles.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.pipeline.browser_profiles as _canonical

sys.modules[__name__] = _canonical
