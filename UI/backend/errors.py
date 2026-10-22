"""Bridge for errors in UI.backend, canonically located in SYSTEM.core.errors."""
from __future__ import annotations

import sys
import SYSTEM.core.errors as _canonical

sys.modules[__name__] = _canonical
