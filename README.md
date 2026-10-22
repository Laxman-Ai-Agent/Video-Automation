# Audio to Video (Telugu)

Turns one Telugu narration into a documentary-style video with motion graphics, synced to the audio.
You supply the audio and the images; the program plans, matches, composes and renders.

## What you need
Windows 11, 16 GB RAM (8 GB free while transcribing), Python 3.12, Node.js 20+, `ffmpeg` and `ffprobe` on PATH.
No GPU is needed. The Whisper `large-v3` model must already be in the Hugging Face cache (it is never downloaded).
Video fonts (Poppins, Noto Sans Telugu) are fetched from Google Fonts while rendering, so rendering needs internet.

## Set up (once)
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
npm run install:all
```

## Run
Double-click `start.bat` (or run `npm start`). It opens:
- the app: http://localhost:5173 (UI) with the API on http://localhost:8000

`runproject.bat` starts only the API and the UI.

## How to make a video
1. **Project**: give a name and drop in the Telugu audio.
2. **Transcript**: press Start. Whisper runs on the CPU (a few minutes per minute of audio).
3. **Plan**: the page shows a command like `/plan my-video`. Run it once in Claude Code; the page continues by itself.
4. **Prompts**: download `prompts.txt` and generate the images elsewhere. Name them `1.png`, `2.png` ... or leave any names.
5. **Images**: upload the images (files or a folder), then Submit. Doubtful matches go to **Match check**.
6. **Render**: render a quick preview first, then the final 1080p video, and download it.

Command line (no UI): `.venv\Scripts\python.exe -m backend.cli build <id> [--preview] [--force]`.
Optional vertical video: add `--aspect 9:16` (writes `out_9x16.mp4` / `out_preview_9x16.mp4`; 16:9 stays the default and is not touched).
Before every render the pipeline checks the video it is about to make (`python -m backend.cli check <id> [--aspect 9:16]` runs the same check by hand): empty slots, repeated pictures, heavy crops, soft or blurry images, text outside the safe area, scene gaps and length. Errors stop the render with a plain message; warnings are kept in `prerender_report.json` for you to review.
In the UI, the Images step shows every prompt as a card; a prompt without an image has its own Upload Image button, and Apply processes all waiting uploads in one build. The progress panel lists every pipeline stage and offers Resume after a failure.
Planning is automatic: when transcription and cut points finish, the app writes the scene plan itself with your signed-in Claude CLI (same result as `/plan <id>`, which stays as the manual recovery), then Review workflow in the UI: the analysis table, then the prompt cards (edit, approving the analysis writes them with your signed-in Claude CLI (`claude -p`, no API key); Regenerate rewrites one prompt; `/regen <id> <n>` in Claude Code still works; approve), then the images (upload per prompt, crop editor, match without a render), then Continue to Timeline. Each of the four checkpoints is approved by you; everything in between runs by itself and no render starts until you press Preview or Render.

## Pipeline page (new)
After Submit the app opens `/p/<id>`: every stage with its real state. The run pauses at **Image Generation** (`/p/<id>/images`): make the images from the prompts, upload them, press **Set All Images to Prompt**, check **Missing Images**, then **Continue**. Then **Approve Timeline** and, as a separate step, **Render Video**. Restart the API (`runproject.bat`) after updating so the new routes are loaded. Stock search keys (optional): `PEXELS_API_KEY`, `PIXABAY_API_KEY`.

## Motion library (optional)
Set `A2V_MOTION=1` before starting the app to build new compositions with the text-animation and motion-graphics library (variety per scene, keyword emphasis, HUD / frame / map graphics). Off by default; see `docs/motion.md`. `A2V_MOTION_SPEED` (default 1.3; 1 = the preset durations) makes entrances, stagger, graphics and scene changes faster; 30 fps never changes.

## Use Images (Motion-Only mode)
The **Use Images** switch (New Project form, Audio Input card) is per project. OFF skips Asset Collection and Image Generation and makes the video from text animation, shapes, lines and motion graphics only; no image is needed anywhere. Switch it back ON to use images (nothing is deleted).

## Canonical Folders
| Folder | What it holds |
|---|---|
| `SYSTEM/` | Shared system infrastructure, 14 autonomous agents, memory store, registries, policies, approvals |
| `UI/frontend/` | The canonical web UI application (Vite + React + Tailwind + Vitest) |
| `UI/backend/` | FastAPI API routes, schemas, and presentation layer |
| `VIDEO_ENGINE/` | PipelineOrchestrator, 12 pipeline stages, Remotion composition engine, FFmpeg media utilities |
| `projects/<id>/` | Project assets, audio, transcripts, plans, generated motion code, renders |
| `docs/` | Milestone design notes and technical specifications |
| `reports/` | Architectural audits, verification logs, and migration reports |

## Tests
```
$env:PYTHONPATH="."; .venv\Scripts\python.exe -m pytest tests/test_laxman_approval.py tests/test_llm_gateway.py tests/test_llm_usage.py tests/test_skills_and_shared_memory.py tests/test_pipeline_state_and_checkpoint.py tests/test_evaluation_and_self_learning.py tests/test_agent_runtime_and_communication.py tests/test_agent_routes.py tests/test_audio_visual_agents_integration.py tests/test_motion_codegen_and_concurrency.py tests/test_timeline_render_qc_delivery.py tests/test_orchestrator_and_monitoring.py -q
cd UI/frontend && npm test
cd UI/frontend && npm run typecheck
cd VIDEO_ENGINE/remotion && npx tsc --noEmit
```

## Good to know
- A 70 s video renders in about 2-3 minutes as a preview and about 6-11 minutes as a final video on a laptop CPU (5-9x the video length; slower when other programs are open).
- Transcribing needs several GB of free RAM. If it fails with a memory message, close other programs and retry.
- Ports used: 8000 (API), 5173 (UI). A second copy of the app will not start while they are taken.
- `/plan` is a Claude Code step; nothing else in the project calls an AI service.
