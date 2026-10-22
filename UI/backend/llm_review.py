"""Canonical alias for SYSTEM.policies.llm_review during Phase 2 migration."""
import sys
import SYSTEM.policies.llm_review as _canonical
sys.modules[__name__] = _canonical
