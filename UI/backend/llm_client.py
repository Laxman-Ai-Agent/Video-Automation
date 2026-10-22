"""Backward-compatibility bridge for backend.llm_client.

Implementation is canonically located in SYSTEM.core.llm_client.
"""
from __future__ import annotations

import sys
import SYSTEM.core.llm_client as _canonical

sys.modules[__name__] = _canonical
