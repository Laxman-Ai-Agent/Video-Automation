# Rules (code, tokens, quality)

## Token saving (most important)
1. Read only CLAUDE.md + the current `docs/mX.md` + files named in the task.
2. Never open: .env, node_modules, .venv, models, assets, out.mp4, big logs, full transcript unless planning.
3. Claude never views images. Use code tools.
4. One milestone per session. Finish, test, commit, update STATUS.json, then tell the user to `/clear`.
5. Edit with small diffs. Do not rewrite whole files or whole JSON for small changes.
6. Show test output trimmed: errors and last 10 lines only. Use `tail`, `head`, `--quiet` flags.
7. Do not re-explain the plan. Reply short: what changed, test result, next step.
8. Ask before installing anything or when a decision is unclear. One question at a time.

## Model switching
| Work | Model |
|------|-------|
| architecture, M1, M2, /plan prompt design | Opus |
| normal coding M0, M3-M8 | Sonnet |
| STATUS update, rename, formatting, tiny fix | Haiku |
At a phase change say: "Switch to <model> with /model". The user switches; you cannot.

## Markdown files
- Each .md: 80-120 lines target, 200 hard max. Longer -> split.
- Docs describe the contract; code comments stay minimal.

## Code style
- Python 3.12, type hints, pydantic models for all JSON. One file = one job, under ~200 lines.
- TypeScript strict. Remotion components are pure functions of (frame, props).
- Paths via `pathlib` (Windows). No hard-coded absolute paths; read `PROJECT_ROOT` from config.
- Set model cache env vars in `backend/config.py` before importing torch/whisper/rembg.
- Config values (thresholds, fps, sizes) live in `backend/config.py` and `VIDEO_ENGINE/remotion/src/config.ts`.
- Log to `projects/{id}/log.txt`; never print secrets.

## Frontend UI & Styling Rules (CSS Modules)
- **Mandatory CSS Modules (`*.module.css`)**: Never dump layout, positioning, typography, borders, shadows, or pseudo-classes into inline `style={{ ... }}` objects. Every component must use a companion `[ComponentName].module.css` file.
- **Dynamic Styles Only in `style`**: Inline styles are strictly reserved for runtime dynamic values (e.g. state-driven dimensions, `strokeDashoffset`, dynamic percentage numbers).
- **No Direct DOM Style Mutation**: Never write `onMouseEnter={(e) => e.currentTarget.style.backgroundColor = ...}`. Use CSS `:hover`, `:active`, `:focus`, and active classes (`.navItemActive`) in the module CSS.
- **Theme Variables**: Use design tokens from `index.css` (`var(--bg-card)`, `var(--text-primary)`, `var(--accent-blue)`, `var(--status-running)`, etc.). Avoid raw hardcoded hex codes.
- **Testing Integrity (`data-testid`)**: Every interactive button, card, tab, and status indicator must maintain its `data-testid` attribute. Never remove or rename existing test IDs during refactoring.
- **Verification Gate**: Any UI change must compile cleanly with `npm --prefix UI/frontend run build` and pass all Playwright automated regression tests.

## Remotion rules
- Animate only with `interpolate()`, `spring()`, or GSAP paused timeline + `seek(frame/fps)`.
- No CSS transitions, no setTimeout, no Framer Motion, no random without a seeded value.
- Use `<Sequence>` per scene; layer `enter`/`exit` times relative to the scene start.
- Images via `<Img>` / `staticFile`; videos via `<OffthreadVideo>`.
- Fonts via `@remotion/google-fonts` (Noto Sans Telugu for subtitles, a clean sans for English).
- Respect safe margins (5%). No text over busy areas without a dark scrim.

## Visual quality rules
- Motion supports narration: change visuals on meaning/word timestamps, not on a timer.
- Max 1-2 text elements per scene; some scenes have no text at all.
- Max 3-5 image layers in a frame. Use depth: slow parallax, soft shadow, vignette, grain.
- Camera moves are slow (1.0 -> 1.12 over a scene). Never jitter.
- Transitions: never the same type twice in a row; match the mood (light-leak for warm, blur for soft).
- Keep one palette and one type scale for the whole video (from `scene_plan.style`).
- Particles and effects only at emphasis moments.

## LLM & CLI Subprocess Execution
- Always pass `stdin=subprocess.DEVNULL` when executing CLI tools (`agy.exe`, `claude`) to prevent Windows console input blocking.
- Guard shared CLI instances with inter-process mutual exclusion locks (`_interprocess_agy_lock`) so short probes do not tear down active daemon sessions.
- Never run un-cached health checks while pipeline LLM generations are actively streaming.
- Use `Gemini 3.8 Flash (Low)` for fast text completion to avoid multi-minute thinking budget delays.

## Safety
- Do not delete files without asking. Do not touch outside the project folder.
- Do not read or print `.env`. Pexels key is read from env at runtime only.
- Pexels clips: save credits to `credits.json`, offer them for the YouTube description.
- Lottie files only if the user provides them (license check is the user's job).

## Testing
- Each task ends with a runnable command and an expected result (see the milestone doc).
- Keep a tiny fixture set in `tests/fixtures/` (10-20s audio, 6 test images, sample JSON).
- Run `tsc --noEmit` and `pytest -q` before commit.
