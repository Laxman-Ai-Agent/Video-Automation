"""Bridge for llm_gateway in stages."""
from __future__ import annotations

import sys
try:
    import SYSTEM.core.llm_gateway as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
