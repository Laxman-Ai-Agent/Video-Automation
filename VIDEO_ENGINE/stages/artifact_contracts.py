"""Bridge for artifact_contracts in stages."""
from __future__ import annotations

import sys
try:
    import SYSTEM.core.artifact_contracts as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
