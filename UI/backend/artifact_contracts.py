"""Bridge for artifact_contracts in UI.backend, canonically located in SYSTEM.core.artifact_contracts."""
from __future__ import annotations
import sys
import SYSTEM.core.artifact_contracts as _canonical
sys.modules[__name__] = _canonical
