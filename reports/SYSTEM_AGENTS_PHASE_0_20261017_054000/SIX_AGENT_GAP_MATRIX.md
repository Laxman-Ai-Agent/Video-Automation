# Six System Agents — Comprehensive Gap Matrix

**Date:** 2026-10-17  
**Repository Root:** `E:\audio-to-video`  
**Report Directory:** `reports/SYSTEM_AGENTS_PHASE_0_20261017_054000/`  

---

## 1. Overview & Classification Criteria

Every capability is evaluated based on actual repository evidence and classified into one of four strict states:
- **Implemented**: Verified working code with executable logic, contracts, tests, and active integration.
- **Partial**: Implementation exists but is incomplete, lacks key workflow steps, or contains stubs.
- **Missing**: No dedicated implementation, class, or functionality exists in the codebase.
- **Unverified**: Code or claims exist but cannot be validated by static read-only inspection.

---

## 2. Section A: Main Architecture Agent

**Current Path:** `SYSTEM/agents/main_architecture_agent/`  
**Target Path:** `SYSTEM/agents/main_architecture_agent/` (Match)  

| Component / Capability | Current Path | Status | Evidence | Dependency / Risk | Recommended Action |
|:---|:---|:---:|:---|:---|:---|
| **Requirement Interpretation & Planning** | `SYSTEM/agents/main_architecture_agent/planning/task_decomposer.py` | **Implemented** | `TaskDecomposer.decompose()` identifies task family, decomposes goal into DAG with dependencies. | Dependent on active strategy rules. Low risk. | Retain and maintain active strategy rules. |
| **Task Decomposition & Prioritization** | `SYSTEM/agents/main_architecture_agent/planning/task_decomposer.py` | **Implemented** | Generates ordered subtasks with step indices, prerequisites, and initial agent assignments. | None. Low risk. | Reuse existing implementation. |
| **Agent Discovery & Selection** | `SYSTEM/agents/main_architecture_agent/planning/agent_router.py` | **Implemented** | `AgentRouter.route_subtask()` queries preferences, fallbacks, registry, and historical failures. | Depends on `AgentRegistry`. | Reuse existing routing engine. |
| **Pre-Flight Plan Evaluation & Cycle Detection** | `SYSTEM/agents/main_architecture_agent/planning/plan_evaluator.py` | **Implemented** | `PlanEvaluator.evaluate_plan()` uses Kahn's topological sort for cycle detection and checks agent existence. | Requires valid DAG. | Reuse existing pre-flight validator. |
| **Individual Agent Delegation** | `SYSTEM/agents/main_architecture_agent/agent.py#L231-L280` | **Implemented** | `_handle_delegate()` retrieves adapter from registry, calls `agent_instance.invoke()`, records duration and status. | Requires target agent in `AgentRegistry`. | Reuse verified delegation logic. |
| **Autonomous Multi-Step Plan Execution** | `SYSTEM/agents/main_architecture_agent/agent.py#L74` | **Partial** | `"execute_plan"` is allowlisted in `validate()`, but `execute()` lacks a dedicated multi-step loop executing subtasks in topological order. | Risk: callers must manually iterate steps via `delegate`. | Implement `_handle_execute_plan()` to iterate topological order automatically. |
| **Result Collection & Decision Logging** | `SYSTEM/agents/main_architecture_agent/agent.py#L201-L263` | **Implemented** | Decisions logged to `SYSTEM.history.history_service.HistoryService` via `DecisionRecord`. | Dependent on `config/history/decisions.jsonl`. | Reuse existing history integration. |
| **Secret Redaction in Task Experiences** | `SYSTEM/agents/main_architecture_agent/learning/experience_collector.py#L20-L37` | **Implemented** | `redact_sensitive_text()` strips API keys (`sk-`, `AIza`), GitHub tokens, Bearer tokens, secrets, PINs. | None. Verified by 15 tests. | Reuse existing redaction engine. |
| **Self-Learning Reflection & Proposals** | `SYSTEM/agents/main_architecture_agent/learning/` | **Implemented** | `ReflectionEngine`, `ImprovementProposalEngine`, `EvaluationRunner`, `StrategyManager`. | Operates strictly on declarative JSON strategies. | Maintain established self-learning architecture. |
| **Laxman Approval Staging for High-Risk Mutations** | `SYSTEM/agents/main_architecture_agent/learning/learning_scheduler.py#L187-L215` | **Implemented** | Automatically calls `submit_candidate_promotion_request()` when proposals are high-risk or alter core decomposition. | Depends on `SYSTEM/approvals/`. | Retain existing governance bridge. |

---

## 3. Section B: Capability Finder

**Current Path:** `SYSTEM/agents/system_agents/capability_finder/`  
**Target Path:** `SYSTEM/agents/capability_finder/` (Sibling directory)  

