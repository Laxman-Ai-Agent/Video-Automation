"""Bridge for errors in stages.

Implementation is canonically located in SYSTEM.core.errors.
"""
from __future__ import annotations

import sys
try:
    import SYSTEM.core.errors as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    import backend.errors as _canonical
    sys.modules[__name__] = _canonical
