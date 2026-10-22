"""Bridge for pipeline execution adapter in UI.backend.

Canonically located in VIDEO_ENGINE.pipeline.legacy_pipeline_adapter.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.pipeline.legacy_pipeline_adapter as _canonical

sys.modules[__name__] = _canonical