| Component / Capability | Current Path | Status | Evidence | Dependency / Risk | Recommended Action |
|:---|:---|:---:|:---|:---|:---|
| **Directory Placement** | `SYSTEM/agents/system_agents/capability_finder/` | **Partial** | Nested inside `system_agents/` rather than a direct sibling under `SYSTEM/agents/`. | Risk of import breakages during relocation. | Relocate to `SYSTEM/agents/capability_finder/` and provide backward compatibility aliases in `system_agents/`. |
| **Agent, Skill & Tool Discovery** | `SYSTEM/agents/system_agents/capability_finder/agent.py#L54-L65` | **Implemented** | Queries `AgentRegistry.list_all_agents()`, `skill_registry.search_skills()`, and `tool_registry.list_tools()`. | Working and verified by unit tests. | Retain discovery query logic. |
| **Runtime Prerequisite Verification** | `SYSTEM/agents/system_agents/capability_finder/agent.py#L67-L77` | **Implemented** | Checks `ffmpeg`, `ffprobe` via `shutil.which()`, checks Whisper model presence. | Requires system binaries. | Retain and expand to Node/Remotion prerequisites. |
| **Requirement Parsing** | *(None)* | **Missing** | Only simple case-insensitive string matching (`query in name` or `query in capabilities`). No structured parsing. | Inability to decompose multi-faceted requirement briefs. | Implement structured requirement parser in Phase 2. |
| **Source Code & AST Scanning** | *(None)* | **Missing** | Cannot discover unmapped functions, scripts, or orphan capabilities directly from code files. | Relies solely on pre-registered metadata. | Implement static AST and module scanner in Phase 2. |
| **Capability Matching & Duplicate Detection** | *(None)* | **Missing** | No similarity scoring or semantic duplicate detection across registered skills/tools. | Risk of creating redundant skills or agents. | Add fuzzy & embedding/token-overlap duplicate detector. |
| **Gap Analysis & Recommendation Engine** | *(None)* | **Missing** | Does not output structured `Reuse`, `Adapt`, `Create`, or `Blocked` recommendations. | Callers receive raw lists rather than actionable guidance. | Implement formal Gap Analyzer returning structured decisions. |
| **Central Capability Catalog / Registry** | *(None)* | **Missing** | No standalone `CapabilityRegistry` exists under `SYSTEM/registries/`. | Capabilities are inferred ad-hoc from other registries. | Create `SYSTEM/registries/capability_registry.py`. |
| **Incremental Scanning & Cache Invalidation** | *(None)* | **Missing** | Queries registries from scratch every execution; no cache or file hash tracking. | Inefficient on large repositories. | Implement content-hashed scan cache. |

---

## 4. Section C: Capability Finder Self-Learning

**Current Path:** *(None — No learning package exists in Capability Finder)*  
**Target Path:** `SYSTEM/agents/capability_finder/learning/`  

| Component / Capability | Current Path | Status | Evidence | Dependency / Risk | Recommended Action |
|:---|:---|:---:|:---|:---|:---|
| **Learning-Case Collection** | *(None)* | **Missing** | No experience recording, query tracking, or outcome logging in `CapabilityFinderAgent`. | Cannot learn from past queries. | Implement `learning/case_collector.py` modeled on MAA. |
| **Outcome Recording & Decision History** | *(None)* | **Missing** | Does not record why an agent/skill was chosen or whether the chosen component succeeded. | Zero tracking of downstream capability utility. | Log capability recommendations to `history_service`. |
| **Execution & Reviewer Feedback** | *(None)* | **Missing** | No interface to accept feedback on whether a recommended capability was effective or deficient. | Feedback cannot influence future matches. | Add feedback recording method. |
| **Agent-Scoped Memory Integration** | `SYSTEM/agents/system_agents/capability_finder/memory/memory_policy.json` | **Partial** | Policy file exists (`retention_days: 90`), but agent code does not read or write scoped memory. | Memory policy is inert. | Connect agent to `ScopedMemoryManager`. |
| **Distinguishing Selection from Environment Failure** | *(None)* | **Missing** | No error classification separating missing prerequisite from inappropriate capability match. | Risk of learning false lessons from system downtime. | Implement failure attribution classifier. |
| **Evidence-Derived Lesson Proposals** | *(None)* | **Missing** | No reflection engine or lesson synthesis mechanism. | Cannot propose improvements. | Implement `learning/reflection_engine.py` for capabilities. |
| **Repeatable Benchmark Evaluation Suite** | *(None)* | **Missing** | No deterministic capability discovery benchmark cases or test fixtures exist. | Cannot measure recommendation accuracy objectively. | Create `evaluations/capability_benchmark.json`. |
| **Measurable Improvement vs Baseline** | *(None)* | **Missing** | No baseline scoring or regression detection for capability recommendations. | Risk of silent recommendation degradation. | Implement evaluation runner with regression tolerance. |
| **Versioned Learning Rules** | *(None)* | **Missing** | No versioned capability mapping strategy or declarative rules document. | Matching rules are hardcoded in Python. | Create declarative `strategies/active/capability_strategy.json`. |
| **Approval-Controlled Publication of Lessons** | *(None)* | **Missing** | No integration with Laxman Approval for publishing newly verified capability rules. | Ungoverned updates or zero updates. | Bridge verified proposals to `LaxmanApprovalEngine`. |
| **Rejected-Proposal History & Rollback** | *(None)* | **Missing** | No audit trail of rejected matching rules or strategy rollback manager. | Inability to revert bad matching heuristics. | Implement rollback mechanism in strategy manager. |
| **Stale Knowledge Detection** | *(None)* | **Missing** | No TTL, deprecation checks, or orphaned capability purging. | Risk of recommending obsolete or deleted code. | Implement stale reference detection against filesystem. |
| **Protection Against Repeated Failures as Multi-Evidence** | *(None)* | **Missing** | No deduplication window or correlation check for identical repeated failures. | Flawed confidence inflation from repeated runs. | Add idempotency & correlation deduplication. |

