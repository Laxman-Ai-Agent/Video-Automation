"""Bridge for shared_memory in stages."""
from __future__ import annotations

import sys
try:
    import SYSTEM.memory.shared_memory as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
