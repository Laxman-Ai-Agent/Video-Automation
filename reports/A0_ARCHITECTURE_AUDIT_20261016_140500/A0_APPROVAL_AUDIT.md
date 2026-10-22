# A0 Approval Audit — Human Approvals, Review Gates & Laxman Approval Readiness

**Audit ID:** A0-APP-01  
**Timestamp:** 2026-10-16T14:15:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Conceptual Separation of Gates & Enforcement

A key finding of this audit is that the codebase currently features three fundamentally distinct types of quality gates that must never be conflated:

1. **Automated LLM Review Gate:** A model-driven heuristic evaluation (in `backend/llm_review.py`) that scores an artifact against rubric criteria (e.g. visual concepts, kinetic typography readability). **An LLM review passing does NOT constitute human approval.**
2. **Deterministic Technical Policy Check:** Non-negotiable code assertions (in `backend/artifact_contracts.py` and `backend/motion_validation.py`) that verify schema validity, file existence, AST safety, frame arithmetic, or media container parameters.
3. **Mandatory Human Approval Gate:** An explicit sign-off decision submitted by a human operator (e.g. Timeline Approval, Final QC Playback Sign-off, Candidate Promotion).

---

## 2. Existing Approval & Review Gates Inventory

| Gate Identifier | Stage / Scope | Mechanism / File | Persistence Location | Enforcement Point | Staleness Behavior | Bypass Risk | Audit Trail | Status |
|---|---|---|---|---|---|---|---|---|
| **Gate 1: Timeline Approval** | Stage 9 (Timeline) | `backend/timeline_approval.py` | `projects/<pid>/timeline_approval_history[_9x16].json` | `backend/timeline_gate.py:require_approved` & `backend/render_video.py` | Binds to timeline SHA, build fingerprint, and render config; recalculates dynamically. If any input changes, `stale: True` locks render. | Low (checked immediately before spawning Remotion) | Append-only event log in `timeline_approval_history.json` | `verified_in_current_source` |
| **Gate 2: Final QC Playback Sign-off** | Stage 11 (Final QC) | `backend/final_qc.py` | `projects/<pid>/final_qc_review[_9x16].json` | `backend/agents/adapters/stage_adapters.py:FinalVideoDeliveryAdapter` | Binds to SHA-256 of candidate MP4 video. If video re-renders, new SHA invalidates prior review. | Low (checked before creating `delivery_manifest.json`) | Append-only review events in `final_qc_review.json` | `verified_in_current_source` |
| **Gate 3: Self-Learning Candidate Promotion** | System / Evaluation | `backend/evaluation.py` | `config/eval_candidates.json` | `backend/routes/evaluation.py:promote_candidate` | Quarantined candidate items cannot enter active memory/skill catalog without human promotion. | Low | Promotion records in candidate metadata | `verified_in_current_source` |
| **Gate 4: Stage LLM Reviews** | Stages 2–12 | `backend/llm_review.py` | `projects/<pid>/llm_review_<stage>.json` | `backend/orchestrator.py:is_stage_review_passed` | Re-evaluated on stage rerun; fail-closed blocks downstream progression. | Low (fail-closed) | Review records in JSON | `verified_in_current_source` |

---

## 3. Vulnerability & Bypass Analysis

### 3.1 Approver Identity is Self-Declared (No RBAC)
- In `backend/timeline_approval.py`:
  ```python
  # The approver's name is what the person typed: this application has no accounts, so it is recorded as self_declared.
  ```
  *Finding:* There is currently no authentication or cryptographic signature verification on the approver identity. Any caller with access to `POST /projects/{pid}/timeline/approve` or `POST /projects/{pid}/qc/review` can submit an approval by typing an arbitrary string (e.g. `reviewer: "Laxman"`).

### 3.2 Fragmented Approval Stores
- There is no unified database or single table of pending approvals.
- To discover what approvals are pending across projects, a client must scan each project directory individually and inspect `timeline_approval.state()` and `final_qc.state()`.

---

## 4. Laxman Approval Gap Analysis & Target Boundary

### 4.1 What Exists vs. What is Missing

| Capability | Current State | Laxman Approval Requirement | Gap Status |
|---|---|---|---|
| **Central Request Queue** | Fragmented across per-project files | Unified server-side queue of pending approval requests across all projects & agents | **Missing** |
| **Standardized Request Schema** | Ad-hoc parameters per stage | Common schema: `request_id`, `requester`, `project_id`, `risk_level`, `action_summary`, `affected_files`, `fingerprint`, `reversibility`, `expiry` | **Missing** |
| **Central Operator UI Inbox** | Separate stage pages (`TimelineApprovalPage.tsx`, `FinalQcPage.tsx`) | Unified **Laxman Approval Inbox** showing pending actions with previews, diffs, and risk ratings | **Missing** |
| **Immediate Enforcement** | Stage-level checks in `timeline_gate.py` and `stage_adapters.py` | Central `AuthorizationGuard` checked before any protected side-effect (render, publish, file write, skill promote) | **Partially Present** (Stage gates exist, but no central authorization guard) |
| **Tamper-Evident Audit Trail** | JSON files with event lists | Append-only, cryptographically linked or checksummed central audit log | **Partially Present** |
| **Rejection & Change Request** | Supported in `timeline_approval.py` | Unified change-request feedback loop across all approval types | **Partially Present** |

### 4.2 Recommended Laxman Approval Architecture for A1 / A2

```mermaid
graph TD
    subgraph Requesting_Actors ["Requesting Actors"]
        VEA["Video Engine Agents (Render, Delivery)"]
        SSA["System Subagents (Skill Finder, Skill Factory)"]
        SYS["System Operations (Candidate Promotion, Config Change)"]
    end

    subgraph Laxman_Approval_Subsystem ["Laxman Approval Subsystem (Target Architecture)"]
        ReqQueue["Central Approval Request Queue"]
        AuthGuard["Server-Side Authorization Guard"]
        AuditLog["Append-Only Central Audit Log"]
        LaxmanUI["Laxman Approval UI Inbox (Dedicated Screen)"]
    end

    subgraph Protected_Side_Effects ["Protected Side Effects"]
        RemotionRender["Execute Remotion Render"]
        FinalDelivery["Publish Final Video Delivery"]
        SkillPromotion["Promote Skill to Production"]
        MemoryPromotion["Promote Memory to Verified"]
    end

    VEA -->|Submit Request| ReqQueue
    SSA -->|Submit Request| ReqQueue
    SYS -->|Submit Request| ReqQueue

    ReqQueue <--> LaxmanUI
    LaxmanUI -->|Human Decision (Approve / Reject / Changes)| ReqQueue

    ReqQueue --> AuditLog
    ReqQueue --> AuthGuard

    AuthGuard -->|Verify Valid Human Approval| Protected_Side_Effects
```
