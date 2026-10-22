"""Bridge for contracts in stages.

Implementation is canonically located in SYSTEM.core.contracts.
"""
from __future__ import annotations

import sys
try:
    import SYSTEM.core.contracts as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    import backend.contracts as _canonical
    sys.modules[__name__] = _canonical
