# Architecture

## Principle
Claude thinks ONCE, in text only (Phase 1). Everything after the user uploads images is plain code.
Claude never sees images. Contracts are JSON files (see `schemas.md`). Every step saves its output,
so any failed step can be re-run alone (idempotent, cached).

## Pipeline
```
audio.mp3
 -> transcribe.py (faster-whisper)            -> transcript.json
 -> cuts.py (pysbd + pydub silencedetect)     -> cuts.json
 -> /plan (Claude Code, text only)            -> scene_plan.json
                                              -> composition.json (image slots empty)
                                              -> prompts.txt + prompts_map.json
 === USER: download prompts.txt, make images, upload in UI, press Submit ===
 -> save uploads                              -> projects/{id}/assets/
 -> matcher.py (filename, else CLIP+Hungarian)-> match_report.json
 -> checks (Pillow, OpenCV, imagehash)        -> warnings in match_report
 -> bg_remove.py (rembg u2netp, icons only)   -> assets/cutouts/
 -> fill_slots.py                             -> composition.json (files filled)
 -> render.py (npx remotion render)           -> out.mp4
```

## Components
| Part | Tech | Role |
|------|------|------|
| backend | FastAPI | endpoints, job runner, file storage |
| remotion | Remotion + React | reads composition.json, renders mp4 |
| frontend | Vite + React | upload, prompts download, match check, preview, render |
| dashboard | Vite + React | read-only progress view of STATUS.json |
| Claude Code | `/plan` command | Phase 1 planning only |

## Backend endpoints (M7)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /projects | create project, upload audio |
| POST | /projects/{id}/transcribe | run Whisper (background) |
| GET | /projects/{id}/status | step + progress |
| POST | /projects/{id}/render | final render of the approved timeline |
| GET | /projects/{id}/result | out.mp4 |

Jobs run in background threads; progress stored in `projects/{id}/job.json`.
Long steps (Whisper, render) report percent so the UI can show a bar.

## Why /plan is run in Claude Code, not from the app
Calling Claude from inside the app needs API credits. The `/plan` command lives in
`.claude/commands/plan.md`; the user runs it in the terminal after transcription.
The UI shows "waiting for plan" until `scene_plan.json` appears, then enables the prompts download.

## /plan command contract
Input: `transcript.json`, `cuts.json`, `docs/schemas.md`, `docs/components.md` (patterns list).
Output: the four Phase 1 files, validated by pydantic (`python backend/validate.py <project>`).
Rules for /plan:
1. Split by meaning; each scene = one visual idea; use only cut points from cuts.json.
2. Pick a mode per scene; images only where they add value.
3. Pick a composition pattern per scene from `components.md`; do not invent layouts.
4. Write English prompts with the shared style suffix; roles and slots per image.
5. Highlight only key numbers/names; max 1-2 text elements per scene.
6. Vary transitions; never repeat the previous scene's transition.
7. Timeline: every `at` is inside the scene's start/end.

## Phase 2 matching details
1. Filename `NN.ext` -> prompt N (certain).
2. Remaining files: CLIP image embedding vs prompt text embedding, cosine matrix.
3. Hungarian assignment so one image maps to one prompt.
4. Low score/margin -> status `review` (UI asks user). Unmatched files -> `unused`.
5. Missing required prompts -> checklist in UI; render blocked until resolved or user skips (slot falls back to gradient + typography).

## Fallbacks (never crash the render)
| Problem | Fallback |
|---------|----------|
| missing optional image | drop layer |
| missing required image | gradient background + keyword text |
| low-res image | limit camera zoom to 1.05 |
| rembg failure | use original with soft mask |
| unknown pattern | `hero_only` |

## Performance (CPU laptop)
Preview 540p/15fps; final render 1080p/30fps once. Render concurrency 2-4.
Limit heavy effects (blur, particles) per scene. Pre-resize images to max 2560px wide.
