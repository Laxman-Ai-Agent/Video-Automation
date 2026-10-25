# Agent Coding Guidelines & Architecture Rules

This repository follows strict modular architecture and testing standards. Refer to [GEMINI.md](./GEMINI.md) and [docs/rules.md](./docs/rules.md) for full guidelines.

## Quick Summary for AI Agents & Developers:
1. **Frontend Styling**: All CSS must use **CSS Modules (`*.module.css`)**. Never write layout, colors, or hover handlers as inline JSX styles.
2. **Dynamic Only in `style`**: Inline styles are strictly reserved for runtime values (pixel width calculations, dynamic SVG offsets).
3. **Never Remove `data-testid`**: All automated tests rely on `data-testid` attributes.
4. **Theme Tokens**: Always use CSS variables (`var(--bg-card)`, `var(--text-primary)`, `var(--accent-blue)`, etc.) from `index.css`.
5. **Always Verify**: Run `npm --prefix UI/frontend run build` to confirm 0 TypeScript / bundle errors before ending any task.
6. **LLM & CLI Subprocess Execution**:
   - When calling CLI engines (`agy.exe`, `claude`), always pass `stdin=subprocess.DEVNULL` to avoid Windows console blocking.
   - Guard shared CLI instances with inter-process mutual exclusion locks (`_interprocess_agy_lock`) so short probes do not tear down active daemon sessions.
   - Never run un-cached health checks while pipeline LLM generations are actively streaming.
   - Use `Gemini 3.8 Flash (Low)` for fast text completion to avoid multi-minute thinking budget delays.
