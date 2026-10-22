"""Backward-compatibility bridge for backend.contracts.

Implementation is canonically located in SYSTEM.core.contracts.
"""
from __future__ import annotations

import sys
import SYSTEM.core.contracts as _canonical

sys.modules[__name__] = _canonical
