"""Bridge for config in stages.

Implementation is canonically located in SYSTEM.core.config.
"""
from __future__ import annotations

import sys
import SYSTEM.core.config as _canonical

sys.modules[__name__] = _canonical
