# A3 — Risk Register, Rollback Procedures & Stop Conditions

**Document ID:** A3-RSK-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  

---

## 1. Risk Identification & Mitigation Register

| Risk ID | Description & Potential Impact | Likelihood | Impact | Severity | Mitigation & Preventative Safeguards |
|---|---|---|---|---|---|
| **R-01** | **Breaking Agent Communication Log Schema**<br>Mutating agent IDs or dropping required metadata fields could invalidate historical records in `communications.jsonl`. | Low | High | Medium | Add `category` as an optional / defaulted field in `AgentMetadata`. Preserve exact strings for all 14 existing agent IDs. |
| **R-02** | **Accidental Deletion of Dynamically Discovered Files**<br>Removing files that appear unreferenced in grep but are loaded via runtime globs, build plugins, or CLI launchers. | Low | Critical | High | Strict pre-removal protocol: require multi-file reference checks across packaging, build scripts, tests, and runtime before any removal. Require external backup. |
| **R-03** | **Premature Retirement of Legacy Pipeline Routes**<br>Deleting `backend/jobs.py` or `pipeline.py` before confirming all frontend and script callers use `/orchestrator/run`. | Medium | High | High | Keep `jobs.py` and `pipeline.py` active as compatibility wrappers. Enforce convergence roadmap with backward-compatible routing flags. |
| **R-04** | **Misrepresenting Planned Subagents as Active**<br>Creating placeholder cards or runtime stubs for Skill Finder or Skill Factory before they are implemented, causing confusing failures. | Low | Medium | Low | Clearly tag planned subagents with `STATUS: PLANNED (Phase A5/A6)`. Do not register active runtime adapters for unbuilt agents. |
| **R-05** | **Violation of Frozen File Invariants**<br>Any unintended modification to `transcribe.py`, `transcript_review.py`, or `scene_segmentation.py`. | Very Low | Critical | High | Maintain bit-level SHA-256 pre-check and post-check before every code batch. Fail-closed immediately if a hash changes. |
| **R-06** | **Accidental Loss of User Project Data or PIN Hash**<br>Wildcard deletion (`rm -rf`) affecting `projects/` or `config/.laxman_pin_hash`. | Very Low | Critical | High | Forbid wildcard removals or broad `git clean`. Only target explicit, verified relative file paths. Require external archive creation. |

---

## 2. Hard Stop Conditions

If any of the following conditions occur during any phase of work, execution must **STOP IMMEDIATELY** and report the blocker to the human operator:

1. **Frozen Module Hash Mismatch**: If `Get-FileHash` on `transcribe.py`, `transcript_review.py`, or `scene_segmentation.py` deviates from canonical hashes.
2. **Untracked User Data Hazard**: If a proposed cleanup path touches `projects/`, `config/.laxman_pin_hash`, or uncommitted user edits.
3. **Ambiguous Dependency Chain**: If a file slated for removal is discovered to be referenced by an active test, script, or dynamic loader.
4. **Discrepancy in Backup Verification**: If an external backup archive fails `zipfile.testzip()` or size verification before removal.
5. **Contract Test Breakage**: If modifying agent metadata breaks existing OpenAPI snapshots or frontend typechecks.

---

## 3. Rollback Procedures (For Future Authorized Execution)

### 3.1 Rollback for Batch 1 (Backend Agent Contracts & Registry)
```powershell
# Discard edits to contracts.py and registry.py
git checkout HEAD -- backend/agents/contracts.py backend/agents/registry.py
# Verify restoration
pytest tests/test_agent_routes.py -v
```

### 3.2 Rollback for Batch 2 (Frontend Types & Client)
```powershell
# Discard edits to frontend agentTypes.ts
git checkout HEAD -- frontend/src/api/agentTypes.ts
# Verify compilation
npm --prefix frontend run typecheck
```

### 3.3 Rollback for Batch 3 (Frontend Agents UI)
```powershell
# Remove newly added UI page and revert App.tsx
Remove-Item -Force frontend/src/pages/AgentsPage.tsx
git checkout HEAD -- frontend/src/App.tsx
# Verify compilation
npm --prefix frontend run typecheck
```

### 3.4 Rollback for Batch 4 (Cleanup Step 1 - Untracked File Restoration)
```powershell
# Restore untracked worktrees and out/ from verified backup archive
python -c "import zipfile; zipfile.ZipFile(r'E:\a2v_tmp\backups\a3_cleanup_step1_backup_<timestamp>.zip').extractall(r'E:\audio-to-video')"
# Verify restoration
Test-Path .claude/worktrees/intelligent-hellman-80f23f
Test-Path out
```

### 3.5 Rollback for Batch 5 (Cleanup Step 2 - Status Files Restoration)
```powershell
# Restore tracked status files and test
git checkout HEAD -- STATUS.json STATUS.md tests/test_status.py
# Verify
pytest tests/test_status.py -v
```
