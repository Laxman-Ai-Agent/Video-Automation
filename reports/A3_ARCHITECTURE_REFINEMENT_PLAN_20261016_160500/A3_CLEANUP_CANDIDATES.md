# A3 — Cleanup Candidate Inventory & Assessment

**Document ID:** A3-CLN-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Authorization Policy:** **Zero files are deleted or modified during A3 planning.** This register provides evidence-backed classifications for future authorized cleanup.

---

## 1. Candidate Classification Standards

In strict accordance with `improvements/A3_Architecture_Refinement_and_Cleanup_Plan/08_CLEANUP_CANDIDATE_POLICY.md`:
- `KEEP`: Active source, configuration, documentation, or fixtures with ongoing utility.
- `REMOVE_CANDIDATE`: Multiple independent checks confirm the item is unreferenced, untracked/orphaned, and safe for future authorized removal.
- `REFACTOR_CANDIDATE`: Required behavior exists, but tight coupling requires refactoring or test migration before removal.
- `VERIFY`: Evidence is currently incomplete, dynamic references may exist, or ambiguity remains.
- `PROTECTED`: User project data, frozen files, unique assets, checkpoints, secrets, or binary weights. Never delete.

---

## 2. Comprehensive Candidate Inventory

| Path | Size / Count | Git Status | References & Scopes Checked | Direct / Runtime Consumers | Risk of Removal | Recommendation | Authorization in A3 |
|---|---|---|---|---|---|---|---|
| `dashboard/` | 167.56 MB (11,654 files) | **Untracked** (Removed) | Entire codebase, `package.json`, root scripts | None | Zero. External backup exists at `E:\a2v_tmp\backups\dashboard_backup_20261016_150000.zip`. | **REMOVED_VERIFIED** | Already removed in Phase A2. Verified absent. |
| `.claude/worktrees/intelligent-hellman-80f23f/` | 32.0 MB (339 files) | **Untracked** (`git ls-files` empty) | Codebase, scripts, `.claude/` config | None. Old Claude Code worktree branch from 2026-10-14. | Low. Duplicate copies of older backend and test code. | **`REMOVE_CANDIDATE`** | NOT authorized in A3 planning. Target for future execution. |
| `out/` | 30.1 MB (5 mp4 files) | **Untracked** (`git ls-files` empty) | `backend/`, `frontend/`, scripts | None. Standalone renders from Oct 8-12 (`gallery.mp4`, `layers.mp4`, `test.mp4`, `transitions.mp4`, `_t.mp4`). | Low. Ephemeral standalone outputs. Active pipeline renders to `projects/<pid>/out.mp4`. | **`REMOVE_CANDIDATE`** | NOT authorized in A3 planning. Target for future execution. |
| `STATUS.json` & `STATUS.md` | 8.5 KB / 15.6 KB | **Tracked** (`git ls-files` matches) | `tests/test_status.py`, `scripts/update_status.py` | `tests/test_status.py` loads `STATUS.json` and asserts milestones. | Medium. Deletion without refactoring breaks `pytest tests/test_status.py`. | **`REFACTOR_CANDIDATE`** | NOT authorized in A3 planning. Refactor `test_status.py` first. |
| `PIPELINE_AUDIT_REPORT.txt` | 24.7 KB (1 file) | **Tracked** | Entire codebase | None | Low. Historical audit artifact from 2026-10-12. | **`KEEP`** | Retain as historical audit record. |
| `testing_audio_files/` | 17.4 MB (2 files) | **Tracked** | Manual test workflows | Manual testing / QA (`02.wav`, `sample json.txt`) | Low. Useful offline developer fixtures. | **`KEEP`** | Retain as offline test fixtures. |
| `models/hf/` | ~1.5 GB (binary files) | **Ignored / Local** | `backend/transcribe.py` | Required by frozen Stage 2 Whisper ASR (`faster-whisper-medium`). | **CRITICAL**. Deletion breaks audio transcription! | **`PROTECTED`** | Critical model assets. Never delete. |
| `projects/` | Variable (User data) | **Local data** | Orchestrator, store, API routes | Contains user project state, checkpoints, narration audio, generated TSX. | **CRITICAL**. Data loss of active user projects. | **`PROTECTED`** | User project assets. Never delete. |
| `config/.laxman_pin_hash` | 134 bytes | **Ignored** (`.gitignore:29`) | `backend/approvals/pin_service.py` | Laxman Approval Engine PIN verification | **HIGH**. Deletion resets operator PIN authentication to unconfigured state. | **`PROTECTED`** | Operator authentication secret. Never delete. |
| `backend/motion_template_selection.py` | 14.0 KB | **Tracked** | `backend/agents/registry.py` | `MotionTemplateSelectionAdapter` imports it to maintain 14-agent schema. | Medium. Deletion breaks registry schema consistency. | **`KEEP_DEPRECATED`** | Retain as deprecated adapter module. |

