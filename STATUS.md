# STATUS

Live progress is stored in `STATUS.json` (single source of truth) and shown by `dashboard/`.

## Rules for Claude Code
- After every finished task run: `python scripts/update_status.py "<task name>" done`
  (create the script in M0; until then edit the single task's `done` flag only).
- Never rewrite the whole file. Never mark a task done before its test passes.
- Task names must match STATUS.json exactly.

## How the user views it
```
python scripts/sync_status.py --watch
cd dashboard && npm run dev
```
Open the printed localhost URL. The page refreshes every 5 seconds.

## Milestones
| ID | Name | Model |
|----|------|-------|
| M0 | STATUS + dashboard | Sonnet |
| M1 | Remotion base | Opus |
| M2 | Component library | Opus |
| M3 | Whisper | Haiku/Sonnet |
| M4 | Planning | Opus/Sonnet |
| M5 | Matching | Sonnet |
| M6 | End-to-end CLI | Sonnet |
| M7 | FastAPI | Sonnet |
| M8 | Main UI | Sonnet |
| M9 | Polish | Sonnet/Haiku |

Each milestone: read `docs/mX.md`, finish, test, update status, `git commit`, `/clear`.

## Dashboard
Terminal A: `python scripts/sync_status.py --watch`
Terminal B: `cd dashboard && npm run dev` (http://localhost:5174)
Or just run `start.bat`: it starts the sync, the dashboard, the API and the UI together.
Tick a task: `python scripts/update_status.py "<task name>" done`

## Review workflow (analysis -> prompts -> images/crops -> timeline) - implemented, committed
Approved by the user: a minimal extension of the M7 API (the 12 original paths and their schemas are unchanged; 10 new paths, snapshot + contract test
updated). Prompts are written by backend/promptgen.py with the user's signed-in Claude CLI (`claude -p`, no tools, no API key, no new provider): approving the
analysis starts it, Regenerate rewrites one prompt, POST /prompts/generate is the retry; /review has a `generation` state. The scene plan itself is written by backend/autoplan.py (translation, plan, checks; built in a temp folder and published only when it passed) right after transcription + cut points, or by POST /prompts/generate when a project was already waiting; /plan stays as the manual recovery. Audit: scene table, approvals,
prompt edit/regenerate, crops and "run without render" were MISSING; upload, matching, review, progress panel, validation were reused.
- Backend: backend/review.py (scene table, prompt items, edits + history, approvals as fingerprints, crops, timeline state), routes/review.py (GET review,
  PUT prompts/{n}, POST prompts/approve, POST prompts/{n}/regenerate, PUT crops/{n}, POST approve, POST run {match|timeline|preview|final, aspect},
  GET video, GET assets/{name}), review.json + crops.json in the project, pipeline chains match / timeline / timeline-9x16 (steps validate, validate-9x16),
  backend/prompt_review.py + .claude/commands/regen.md (the manual regeneration of ONE prompt), fill_slots writes the saved crop (crop + zoom) into the composition.
- An approval is a fingerprint: editing a prompt, replacing an image or moving a crop makes the gates above it stale by themselves; /plan keeps user edits
  (reapply_edits); an accepted image match stays with its prompt when matching runs again (only an image numbered for that prompt replaces it).
- Renderer: ImageLayer applies crop + zoom (same geometry as lib/crop.ts); a real Remotion still with a saved crop correlates 0.92 with the expected window.
- UI: Analysis table, checkpoint bar, prompt cards (edit, save, regenerate request, approve, approve all, history), crop editor (9:16 main, drag, zoom,
  before/after, warnings, apply/reset), Match images without a render, Approve Images & Crops, Timeline screen (Continue to Timeline, warnings, Preview, Render with confirmation).
Tests: pytest 180, vitest 265, tsc 0, oxlint 0, build ok. Browser smoke on a scratch project: whole flow, no console errors, no horizontal scroll at 375 px.
Limits: scene rows are read-only (change them by running /plan); /regen <id> <n> in Claude Code still works as a manual fallback (about $0.007 per CLI call);
thumbnails only for this session's uploads, the crop editor loads the picture from the new assets endpoint; the pre-render check cannot see the subject.
The running servers must be restarted to load the new API (runproject.bat). P6 pre-render validation and the P1-P5 UI are committed (dba9616, e812af3, 339a976).

## FINAL STATUS for real-time use (freeze point, HEAD 68c0e25)
Nothing below was re-run for this note; numbers are from the last runs recorded in this file and in the commits.
Done and committed: M0-M7 (done), M8 10/11, M9 9/14 + the optional 9:16 export. Last tests: pytest 120 passed, Remotion tsc 0
(frontend untouched since its last green run: tsc 0, oxlint 0, vitest 179/179, build ok).
Commits of this stretch: 92ebcef (M8), c592708 (M8 status), c90784e (M9 phase 1), a784758 (packaging), 385ccc0 (typography,
palette), 451f5c3 (camera, accents, effect rules), 05e2313 (9:16 export), ef173fa (9:16 names empty scenes), 68c0e25 (demo slots).
Deferred or blocked (reason in the M9 section): Parallax (large model), Music ducking (no music), Pexels (no key), Lottie (no files),
Export extras (thumbnail picker needs a new API endpoint, credits need Pexels). The 9:16 part of Export extras is DONE (CLI only).
Waiting for the user (nothing here can be proven by tests):
- Visual review of the 16:9 polish and of out_9x16.mp4 (yes/no + 3 weakest scenes). Then tick M6 "Quality review checklist".
- M8 "Full UI run": one new audio to final video through the UI.
- The demo outputs of 16:9 are STALE: out.mp4 (Oct 8) and out_preview.mp4 were rendered before prompts 4, 9, 13 got images.
  composition.json is filled (14/14); run build (or the UI) once to refresh them. The 9:16 files are current.
- Prompt 9's picture is 16:9, blurry and has no plain white background; it was matched by hand (fix demo <file> 9).
- Render time: not re-measured on an idle machine. A-B-A-B preview test of the pre-M9 code vs now (concurrency 3, 2 timed runs each):
  182.3 s vs 177.1 s, no reproducible slowdown. Under load: 16:9 final 651 s (9.3x), 9:16 final 432 s (6.2x); 341 s (4.9x) at baseline.
- requirements.txt was never installed into a fresh venv (several GB); the pins match the running environment.
Frozen modules: M7 API (backend/routes, main.py) and frontend/ have NO changes since their commits. M1-M6 were changed in M9 with
the user's approval: render.py, pipeline.py, fill_slots.py, focus.py, cli.py, audio_utils.py/transcribe.py (silent audio), the Remotion
components and patterns, build_composition.ts, dashboard port 5174, and the step list asserted in tests/test_m6.py.
Practical use: no blocker found. Things to know: /plan runs in Claude Code per project; Whisper needs several GB of free RAM;
fonts are fetched from Google Fonts at render time (needs internet); 9:16 has no UI option (CLI: build <id> --aspect 9:16).
Working tree (untouched, never committed): projects/_m5check, projects/_m5final, projects/demo/prompts_missing.txt,
testing_audio_files/IMAGES, plus generated projects/demo/composition_9x16.json and render_profile_9x16.json (not committed yet).

## M8 (Main UI) - implementation done, 10/11 (commit 92ebcef)
`frontend/` (Vite + React 19 + TS) uses only the frozen M7 API. Checks at the commit: tsc 0, build 0, oxlint 0,
vitest 179/179, pytest 37. Real-browser smoke (scratch copy of demo, M7 + Vite): upload, refresh, review fixes,
preview render, result playback, download (byte-exact) and cancel all worked.
The schema derives a milestone's status from its task flags, so M8 shows "doing" until the last task is ticked.
The only open task is "Full UI run": a complete new-audio-to-final-video workflow (upload audio, transcribe,
/plan in Claude Code, prompts, images, match, preview, final 1080p render, download) has NOT been verified end to end.
Verified so far: the demo project from the images step onward (preview render only), and Whisper started from the UI
(cancelled at 89%). Tick it only after one complete run, including a final render started from the UI.
Limitations of two ticked tasks (approved deviations from docs/m8.md; they are not built as written):
- "Remotion Player preview": replaced by the backend preview render (out_preview.mp4) played in a `<video>`.
- "Subtitles toggle": not implemented (needs a backend field); no transcript editor or scene list either.

## M9 (Polish) - progress
M9 = doing, 9/14 (done: tasks 1, 2, 3, 4, 6, 8, 11, 12, 13). Order followed: Phase 1, Phase 3 (packaging), Phase 2a (typography + color),
Phase 2b/2c (camera, word accents, effect rules).
Phase 2b/2c done ("Camera polish", "Word accents", "Particles tuning"): camera.ts has one easing per kind of move (the old single
curve spent most of a zoom in the first fifth of the scene: peak speed 4.5x the average, now 1.6-1.7x, zoom-to-focus 2.3x);
optional seeded handheld drift (off by default, max 0.3% / 0.15 deg); `fill` now converts a photo's focus point to FRAME
coordinates (before, a 1:1 photo with its subject at y=0.40 aimed the zoom 84 px too high; boxes shared via theme.json);
accent.ts pulses (x1.045) at highlight end, at later keywords (build_composition writes `pulses`) and when a counter lands;
backend/motion_checks.py (in plan_checks) flags zoom > 1.15, focus near the edge, effects not near a keyword or an entering
element, more than 2 effects per scene, particles over 60, accents longer than 4 s (the demo's 5.8 s glow is flagged).
Particles tuning is rule/check based: the component already capped particles at 60, nothing in the look changed.
Verified by numbers (tests run the real TypeScript). NOT visually approved.
Render time: the added work is about 0.4 us per frame (about 1 ms per video) and scenes without the new features produce the
same DOM as before. Wall-clock timing on this laptop is too noisy to prove 10% right now: the SAME code took 133.7 s and 194.1 s
in an A-B-A-B test (A = committed code 133.7/194.1, B = with 2b 175.5/170.8); earlier 2a runs were 118-126 s. Re-measure
when the machine is idle; the 1080p final was not re-timed after Phase 2.
Phase 2a done ("Typography", "Color grade"): VIDEO_ENGINE/remotion/src/theme.json is the one source for the type scale, 5% safe margin,
scrim and default palette; palette roles are derived from the colors (plans list [dark, teal, amber], docs showed
[dark, amber, teal]); fill copies style.palette/grade into composition.meta; backend/palette.py warns about colors outside
the palette and weak contrast; the optional grade is a cheap blend overlay (off by default).
Verified by numbers only (tests/test_m9.py runs the real TypeScript): scale is a ladder, scrim gives 3:1 on a white photo,
text is fitted into the safe width, components contain no literal sizes or accent colors, build_composition no longer makes
the old dark-to-amber background. NOT visually approved: sizes moved at most +12% (label 50 to 56, subtitles 52 to 56,
display 150 to 144, hero 220 to 224) and big text on photos now has a dark band; the user must review a preview.
Render time (preview, 70 s demo, concurrency 3): 118-126 s vs the 114.6 s baseline (+3% to +10%).
Phase 3 (packaging) done: "Packaging and start.bat" - requirements.txt (pinned, checked against the imports and the
installed versions by tests), README.md, root package.json, start.bat (sync + dashboard on 5174 + runproject.bat).
A fresh-venv install was NOT run (it would download several GB); the pins equal the versions this project runs with.

9:16 export (optional, part of "Export extras"; the rest of that task stays blocked): `--aspect 9:16` builds composition_9x16.json
and out_9x16.mp4 from the same plan and images; 16:9 is unchanged (composition built from the sample plan is byte-identical, golden
hash in tests/test_m9_portrait.py). Verified by numbers: pytest 117 passed, Remotion tsc 0, layers inside the frame and above the
bottom 16%. A real 70 s preview rendered (540x960, 30 fps, audio kept, 217 s = 3.1x on a busy laptop; the 16:9 preview took 172-219 s in the
same session). NOT visually approved: wide photos are cropped to their focus point; no UI toggle (needs an API field); the final 1080x1920
render was not run.

## M9 Phase 1 - done
Done: "Transition audit", "Error handling pass", "Performance pass". Tests: tests/test_m9.py, pytest total 76 then.
- Transition audit: `python -m backend.transition_audit <id>`; mood table shared via VIDEO_ENGINE/remotion/src/transitions/by_mood.json.
- Error handling: backend/diagnose.py gives plain-language messages (memory, disk, locked file, damaged JSON, fonts,
  ffmpeg); silent audio stops before Whisper loads; corrupt/missing images are named by ingest, gate and render preflight.
- Performance: every render writes render_profile.json (cost per scene). Measured on the demo (70 s video):
  preview 105-130 s (1.5-1.8x video length), final 1080p 341 s (4.9x). No scene is heavy (0.14-0.18 s/frame at 1080p),
  so there is nothing to cap. Render concurrency stays 3 (4 was only ~5-8% faster and needs more RAM); no quality
  settings were changed.
Blocked or deferred (5 tasks, none started):
- "Parallax upgrade (optional)": needs a Depth Anything model download (large) and render time is already ~5x the video length.
- "Music ducking": needs a music file from the user.
- "Pexels stock": needs a Pexels API key in the environment (PEXELS_API_KEY); .env is never read.
- "Lottie (optional)": needs Lottie files from the user.
- "Export extras": the thumbnail picker needs a new API endpoint (not allowed without approval), credits text depends on
  Pexels, and a 9:16 variant must be asked first.
All visual work (type scale, scrim, grade, camera, accents) still needs the user's preview review: render a preview, fill in
the M6 yes/no checklist and name the 3 weakest scenes.

## Open items (reviewed at the freeze; entries marked RESOLVED are kept for history)
- M6 "Quality review checklist" stays open (M6 = 7/8): needs the user visual yes/no on the final video.
- RESOLVED: the 3 demo slots s03_0 (prompt 4), s07_0 (prompt 9), s08_3 (prompt 13) got images (inbox -> match -> 14/14, commit 68c0e25).
  The 16:9 video files of the demo still have to be re-rendered to show them.
- Audio validation with ffprobe at project creation is not implemented (only the file extension is checked).
- Cancel (POST /projects/{id}/cancel) takes effect between steps; an already-running render is not interrupted.
- pipeline.py is ~420 lines (rules.md asks for about 200): the split planned for M9 was NOT done (no feature needed it).
- M8 "Full UI run" stays open (M8 = 10/11): needs one complete new-audio run to a final video from the UI.
- UI: the uploaded-image count only covers the current browser session (M7 has no endpoint listing server images),
  and optional prompts are unknown to the UI, so missing images always need the "skip" box. Fix needs an M7 change.
- UI: the Render screen cannot tell that a video is older than later image fixes (no API signal); it shows a hint.
- Ops: Whisper large-v3 failed twice with "mkl_malloc" when only ~4 GB RAM was free; close other programs first.
- Ops (resolved in M9 Phase 3): the dashboard moved to port 5174 so it can run next to the UI on 5173.
- The unused Vite template files were moved out of frontend/ (not deleted) to the session scratchpad.
- Final 1080p render takes 4.9x (baseline) to 9.3x (busy machine) the video length on this machine (docs/m9.md asks to tell the user above ~3x). The cost
  is spread evenly over the scenes, so it is pixel-bound; accepted for now, no settings changed.
- Fonts are downloaded from Google Fonts at render time: offline, the render fails; the error is explained, not pre-checked.
