"""Backward-compatibility bridge for backend.cli.

Implementation is canonically located in SYSTEM.core.cli.
"""
from __future__ import annotations

import sys
import SYSTEM.core.cli as _canonical

sys.modules[__name__] = _canonical

if __name__ == "__main__":
    sys.exit(_canonical.main())