---

## 5. Section D: Skill Factory

**Current Path:** `SYSTEM/agents/system_agents/skill_factory/`  
**Target Path:** `SYSTEM/agents/skill_factory/` (Sibling directory)  

| Component / Capability | Current Path | Status | Evidence | Dependency / Risk | Recommended Action |
|:---|:---|:---:|:---|:---|:---|
| **Directory Placement** | `SYSTEM/agents/system_agents/skill_factory/` | **Partial** | Nested in `system_agents/` rather than directly under `SYSTEM/agents/`. | Risk of import breakages during relocation. | Relocate to `SYSTEM/agents/skill_factory/` with backward compatibility shims. |
| **Security & Token Leakage Audit** | `SYSTEM/agents/system_agents/skill_factory/agent.py#L56-L67` | **Implemented** | Calls `skill_registry.audit_skill_content()` to check prohibited tokens, shell calls, dangerous imports. | Verified by unit tests. | Retain existing static auditor. |
| **Candidate Quarantine Staging** | `SYSTEM/agents/system_agents/skill_factory/agent.py#L69-L93` | **Implemented** | Calls `skill_registry.stage_external_candidate()` to write unverified skills to `SYSTEM/skills/staging/`. | Working and quarantined from production catalog. | Retain quarantine staging workflow. |
| **Publication to Canonical Central Library** | `SYSTEM/agents/system_agents/skill_factory/agent.py#L94-L101` | **Missing** | Action `promote` returns `error="Action not implemented yet"`, `status="failed"`. | Blocked: cannot publish candidate skills to production! | Implement `promote` action moving staged skill to catalog with approval check. |
| **Autonomous Skill Synthesis & Adaptation** | *(None)* | **Partial** | Expects caller to pass raw `content` string. No LLM synthesis prompt or template adaptation logic. | Cannot author skills autonomously from brief. | Implement skill prompt generator and AST builder. |
| **Structural Schema & Frontmatter Validation** | `SYSTEM/registries/skill_registry.py#L110-L150` | **Implemented** | Validates YAML frontmatter (`name`, `description`, `version`, `tags`, `dependencies`). | Working. | Retain schema validator. |
| **Testing & Approval Workflow** | *(None)* | **Missing** | No integration with test runners to verify skill instructions, nor integration with `LaxmanApprovalEngine`. | Candidate skills cannot be tested or approved formally. | Bridge staging promotion to Laxman Approval. |
| **Versioning & Duplicate Prevention** | `SYSTEM/registries/skill_registry.py` | **Partial** | Enforces unique filenames, but lacks semantic similarity checks against existing approved skills. | Potential for duplicate skills under different names. | Add semantic duplicate checker in Skill Factory. |

---

## 6. Section E: Architecture Validator

**Current Path:** *(None — No dedicated agent exists)*  
**Target Path:** `SYSTEM/agents/architecture_validator/`  

