# SYSTEM AGENTS ARCHITECTURE AUDIT — DELIVERABLE 7
## LEGACY COMPATIBILITY AND RISK REGISTER

**Repository Root:** `E:\audio-to-video`  
**Audit Timestamp:** 2026-10-17T05:40:00+05:30  
**Phase:** 0 — Current Architecture Audit (Strict Read-Only)  
**Status:** COMPLETE  

---

## 1. Executive Summary

This register catalogs all legacy paths, compatibility bridges, structural risks, and dependencies identified during the Phase 0 audit of the Laxman-Autonomous Master System. Its purpose is to guarantee that the restructuring of the six System Agents in subsequent implementation phases causes zero regressions, zero test breakage, and zero unintended downtime.

The primary finding is that the repository contains two critical structural transition areas:
1. **The `backend/` Compatibility Layer:** An intentional module-forwarding bridge preserving compatibility with legacy test suites and older entry points.
2. **The `SYSTEM/agents/system_agents/` Nesting:** A temporary grouping holding `capability_finder` and `skill_factory` that must be promoted to first-class sibling directories under `SYSTEM/agents/` while maintaining backward-compatible facades for existing callers.

---

## 2. Legacy Path Analysis

### 2.1 The `backend/` Compatibility Shim Directory

- **Location:** `E:\audio-to-video\backend\`
- **Role:** Backward-compatibility bridge established during Phase 2 repository consolidation.
- **Mechanism:** Files in `backend/` are lightweight shims that dynamically reassign `sys.modules[__name__]` to their canonical counterparts in `SYSTEM` and `VIDEO_ENGINE`.
  ```python
  # Example from backend/transcribe.py
  import VIDEO_ENGINE.stages.transcribe as _canonical
  sys.modules[__name__] = _canonical
  ```
- **Active Callers:** Over 30 test files in `tests/` continue to import via `backend.*` (e.g., `tests/test_motion_codegen.py`, `tests/test_scene_segmentation.py`, `tests/test_visual_planning.py`, `tests/test_timeline_render_qc_delivery.py`).
- **Audit Verdict:** `backend/` **MUST NOT BE DELETED** or prematurely stripped during the System Agents implementation. Doing so would immediately break dozens of passing integration tests. Removal of `backend/` belongs strictly in a future dedicated legacy deprecation phase after all test imports are migrated to canonical packages.

### 2.2 The `SYSTEM/agents/system_agents/` Directory

- **Current Location:** `E:\audio-to-video\SYSTEM\agents\system_agents\`
- **Contained Components:**
  - `system_agents/capability_finder/` (contains `agent.py`, `tests/test_agent.py`)
  - `system_agents/skill_factory/` (contains `agent.py`, `tests/test_agent.py`)
- **Target Location (per Approved Architecture):**
  - `SYSTEM/agents/capability_finder/`
  - `SYSTEM/agents/skill_factory/`
- **Active Callers Identified:**
  1. `SYSTEM/registries/agent_registry.py` (lines 24–25):
     ```python
     from SYSTEM.agents.system_agents.capability_finder.agent import CapabilityFinderAgent
     from SYSTEM.agents.system_agents.skill_factory.agent import SkillFactoryAgent
     ```
  2. `SYSTEM/registries/agent_registry.py` (method `list_system_agents()` at line 348)
  3. `tests/test_agent_architecture_reorg.py` (lines 31–32 and lines 173–177):
     ```python
     from SYSTEM.agents.system_agents.capability_finder.agent import CapabilityFinderAgent
     from SYSTEM.agents.system_agents.skill_factory.agent import SkillFactoryAgent
     ...
     system_agents = reg.list_system_agents()
     assert len(system_agents) == 3
     ```
  4. Internal agent test files:
     - `SYSTEM/agents/system_agents/capability_finder/tests/test_agent.py`
     - `SYSTEM/agents/system_agents/skill_factory/tests/test_agent.py`

---

## 3. Migration Strategy & Re-export Facades

When migrating `capability_finder` and `skill_factory` from `SYSTEM/agents/system_agents/` to root sibling directories `SYSTEM/agents/` in Phase 1:

### 3.1 Migration Steps
1. **Move Code:** Relocate directory trees to:
   - `SYSTEM/agents/capability_finder/`
   - `SYSTEM/agents/skill_factory/`
2. **Leave Compatibility Shims in `SYSTEM/agents/system_agents/`:**
   To guarantee zero breakage of existing callers and test fixtures, create forwarding facades:
   - `SYSTEM/agents/system_agents/__init__.py`: Re-export the agents and define clear deprecation warnings.
   - `SYSTEM/agents/system_agents/capability_finder/agent.py`:
     ```python
     """Backward-compatibility facade for capability_finder."""
     import sys
     import SYSTEM.agents.capability_finder.agent as _canonical
     sys.modules[__name__] = _canonical
     CapabilityFinderAgent = _canonical.CapabilityFinderAgent
     ```
   - `SYSTEM/agents/system_agents/skill_factory/agent.py`:
     ```python
     """Backward-compatibility facade for skill_factory."""
     import sys
     import SYSTEM.agents.skill_factory.agent as _canonical
     sys.modules[__name__] = _canonical
     SkillFactoryAgent = _canonical.SkillFactoryAgent
     ```
3. **Update Canonical Callers:**
   - Update `SYSTEM/registries/agent_registry.py` imports to direct sibling paths:
     ```python
     from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent
     from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent
     ```
4. **Update Test Suites:**
   - Update `tests/test_agent_architecture_reorg.py` while ensuring assertions pass under both direct and shinned paths.

---

## 4. Comprehensive Risk Matrix

| Risk ID | Category | Description | Impact | Likelihood | Severity | Mitigation Strategy | Verification Gate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R-01** | Breaking Changes | Moving `system_agents/` breaks `AgentRegistry` and existing tests | High | High | **CRITICAL** | Implement re-export facades in `SYSTEM/agents/system_agents/` using the exact `sys.modules` bridging pattern proven in `backend/`. | Run `pytest tests/test_agent_architecture_reorg.py` and verify all tests pass without import errors. |
| **R-02** | Legacy Deletion | Premature deletion or modification of `backend/` folder | Critical | Low | **HIGH** | Explicit freeze on `backend/`. Prohibit deletions in `backend/` across all System Agents implementation phases. | Automated assertion check in pre-commit/verification agent ensuring `backend/` presence and file count. |
| **R-03** | Frozen Files | Modification of frozen video generation algorithm files | Critical | Low | **HIGH** | Strict SHA-256 integrity verification before and after any changes. Never import or alter frozen stage code. | SHA-256 hash checks against baseline hashes recorded in `TEST_AND_FROZEN_FILE_BASELINE.md`. |
| **R-04** | Capability Routing | Capability Finder failure leads MAA to bypass skill discovery | High | Med | **HIGH** | Provide deterministic fallback in MAA delegation: if capability query fails, fall back to direct agent registry lookup. | Integration tests simulating capability finder unavailability and verifying graceful fallback. |
| **R-05** | Skill Security | Dynamic skill generation in Skill Factory escapes sandbox or executes unsafe code | Critical | Med | **HIGH** | Enforce quarantine staging (`quarantine/`), AST safety scanner, ban `eval`, `exec`, `os.system`, require automated test execution before promotion. | Security Policy Agent audit gate must approve promotion from quarantine to canonical `SYSTEM/skills/`. |
| **R-06** | Circular Dependency | System agents importing MAA while MAA imports System agents | High | Med | **MEDIUM** | Strict interface segregation via `SYSTEM/agents/shared/contracts.py`. System agents communicate solely via `AgentRequest` and `AgentResult`. | Static cycle detection in Architecture Validator during Phase 5. |
| **R-07** | Registry Drift | Disconnect between `AgentRegistry`, `SkillRegistry`, and new `CapabilityRegistry` | Med | Med | **MEDIUM** | Establish `CapabilityRegistry` as an aggregation layer over `AgentRegistry` and `SkillRegistry` with synchronized registration hooks. | Unit tests verifying that registering an agent/skill automatically indexes its capabilities. |
| **R-08** | Legacy Test Failures | 8 legacy test collection failures due to optional dependencies (`scipy`, `openai`) | Low | High | **LOW** | Document failures in Phase 0 baseline. Do not attempt to fix unrelated missing third-party packages during System Agents tasks. | Compare test results strictly against the 239 passed test baseline. |
| **R-09** | State Growth | Unbounded SQLite audit logging and reflection history consuming disk space | Med | Low | **LOW** | Implement automatic rolling retention (e.g., max 10,000 entries) and cache eviction policies in self-learning managers. | Verify database pruning routines under synthetic load benchmarks. |

---

## 5. Architectural Guardrails for Future Implementation Phases

1. **Read-Only Invariant for Video Engine:**
   - The video engine core (`VIDEO_ENGINE/stages/`, `VIDEO_ENGINE/pipeline/orchestrator.py`) is completely frozen and decoupled from System Agents. System Agents operate at the meta/coordination layer only.
2. **Unified BaseAgent Contract:**
   - All newly implemented System Agents (`architecture_validator`, `verification_test_agent`, `security_policy_agent`) must subclass `BaseAgent` from `SYSTEM.agents.shared.base_agent` and conform to `SYSTEM.agents.shared.contracts`.
3. **Quarantine Before Canonical:**
   - No skill generated by `skill_factory` may be written directly to `SYSTEM/skills/`. It must be written to `quarantine/`, tested, audited, and promoted only upon verified clearance.
4. **Non-Destructive Refactoring:**
   - Old import paths must never break abruptly. Forwarding facades must accompany any path relocation.
