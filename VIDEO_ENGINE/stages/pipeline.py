"""Bridge for legacy pipeline in stages."""
from __future__ import annotations

import sys
try:
    import VIDEO_ENGINE.pipeline.legacy_pipeline_adapter as _canonical
    from VIDEO_ENGINE.pipeline.legacy_pipeline_adapter import *
    sys.modules[__name__] = _canonical
except ImportError:
    pass
