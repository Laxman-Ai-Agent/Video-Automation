"""Bridge for pipeline_state in stages."""
from __future__ import annotations

import sys
try:
    import SYSTEM.core.pipeline_state as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
