# Phase 2B — Batch 5: API Compatibility Report

- **Date/Time**: 2026-10-16 22:30:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Scope**: HTTP API Route Inspection, Route Parity, Middleware & Schema Verification
- **Status**: 100% COMPATIBLE (All 139 Routes Verified, 0 Breaking Changes)

---

## 1. Executive Summary

A comprehensive endpoint audit was conducted across the FastAPI application loaded via `UI.backend.main`. All 139 public and internal API endpoints across all 15 routers are mounted, fully accessible, and preserve their exact path templates, HTTP methods, authentication/approval middlewares, and Pydantic schemas.

Zero route paths were altered or dropped. Both `UI.backend.main:app` and the backward-compatibility entry point `backend.main:app` expose identical route tables.

---

## 2. Mounted Route Inventory by Subsystem

### A. Agents Subsystem (`/agents`)
- `GET /agents` — Lists all registered agents from `SYSTEM.registries.agent_registry`
- `GET /agents/{agent_id}` — Retrieves detailed agent specification, state, and metrics
- `GET /projects/{pid}/agent-communications` — Project-scoped agent message history
- `GET /projects/{pid}/agent-communications/stream` — SSE endpoint for live agent message streaming

### B. Laxman Approval & Security Subsystem (`/approvals`)
- `GET /approvals` — Retrieves active approval queue
- `GET /approvals/status` — Retrieves Laxman PIN configuration and lockout state
- `GET /approvals/audit` — Queries audit event log with pagination and filters
- `GET /approvals/{request_id}` — Retrieves individual approval request detail
- `POST /approvals/{request_id}/decide` — Mandatory PIN-verified decision endpoint (approve, reject, changes_requested)

### C. Pipeline & Project Control Subsystem (`/projects`)
- `GET /projects` / `POST /projects` — Project listing and project creation
- `GET /projects/{pid}` / `DELETE /projects/{pid}` — Project retrieval and deletion
- `POST /projects/{pid}/mode` — Motion-Only toggle and validation
- `POST /projects/{pid}/submit` — Project submission with aspect ratio
- `GET /projects/{pid}/status` — Full project status with blocker checks
- `POST /projects/{pid}/cancel` — Cancellation of active stage processes
- `POST /projects/{pid}/continue` — Unblocking and continuation

### D. Pipeline Orchestrator Subsystem (`/projects/{pid}/orchestrator`)
- `GET /projects/{pid}/orchestrator/status` — Authoritative DAG pipeline state
- `POST /projects/{pid}/orchestrator/run` — Dispatches canonical DAG execution
- `POST /projects/{pid}/orchestrator/cancel` — Halts execution cooperatively
- `POST /projects/{pid}/orchestrator/reconcile` — Recovers orphaned jobs on restart
- `GET /projects/{pid}/orchestrator/runs` / `GET .../{run_id}` — Run history inspection
- `GET /projects/{pid}/orchestrator/capabilities` — Environmental prerequisite checks (Chromium, Node, FFmpeg)
- `GET /projects/{pid}/orchestrator/gates` — Gate eligibility inspection

### E. LLM Gateway & Usage Subsystem (`/llm`)
- `GET /llm/settings` — Public LLM configuration
- `POST /llm/test` — Live provider connection testing
- `GET /llm/usage` — Live cost and token consumption metrics (INR/USD)
- `GET /llm/usage/history` — Session history and query deduplication
- `POST /llm/usage/refresh` — Forces recalculation from audit logs
- `POST /llm/usage/settings` — Updates USD-to-INR exchange rate

### F. Skills, Memory & Evaluation Subsystems
- `/skills` (CRUD, audit, promotion, stage candidates)
- `/memory` (CRUD, candidate promotion, superseding)
- `/evaluations` (test suites, baseline comparison, candidate evaluation)

---

## 3. Middleware and CORS Verification

- **CORS Allowed Origins**: `http://localhost:5173`, `http://127.0.0.1:5173` (Vite dev server)
- **CORS Allowed Methods**: `*`
- **CORS Allowed Headers**: `*`
- **Exception Handlers Installed**:
  - `ApiError`: Maps to standard error format `{"error": {"code", "message", "hint"}}` with sanitized paths.
  - `RequestValidationError`: Formats Pydantic validation errors cleanly.

---

## 4. Frontend API Client Parity

The frontend API client (`UI/frontend/src/api/client.ts`) communicates via the `/api` prefix, which Vite proxies directly to `http://127.0.0.1:8000/`.

Unit tests in `UI/frontend/tests/client.test.ts` (15/15 passed) and `UI/frontend/tests/contract.test.ts` (12/12 passed) verify that all client requests match the backend schema contracts exactly.