---

## 3. Deep Dive on Removal Candidates

### 3.1 `.claude/worktrees/intelligent-hellman-80f23f/`
- **Current State**: Located at `E:\audio-to-video\.claude\worktrees\intelligent-hellman-80f23f`. Contains 339 files totaling 32,023,555 bytes.
- **Investigation Results**:
  - `git ls-files .claude/worktrees` returns empty (untracked).
  - Search across all Python, TypeScript, JSON, and shell scripts returned zero imports or path references.
  - Files inside this directory are older, out-of-date snapshots of `backend/`, `frontend/`, and `tests/` generated during an automated worktree branch in mid-October.
  - Active Claude Code commands and git worktrees do not mount or depend on this path.
- **Future Removal Protocol**:
  1. Create an external backup archive: `E:\a2v_tmp\backups\worktree_backup_<timestamp>.zip`.
  2. Verify archive readability with `zipfile.testzip()`.
  3. Delete only `.claude/worktrees/intelligent-hellman-80f23f/`.
  4. Run `git status` to verify zero tracked file impact.

### 3.2 `out/` Directory
- **Current State**: Located at `E:\audio-to-video\out`. Contains 5 mp4 video files (`gallery.mp4`, `layers.mp4`, `test.mp4`, `transitions.mp4`, `_t.mp4`) and an empty `_probe/` directory totaling 30,128,120 bytes.
- **Investigation Results**:
  - `git ls-files out/` returns empty (untracked).
  - Search across `backend/`, `frontend/`, and `scripts/` returned zero code references to the top-level `out/` path.
  - The canonical video pipeline outputs all project renders to `projects/<project_id>/out.mp4` and `projects/<project_id>/delivery.json` managed via `backend/store.py`.
  - The files in `out/` are ad-hoc test renders generated on October 8–12 during initial Remotion proofs-of-concept.
- **Future Removal Protocol**:
  1. Create external backup archive: `E:\a2v_tmp\backups\out_legacy_backup_<timestamp>.zip`.
  2. Verify archive readability.
  3. Delete `out/`.
  4. Verify that running `pytest tests/test_timeline_render_qc_delivery.py` remains completely green.

### 3.3 `STATUS.json` & `STATUS.md` Refactoring Candidate
- **Current State**: Root-level files tracked in Git.
- **Investigation Results**:
  - `STATUS.json` contains static task checkboxes from early October.
  - `tests/test_status.py` actively reads `STATUS.json`:
    ```python
    with open("STATUS.json") as f:
        data = json.load(f)
    ```
  - Deleting `STATUS.json` immediately causes test failure in `pytest tests/test_status.py`.
- **Refactoring Strategy (Future Implementation)**:
  1. Refactor `tests/test_status.py` to assert against `backend/agents/registry.py` and `pipeline_state.py` rather than static root JSON files.
  2. Alternatively, move `STATUS.json` and `STATUS.md` into `docs/archive/` and update `test_status.py` accordingly.
  3. Only after test decoupling is verified, retire the obsolete root files.

---

## 4. Execution Boundary Statement

**No files have been deleted, moved, or modified during Phase A3.** The candidate inventory above is established purely as a technical roadmap for a future explicitly authorized cleanup execution.