| Component / Capability | Current Path | Status | Evidence | Dependency / Risk | Recommended Action |
|:---|:---|:---:|:---|:---|:---|
| **Dedicated Agent Implementation** | *(None)* | **Missing** | No directory or class named `ArchitectureValidatorAgent` exists under `SYSTEM/agents/`. | System lacks autonomous architectural self-policing. | Implement `ArchitectureValidatorAgent` in Phase 5. |
| **Package Boundary & Direction Enforcement** | `tests/test_agent_architecture_reorg.py` | **Partial** | Test suite checks package imports statically, but no agent checks runtime boundaries autonomously. | Manual testing only; no agentic detection. | Implement AST import-direction validator. |
| **Circular Import Detection** | `SYSTEM/agents/main_architecture_agent/planning/plan_evaluator.py` | **Partial** | Plan evaluator detects circular task dependencies, but Python module circular imports are not scanned. | Import errors only surface at test collection time. | Build static import cycle detector using `ast`. |
| **Duplicate Implementation Detection** | *(None)* | **Missing** | No automated agent scans for duplicate functions, utility copies, or conflicting shims. | Risk of accumulating legacy duplicates. | Implement code similarity & signature scanner. |
| **Registry Consistency & Integrity Verification** | `SYSTEM/registries/agent_registry.py#L356-L390` | **Partial** | `validate_registry()` checks 14 video agents, but system subagents are not verified against target spec. | Missing agents go unnoticed by runtime check. | Implement complete 17-agent registry validator. |
| **Frozen-File Integrity Protection** | *(Ad-hoc scripts)* | **Partial** | Frozen-file hashes are verified manually or in batch scripts, not by an active architecture agent. | Risk of silent modification during development. | Implement automated frozen-file hash watchdog. |

---

## 7. Section F: Verification & Test Agent

**Current Path:** *(None — No dedicated agent exists)*  
**Target Path:** `SYSTEM/agents/verification_test_agent/`  

| Component / Capability | Current Path | Status | Evidence | Dependency / Risk | Recommended Action |
|:---|:---|:---:|:---|:---|:---|
| **Dedicated Agent Implementation** | *(None)* | **Missing** | No directory or class named `VerificationTestAgent` exists under `SYSTEM/agents/`. | Testing relies on manual terminal commands or IDE. | Implement `VerificationTestAgent` in Phase 6. |
| **Focused Test Planning & Selection** | *(None)* | **Missing** | No agent selects which test files to execute based on modified source files. | Rerunning all tests wastes compute; running too few misses bugs. | Implement change-aware test selector. |
| **Subprocess Execution & Exit Code Handling** | `SYSTEM/observability/evaluation.py` | **Partial** | Evaluation engine runs evaluation cases in memory, but does not invoke and monitor external test processes. | Cannot autonomously supervise pytest runs. | Implement pytest subprocess runner with timeout & exit-code capture. |
| **Baseline Regression Classification** | `SYSTEM/agents/main_architecture_agent/evaluations/evaluation_runner.py` | **Partial** | Benchmark runner classifies strategy regressions, but unit/integration test regressions are not tracked. | Cannot detect if a code commit broke a previously passing test. | Build historical test result comparison engine. |
| **Evidence-Based Test Reporting** | *(None)* | **Missing** | Test reports are generated manually in markdown by developers. | No standardized, reproducible test execution artifacts. | Implement automated JUnit/JSON test report generator. |

---

## 8. Section G: Security & Policy Agent

**Current Path:** *(None — No dedicated agent exists)*  
**Target Path:** `SYSTEM/agents/security_policy_agent/`  

| Component / Capability | Current Path | Status | Evidence | Dependency / Risk | Recommended Action |
|:---|:---|:---:|:---|:---|:---|
| **Dedicated Agent Implementation** | *(None)* | **Missing** | No directory or class named `SecurityPolicyAgent` exists under `SYSTEM/agents/`. | Security checks are fragmented across multiple modules. | Implement `SecurityPolicyAgent` in Phase 7. |
| **Tool Allowlist Enforcement** | `SYSTEM/agents/shared/base_agent.py#L16-L19` | **Partial** | `AgentMetadata.allowed_tools` list exists, but `BaseAgent.invoke()` does not actively block unauthorized tool calls. | Tool allowlist is descriptive rather than preventative. | Enforce tool allowlist interception at runtime. |
| **Laxman Approval Gate Interception** | `SYSTEM/approvals/guard.py` | **Implemented** | `ApprovalGuard` checks approved state before sensitive operations. | Working and verified by 18 approval tests. | Connect SecurityPolicyAgent to ApprovalGuard. |
| **Secret & Token Redaction** | `SYSTEM/agents/shared/communication.py#L30-L82` | **Implemented** | `redact_sensitive_data()` and `redact_object()` scrub secrets from communications and logs. | Working and concurrency-safe. | Retain and centralize redaction rules. |
| **Filesystem Path Confinement & Sandbox** | `SYSTEM/memory/store.py` | **Partial** | `project_dir()` confines paths to `projects/`, but arbitrary filesystem reads outside `projects/` are not blocked. | Potential path traversal in custom skills or scripts. | Implement strict path confinement sandbox. |
| **Immutable Audit Logging** | `SYSTEM/history/history_service.py` | **Implemented** | `HistoryService.record_audit()` logs structured `AuditRecord`s to append-only `config/history/audits.jsonl`. | Working and thread-safe. | Connect SecurityPolicyAgent as audit supervisor. |
