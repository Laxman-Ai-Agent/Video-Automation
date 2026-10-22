# SYSTEM AGENTS ARCHITECTURE — DELIVERABLE 2
## PATH MIGRATION MAP

**Repository:** `E:\audio-to-video`  
**Execution Timestamp:** 2026-10-17T06:25:00+05:30  
**Phase:** 1 of 10  
**Status:** COMPLETE  

---

## 1. Overview

This document provides a detailed mapping of files, modules, and directories migrated during Phase 1. It details the transition from the pre-Phase 1 layout under `SYSTEM/agents/system_agents/` to the canonical top-level sibling architecture under `SYSTEM/agents/`, alongside the preservation of backward-compatibility facades.

---

## 2. Master Path Migration Matrix

| Component | Pre-Phase 1 Path | Canonical Target Path (Phase 1) | Compatibility Facade Path | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Capability Finder Package** | `SYSTEM/agents/system_agents/capability_finder/` | `SYSTEM/agents/capability_finder/` | `SYSTEM/agents/system_agents/capability_finder/` | **MIGRATED & BRIDGED** |
| Capability Finder Core | `SYSTEM/agents/system_agents/capability_finder/agent.py` | `SYSTEM/agents/capability_finder/agent.py` | `SYSTEM/agents/system_agents/capability_finder/agent.py` | **MIGRATED & BRIDGED** |
| Capability Finder Config | `SYSTEM/agents/system_agents/capability_finder/config/agent_config.json` | `SYSTEM/agents/capability_finder/config/agent_config.json` | *Retained for legacy tests* | **MIGRATED** |
| Capability Finder Memory | `SYSTEM/agents/system_agents/capability_finder/memory/memory_policy.json` | `SYSTEM/agents/capability_finder/memory/memory_policy.json` | *Retained for legacy tests* | **MIGRATED** |
| Capability Finder Readme | `SYSTEM/agents/system_agents/capability_finder/README.md` | `SYSTEM/agents/capability_finder/README.md` | *Retained for legacy docs* | **MIGRATED** |
| Capability Finder Tests | `SYSTEM/agents/system_agents/capability_finder/tests/test_agent.py` | `SYSTEM/agents/capability_finder/tests/test_agent.py` | `SYSTEM/agents/system_agents/capability_finder/tests/test_agent.py` | **MIGRATED & BRIDGED** |
| **Skill Factory Package** | `SYSTEM/agents/system_agents/skill_factory/` | `SYSTEM/agents/skill_factory/` | `SYSTEM/agents/system_agents/skill_factory/` | **MIGRATED & BRIDGED** |
| Skill Factory Core | `SYSTEM/agents/system_agents/skill_factory/agent.py` | `SYSTEM/agents/skill_factory/agent.py` | `SYSTEM/agents/system_agents/skill_factory/agent.py` | **MIGRATED & BRIDGED** |
| Skill Factory Config | `SYSTEM/agents/system_agents/skill_factory/config/agent_config.json` | `SYSTEM/agents/skill_factory/config/agent_config.json` | *Retained for legacy tests* | **MIGRATED** |
| Skill Factory Memory | `SYSTEM/agents/system_agents/skill_factory/memory/memory_policy.json` | `SYSTEM/agents/skill_factory/memory/memory_policy.json` | *Retained for legacy tests* | **MIGRATED** |
| Skill Factory Readme | `SYSTEM/agents/system_agents/skill_factory/README.md` | `SYSTEM/agents/skill_factory/README.md` | *Retained for legacy docs* | **MIGRATED** |
| Skill Factory Tests | `SYSTEM/agents/system_agents/skill_factory/tests/test_agent.py` | `SYSTEM/agents/skill_factory/tests/test_agent.py` | `SYSTEM/agents/system_agents/skill_factory/tests/test_agent.py` | **MIGRATED & BRIDGED** |
| **System Agents Root** | `SYSTEM/agents/system_agents/__init__.py` | *N/A (Group folder)* | `SYSTEM/agents/system_agents/__init__.py` | **FACADE DEPLOYED** |
| **Agent Registry** | `SYSTEM/registries/agent_registry.py` | `SYSTEM/registries/agent_registry.py` | *N/A (Updated to canonical)* | **UPDATED** |

---

## 3. Structural File Inventory

```text
E:\audio-to-video\SYSTEM\agents\
│
├── capability_finder\                 <-- CANONICAL IMPLEMENTATION
│   ├── __init__.py                    (Exports: CapabilityFinderAgent)
│   ├── agent.py                       (Authoritative CapabilityFinderAgent class)
│   ├── README.md                      (Canonical agent spec)
│   ├── config\
│   │   └── agent_config.json          (Timeout: 60s, allowed_tools: registries)
│   ├── memory\
│   │   └── memory_policy.json         (Scope: agent, isolation: strict)
│   └── tests\
│       ├── __init__.py                (Pytest package namespace isolation)
│       └── test_agent.py              (Canonical unit tests)
│
├── skill_factory\                     <-- CANONICAL IMPLEMENTATION
│   ├── __init__.py                    (Exports: SkillFactoryAgent)
│   ├── agent.py                       (Authoritative SkillFactoryAgent class)
│   ├── README.md                      (Canonical agent spec)
│   ├── config\
│   │   └── agent_config.json          (Timeout: 120s, allowed_tools: audit/staging)
│   ├── memory\
│   │   └── memory_policy.json         (Scope: agent, isolation: strict)
│   └── tests\
│       ├── __init__.py                (Pytest package namespace isolation)
│       └── test_agent.py              (Canonical unit tests)
│
├── main_architecture_agent\           <-- MASTER COORDINATOR (UNTOUCHED)
│   ├── agent.py
│   ├── evaluations\
│   ├── learning\
│   └── planning\
│
└── system_agents\                     <-- COMPATIBILITY BRIDGES ONLY
    ├── __init__.py                    (Re-exports: CapabilityFinderAgent, SkillFactoryAgent)
    ├── capability_finder\
    │   ├── __init__.py                (Re-exports: CapabilityFinderAgent, agent)
    │   ├── agent.py                   (Re-exports: from SYSTEM.agents.capability_finder.agent)
    │   └── tests\
    │       ├── __init__.py            (Namespace isolation)
    │       └── test_agent.py          (Legacy assertion: LegacyAgent is CanonicalAgent)
    └── skill_factory\
        ├── __init__.py                (Re-exports: SkillFactoryAgent, agent)
        ├── agent.py                   (Re-exports: from SYSTEM.agents.skill_factory.agent)
        └── tests\
            ├── __init__.py            (Namespace isolation)
            └── test_agent.py          (Legacy assertion: LegacyAgent is CanonicalAgent)
```

---

## 4. Package Ownership & Import Rules

1. **One Authoritative Implementation:**
   The files under `SYSTEM/agents/capability_finder/` and `SYSTEM/agents/skill_factory/` are the sole sources of truth. Future enhancements (e.g., Phase 2 AST code discovery, Phase 3 self-learning, Phase 4 promotion engine) must be implemented strictly in these canonical locations.
2. **Facade Immutability:**
   Files under `SYSTEM/agents/system_agents/` are strictly thin re-export stubs. They must contain zero business logic.
3. **No Direct Sibling Inter-Dependencies:**
   Neither `capability_finder` nor `skill_factory` may directly import each other. All inter-agent communication must flow through `SYSTEM.agents.shared.contracts` and the `AgentRegistry`/`MainArchitectureAgent`.
