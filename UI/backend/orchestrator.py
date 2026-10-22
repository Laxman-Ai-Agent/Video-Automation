"""Backward-compatibility bridge for backend.orchestrator.

All execution and orchestration logic is canonically unified in
VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator.
This module aliases the canonical implementation via sys.modules
to guarantee single in-memory state, singletons, and lock identities.
"""
from __future__ import annotations

import sys
import VIDEO_ENGINE.pipeline.orchestrator as _canonical

sys.modules[__name__] = _canonical
