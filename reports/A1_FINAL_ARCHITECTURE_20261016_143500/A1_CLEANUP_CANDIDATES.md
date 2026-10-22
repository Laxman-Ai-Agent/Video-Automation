# A1 Cleanup Candidates — Evidence-Based Assessment

**Audit ID:** A1-CLN-01  
**Timestamp:** 2026-10-16T14:40:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Cleanup Policy & Categories

In strict accordance with `improvements/A1_Final_Architecture_and_Ownership_Plan/09_CLEANUP_CANDIDATE_POLICY.md`:
- **ZERO files or folders are deleted during Phase A1.**
- This register identifies candidates based on static import searches, Git tracking, runtime scripts, and test definitions.
- Items are strictly categorized into four classes:
  1. **`KEEP`**: Active source, required config, user data, test fixtures, model weights, or historical audit records.
  2. **`REMOVE-CANDIDATE`**: Multiple independent checks confirm the item is unreferenced, untracked/orphaned, and safe to delete in a later approved cleanup phase.
  3. **`REFACTOR`**: Required behavior or tests exist, but code or structure needs decoupling before removal.
  4. **`VERIFY`**: Evidence is incomplete, dynamic references may exist, or removal risks breaking tests.

---

## 2. Comprehensive Candidate Inventory

| Path | Size / Type | Git-Tracked? | References Checked | Build / Test / Config Refs | Evidence for Unused | Counter-Evidence / Caveats | Classification | Future Removal Checks | Rollback Plan |
|---|---|---|---|---|---|---|---|---|---|
| `dashboard/` | 175.7 MB / Folder (11,654 files) | **NO** (`git ls-files` is empty) | `backend/`, `frontend/`, root scripts | None. `PROJECT_OVERVIEW.md` stated it was removed 2026-10-13. | Contains only orphaned `node_modules` (@reduxjs/toolkit) and an old 2026-10-09 `status.json`. Zero source files remain. | None. Frontend uses `frontend/` exclusively. | **`REMOVE-CANDIDATE`** | Verify `npm run build` in `frontend/` and Uvicorn server pass with directory moved to trash. | Recreate or restore from recycle bin / backup archive. |
| `.claude/worktrees/intelligent-hellman-80f23f/` | 32.0 MB / Folder (339 files) | **NO** (`git ls-files` is empty) | Root codebase, `.claude/` | None. Old Claude Code worktree branch. | Duplicate copies of older backend and test files from an earlier migration. | Contains old plan references, but all active plans are in `improvements/`. | **`REMOVE-CANDIDATE`** | Confirm current git status and Claude Code commands do not mount this worktree. | Back up to `.claude_worktree_backup.zip` prior to deletion. |
| `STATUS.json` & `STATUS.md` | 8.5 KB / 15.6 KB | **YES** | `backend/`, `frontend/`, `tests/` | **Referenced in `tests/test_status.py` and `scripts/update_status.py`!** | Not referenced in active runtime pipeline or frontend UI. | **`tests/test_status.py` directly loads `STATUS.json` and asserts milestone task status!** Deleting breaks pytest. | **`VERIFY` / `REFACTOR`** | Must refactor or retire `test_status.py` in Phase A7 before `STATUS.json` can be removed. | `git checkout HEAD -- STATUS.json STATUS.md` |
| `PIPELINE_AUDIT_REPORT.txt` | 24.7 KB / File | **YES** | Root codebase | None | Static snapshot from 2026-10-12 audit. | Historical record documenting early audio pipeline audit. | **`KEEP`** | None (keep as historical documentation). | `git checkout HEAD -- PIPELINE_AUDIT_REPORT.txt` |
| `reports/AUTOFIX_BACKUP_*` | ~150 KB / Folders | **YES** | `backend/` | None | Staged snapshots from 2026-10-15 manual autofix verification. | Tracked in Git; preserves historical audit evidence of autofix diffs. | **`KEEP`** | None (keep as audit evidence). | `git checkout HEAD -- reports/` |
| `testing_audio_files/` | 17.4 MB / Folder | **YES** | `tests/` | Manual audio testing | Real audio test files (`02.wav`, `sample json.txt`). | Used by developers for manual end-to-end ingest testing. | **`KEEP`** | None (keep as test fixtures). | `git checkout HEAD -- testing_audio_files/` |
| `models/hf/` | ~1.5 GB / Folder | **NO** (Binary weights) | `backend/transcribe.py` | Local Whisper model path | Large binary weights directory. | Required by `faster-whisper-medium` in frozen Stage 2 Audio Analyzer. Deletion breaks transcription! | **`KEEP`** | Critical model dependency; never delete. | Re-download via huggingface_hub if missing. |
| `improvements/sampel video.mp4` | 73.6 MB / File | **YES** | User requirements | User reference | User-uploaded sample video. | Provided explicitly by user as gold-standard motion reference. | **`KEEP`** | Keep as user reference media. | `git checkout HEAD -- improvements/` |
| `backend/motion_template_selection.py` | 14.0 KB / File | **YES** | `stage_adapters.py` | Imported by `MotionTemplateSelectionAdapter` | Template selection is deprecated in Motion-Only mode. | Imported by adapter to return explicit `blocked` status and preserve 14-agent target schema. | **`KEEP` / `DEPRECATED`** | Keep as deprecated adapter module. | `git checkout HEAD -- backend/` |

---

## 3. Recommended Phased Cleanup Strategy (Phase A7)

1. **Phase A1 (Current):** Document candidates with evidence; **ZERO deletions executed**.
2. **Phase A7 (Cleanup Step 1 - Reclaim 207 MB of Untracked Disk Space):**
   - Create local zip backup of untracked directories: `dashboard/` (175.7 MB) and `.claude/worktrees/` (32.0 MB).
   - Delete `dashboard/` and `.claude/worktrees/`.
   - Run full regression test suite (121 tests) and `npm run typecheck` to verify zero disruption.
3. **Phase A7 (Cleanup Step 2 - Refactor Tracked Status Files):**
   - Refactor `tests/test_status.py` to decouple from root `STATUS.json` or archive both under `docs/archive/`.
