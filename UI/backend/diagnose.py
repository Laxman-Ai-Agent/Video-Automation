"""Backward-compatibility bridge for backend.diagnose.

Implementation is canonically located in SYSTEM.observability.diagnose.
"""
from __future__ import annotations

import sys
import SYSTEM.observability.diagnose as _canonical

sys.modules[__name__] = _canonical
