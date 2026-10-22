"""Canonical alias for SYSTEM.agents during Phase 2 migration."""
import sys
import SYSTEM.agents as _canonical
import SYSTEM.agents.shared.contracts as _contracts
import SYSTEM.agents.shared.communication as _communication
import SYSTEM.agents.shared.base_agent as _base_agent
import SYSTEM.agents.video_generation_agents.stage_adapters as _stage_adapters
import SYSTEM.registries.agent_registry as _registry

sys.modules["backend.agents.contracts"] = _contracts
sys.modules["backend.agents.communication"] = _communication
sys.modules["backend.agents.base_agent"] = _base_agent
sys.modules["backend.agents.registry"] = _registry
sys.modules["backend.agents.adapters"] = sys.modules.get("backend.agents.adapters", _canonical)
sys.modules["backend.agents.adapters.stage_adapters"] = _stage_adapters

_canonical.contracts = _contracts
_canonical.communication = _communication
_canonical.base_agent = _base_agent
_canonical.registry = _registry.registry

sys.modules[__name__] = _canonical

