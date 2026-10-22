"""Canonical Agent Runtime, Registry, and Communication module for Dark World Video Generation Agent."""
import importlib
import importlib.abc
import importlib.util
import sys
import types

from SYSTEM.agents.shared import base_agent, communication, contracts
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.communication import (
    append_message,
    get_communications_dir,
    get_communications_file,
    publish_handoff,
    publish_lifecycle_event,
    publish_message,
    publish_review_feedback,
    query_messages,
    subscribe_events,
)
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMessage,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
    ArtifactRef,
    MessageType,
)


# Virtual backward-compatibility package for legacy SYSTEM.agents.system_agents imports
def _setup_system_agents_facade():
    pkg = types.ModuleType("SYSTEM.agents.system_agents")
    pkg.__path__ = []
    pkg.__doc__ = "Virtual backward-compatibility package redirecting to canonical SYSTEM.agents."
    sys.modules["SYSTEM.agents.system_agents"] = pkg

    subagents = {
        "capability_finder": "CapabilityFinderAgent",
        "skill_factory": "SkillFactoryAgent",
        "architecture_validator": "ArchitectureValidatorAgent",
        "verification_and_test": "VerificationAndTestAgent",
        "security_policy": "SecurityPolicyAgent",
        "autonomous_execution": "AutonomousExecutionAgent",
    }

    for name, cls_name in subagents.items():
        try:
            canon_pkg = importlib.import_module(f"SYSTEM.agents.{name}")
            canon_mod = importlib.import_module(f"SYSTEM.agents.{name}.agent")
            agent_cls = getattr(canon_mod, cls_name, None)

            sys.modules[f"SYSTEM.agents.system_agents.{name}"] = canon_pkg
            sys.modules[f"SYSTEM.agents.system_agents.{name}.agent"] = canon_mod
            setattr(pkg, name, canon_pkg)
            if agent_cls:
                setattr(pkg, cls_name, agent_cls)
        except Exception:
            pass

    class _SystemAgentsFinder(importlib.abc.MetaPathFinder):
        PREFIX = "SYSTEM.agents.system_agents."

        def find_spec(self, fullname, path, target=None):
            if fullname.startswith(self.PREFIX):
                canonical = "SYSTEM.agents." + fullname[len(self.PREFIX) :]
                try:
                    return importlib.util.find_spec(canonical)
                except Exception:
                    return None
            return None

    if not any(isinstance(f, _SystemAgentsFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _SystemAgentsFinder())

    return pkg


system_agents = _setup_system_agents_facade()


def __getattr__(name: str):
    if name in ("AgentRegistry", "registry", "get_agent_registry"):
        from SYSTEM.registries import agent_registry
        return getattr(agent_registry, name)
    if name == "system_agents":
        return sys.modules.get("SYSTEM.agents.system_agents")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AgentCategory",
    "AgentMessage",
    "AgentMetadata",
    "AgentRegistry",
    "AgentRequest",
    "AgentResult",
    "AgentStatus",
    "ArtifactRef",
    "BaseAgent",
    "MessageType",
    "append_message",
    "get_communications_dir",
    "get_communications_file",
    "publish_handoff",
    "publish_lifecycle_event",
    "publish_message",
    "publish_review_feedback",
    "query_messages",
    "subscribe_events",
    "registry",
    "get_agent_registry",
    "system_agents",
]
