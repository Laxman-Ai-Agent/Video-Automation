"""Bridge for checks in stages.

Implementation is canonically located in SYSTEM.core.checks.
"""
from __future__ import annotations

import sys
try:
    import SYSTEM.core.checks as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    import backend.checks as _canonical
    sys.modules[__name__] = _canonical
