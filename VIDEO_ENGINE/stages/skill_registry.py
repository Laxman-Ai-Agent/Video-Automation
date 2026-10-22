"""Bridge for skill_registry in stages."""
from __future__ import annotations

import sys
try:
    import SYSTEM.registries.skill_registry as _canonical
    sys.modules[__name__] = _canonical
except ImportError:
    pass
