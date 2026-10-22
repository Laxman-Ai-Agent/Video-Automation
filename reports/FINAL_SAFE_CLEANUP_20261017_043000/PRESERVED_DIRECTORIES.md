# Preserved Directories & Intentional Retention Evidence

**Date:** 2026-10-17 04:30:00 IST  
**Repository Root:** `E:\audio-to-video`  
**Git Branch:** `agents-building` | **HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Status:** 100% AUDITED — EVIDENCE-BACKED RETENTION  

---

## 1. Executive Summary

As instructed by operator guidelines, non-canonical directories were not deleted reflexively. Each candidate was audited for:
1. Physical NTFS junction dependencies.
2. Active callers in scripts, CLI tools, and test fixtures.
3. User data, checkpoints, or downloaded machine learning weights.

This document details the exact technical reasons why each non-canonical or legacy directory was intentionally preserved.

---

## 2. Detailed Retention Matrix

| Directory Path | Classification | Physical Size | Specific Retention Justification & Callers |
| :--- | :--- | :--- | :--- |
| `backend/` | `REQUIRED_COMPATIBILITY` | ~1.50 MB (120 files) | **Active Caller Dependency:** Contains legacy compatibility modules. While 100% of its modules exist canonically in `SYSTEM/`, `VIDEO_ENGINE/`, and `UI/backend/`, older test fixtures (e.g. `tests/conftest.py` importing `backend.autoplan` and `backend.llm_client`, and `tests/test_skills_and_shared_memory.py` importing `backend.shared_memory`) still reference `backend`. Deleting `backend/` immediately would cause multi-suite test failures. |
| `frontend/` (root) | `LEGACY_BUT_IN_USE` | 213.1 MB | **Physical Junction Target:** Contains the actual, physical `frontend/node_modules/` folder (~210 MB). The canonical directory `UI/frontend/node_modules` is an NTFS junction pointing here. Deleting root `frontend/` would break npm dependencies across the canonical UI. |
| `remotion/` (root) | `LEGACY_BUT_IN_USE` | 1.52 GB | **Physical Junction Target:** Contains the actual, physical `remotion/node_modules/` folder (~1.52 GB) and the Chromium headless executable. The canonical directory `VIDEO_ENGINE/remotion/node_modules` is an NTFS junction pointing here. Deleting root `remotion/` would break all video rendering dependencies. |
| `config/` | `USER_DATA_PRESERVE` | ~15 KB (11 files) | **Active Runtime Configuration:** Every file is an active, live state store: `.laxman_pin_hash` (operator security PIN), `approvals_queue.json`, `approvals_audit.jsonl`, `llm_usage.json` (token metrics), `shared_memory.json`, and `eval_suites.json`. |
| `skills/` | `MIGRATE_THEN_REASSESS` | 17.6 KB (7 files) | **Test Fixture Dependency:** Although `SYSTEM/skills/` exists with identical `SKILL.md` files, `tests/test_skills_and_shared_memory.py:27` explicitly executes: `if (config.PROJECT_ROOT / "skills").exists(): shutil.copytree(...)`. Deleting root `skills/` causes test isolation fixtures to miss seed skills. |
| `projects/` | `USER_DATA_PRESERVE` | 333.0 MB (30 projects) | **User Data Protection:** Contains user video generation projects, audio narration WAVs, Whisper transcripts, and generated artifacts. |
| `models/` | `USER_DATA_PRESERVE` | 1.53 GB (8 files) | **ASR Model Weights:** Pre-downloaded neural network weights for Faster-Whisper (`models--Systran--faster-whisper-medium`). Enables offline transcription without remote network calls. |
| `resource-library/` | `USER_DATA_PRESERVE` | 1.65 MB (80 files) | **Offline Asset Catalog:** Royalty-free fonts (Noto Sans Telugu), SFX audio clips, licenses, and motion graphic presets. |
| `tests/` | `TEST_SUITE` | 9.69 MB (167 files) | **Test Suite:** Centralized repository of 68 Python unit, integration, and E2E test suites. |
| `improvements/` | `DOCUMENTATION` | 74.3 MB (291 files) | **Architecture Specs & Assets:** Complete architectural plans (A0–A4, Phase 1–10) and reference media (`sampel video.mp4`). |
| `reports/` | `DOCUMENTATION` | 56.8 MB (381 files) | **Audit Artifacts:** Historical migration batch reports, discrepancy audits, and inventories. |

---

## 3. The Root Legacy Retention Verdict

Removing `backend/`, root `frontend/`, or root `remotion/` at this stage without modifying launch scripts and relocating dependency stores would violate safety constraints. They are preserved under strict `REQUIRED_COMPATIBILITY` status until a future planned refactor can safely migrate remaining test fixtures and invert the dependency junctions.
