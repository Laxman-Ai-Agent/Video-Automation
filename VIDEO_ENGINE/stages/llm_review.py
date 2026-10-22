"""Bridge for llm_review in stages."""
from __future__ import annotations

import sys
try:
    import SYSTEM.policies.llm_review as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
