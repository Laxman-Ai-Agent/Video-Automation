# Disk Usage Analysis & Storage Breakdown

**Date:** 2026-10-17 04:22:00 IST  
**Repository Root:** `E:\audio-to-video`  
**Git Branch:** `agents-building` | **HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Status:** 100% AUDITED PHYSICAL STORAGE  

---

## 1. Storage Overview: Logical vs Physical

A primary risk in disk measurement on Windows is double-counting storage when symbolic links or NTFS directory junctions are followed.
- **Physical Reality:**
  - `E:\audio-to-video\frontend\node_modules\` physically stores the React 19 npm packages (~210 MB).
  - `E:\audio-to-video\remotion\node_modules\` physically stores the Remotion video engine packages (~1.52 GB).
  - `UI/frontend/node_modules` and `VIDEO_ENGINE/remotion/node_modules` are zero-byte reparse pointers (junctions).
  - The measurements below reflect **true physical storage** without junction inflation.

---

## 2. Area Disk Usage Breakdown

| Major Folder / Area | Physical Disk Usage | Percentage | Description |
| :--- | :--- | :--- | :--- |
| `.venv/` | **2.81 GB** (2,810 MB) | 41.3% | Python 3.10 virtual environment (PyTorch, TorchVision, OpenCV, FFmpeg) |
| `models/` | **1.53 GB** (1,531 MB) | 22.5% | Local `faster-whisper-medium` neural network weights |
| `remotion/` (root physical store) | **1.53 GB** (1,526 MB) | 22.4% | Remotion root hosting `node_modules` and Chromium headless shell |
| `projects/` | **333.0 MB** | 4.9% | 30 user video project directories, audio, and render outputs |
| `frontend/` (root physical store) | **213.1 MB** | 3.1% | Root frontend hosting `node_modules` and build output |
| `VIDEO_ENGINE/` | **197.3 MB** | 2.9% | Pipeline stages, test render frames, Remotion source (excl. junction) |
| `improvements/` | **74.3 MB** | 1.1% | Reference sample videos (`sampel video.mp4`: 73.6 MB) & phase plans |
| `reports/` | **56.8 MB** | 0.8% | Audit reports and benchmark video captures (`RENDER_QC`: 33.1 MB) |
| `tests/` | **9.69 MB** | 0.1% | Multi-suite Python tests and fixtures |
| `UI/` | **2.41 MB** | <0.1% | Canonical UI frontend source & backend routes (excl. junction) |
| `resource-library/` | **1.65 MB** | <0.1% | Google Fonts (Noto Sans Telugu), SFX audio clips, licenses |
| `backend/` | **1.50 MB** | <0.1% | 120 legacy Python modules (preserved compatibility layer) |
| `SYSTEM/` | **848.6 KB** | <0.1% | Canonical agents, approvals, memory, registries, observability |
| `skills/` | **17.6 KB** | <0.1% | Agent skill Markdown instruction files |
| `config/` | **15.2 KB** | <0.1% | Runtime JSON configs (LLM usage, Approvals, Memory) |
| `scripts/` | **3.55 KB** | <0.1% | CLI administration utilities |
| Root Regular Files | **232.0 KB** | <0.1% | Configuration files, READMEs, batches |
| **TOTAL REPOSITORY (Physical)** | **~6.80 GB** | **100.0%** | **Entire physical footprint on Drive E:** |

---

## 3. Top 15 Largest Files in the Repository

| # | File Relative Path | Size | Category / Purpose |
|---|---|---|---|
| 1 | `models/hf/hub/.../model.bin` | **1.53 GB** | Faster-Whisper ASR neural network weights |
| 2 | `.venv/Lib/site-packages/torch/lib/torch_cpu.dll` | **305.9 MB** | PyTorch native C++ CPU inference engine |
| 3 | `remotion/node_modules/.../chrome-headless-shell.exe` | **221.1 MB** | Headless Chromium browser used by Remotion |
| 4 | `remotion/node_modules/.cache/.../2.pack` | **172.0 MB** | Webpack build cache for Remotion dev |
| 5 | `remotion/node_modules/.cache/.../0.pack` | **170.8 MB** | Webpack build cache for Remotion production |
| 6 | `.git/objects/pack/pack-5e4af53a6...pack` | **157.7 MB** | Git repository version history packfile |
| 7 | `.venv/Lib/site-packages/llvmlite/binding/llvmlite.dll` | **120.4 MB** | LLVM JIT compiler binding for Numba |
| 8 | `.venv/Lib/site-packages/playwright/driver/node.exe` | **93.6 MB** | Playwright headless browser driver |
| 9 | `.venv/Lib/site-packages/cv2/cv2.pyd` | **86.3 MB** | OpenCV computer vision Python extension |
| 10 | `remotion/node_modules/.cache/.../0.pack` | **74.0 MB** | Webpack build cache |
| 11 | `improvements/sampel video.mp4` | **73.6 MB** | Sample reference video for pipeline comparison |
| 12 | `.venv/Lib/site-packages/ctranslate2/ctranslate2.dll` | **59.3 MB** | CTranslate2 inference engine for Whisper |
| 13 | `remotion/node_modules/.cache/.../8.pack` | **52.0 MB** | Webpack production bundle pack |
| 14 | `remotion/node_modules/@rspack/binding-win32-x64-msvc/...` | **47.8 MB** | Rspack native Rust binary |
| 15 | `reports/RENDER_QC/.../out.mp4` | **33.2 MB** | Benchmark QC video render artifact |

---

## 4. Key Takeaways for Storage Optimization

1. **Clean Code Footprint:** The actual operational application codebase (`SYSTEM/`, `UI/`, and `VIDEO_ENGINE/` excluding heavy models and vendor bundles) is exceptionally compact at **under 202 MB**.
2. **Deterministic Model Storage:** The 1.53 GB `models/` directory contains pre-downloaded Faster-Whisper weights, ensuring the application operates fully offline without downloading weights during pipeline runs.
3. **Cache Growth in Remotion:** Over 460 MB of Webpack cache (`remotion/node_modules/.cache`) exists from previous dev/prod builds; this can be safely purged if disk space is ever required without affecting source integrity.
