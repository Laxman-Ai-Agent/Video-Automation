"""Backward-compatibility bridge for backend.jobs.

All job execution is canonically unified in
VIDEO_ENGINE.pipeline.jobs_adapter and driven exclusively by PipelineOrchestrator.
This module aliases the canonical implementation via sys.modules.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.pipeline.jobs_adapter as _canonical

sys.modules[__name__] = _canonical
