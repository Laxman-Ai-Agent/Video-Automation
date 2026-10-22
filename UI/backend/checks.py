"""Backward-compatibility bridge for backend.checks.

Implementation is canonically located in SYSTEM.core.checks.
"""
from __future__ import annotations

import sys
import SYSTEM.core.checks as _canonical

sys.modules[__name__] = _canonical
