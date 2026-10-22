"""Bridge for diagnose in stages.

Implementation is canonically located in SYSTEM.observability.diagnose.
"""
from __future__ import annotations

import sys
try:
    import SYSTEM.observability.diagnose as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    import backend.diagnose as _canonical
    sys.modules[__name__] = _canonical
