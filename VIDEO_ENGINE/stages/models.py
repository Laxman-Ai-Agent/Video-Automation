"""Bridge for models in stages.

Implementation is canonically located in UI.backend.models.
"""
from __future__ import annotations

import sys
try:
    import UI.backend.models as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    import backend.models as _canonical
    sys.modules[__name__] = _canonical
