"""Bridge for llm_client in stages.

Implementation is canonically located in SYSTEM.core.llm_client.
"""
from __future__ import annotations

import sys
try:
    import SYSTEM.core.llm_client as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    import backend.llm_client as _canonical
    sys.modules[__name__] = _canonical
