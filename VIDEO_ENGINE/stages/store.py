"""Bridge for store in stages."""
from __future__ import annotations

import sys
try:
    import SYSTEM.memory.store as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
