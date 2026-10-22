"""Backward-compatibility bridge for backend.resource_jobs.

Implementation is canonically located in VIDEO_ENGINE.stages.resource_jobs.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.stages.resource_jobs as _canonical

sys.modules[__name__] = _canonical
