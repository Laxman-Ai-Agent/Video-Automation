"""Bridge for jobs in stages."""
from __future__ import annotations

import sys
try:
    import VIDEO_ENGINE.pipeline.jobs_adapter as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
