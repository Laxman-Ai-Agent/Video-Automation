# Project Rules & Development Guidelines

This document defines the core architecture and development rules for this repository. Every developer and AI agent must adhere strictly to these standards to ensure long-term stability, rapid debugging, and zero regression.

---

## 1. Frontend UI & Styling Rules (CSS Modules)

### A. Mandatory CSS Modules (`*.module.css`)
- **No Inline Style Dumping**: Never write massive inline `style={{ ... }}` objects for layout (flex, grid, padding, margin, width, height), borders, box-shadows, typography, or transitions.
- **Companion File Pattern**: Every React component in `UI/frontend/src/` with styling must be accompanied by its scoped CSS file:
  ```
  src/components/
  ├── MyComponent.tsx
  └── MyComponent.module.css
  ```
- **Scoped Styles**: Use CSS classes defined in `MyComponent.module.css` and import them as:
  ```tsx
  import styles from './MyComponent.module.css';
  ```

### B. Dynamic Styles in `style={{ ... }}` Only
- Inline `style` is strictly limited to **runtime dynamic values** calculated from React state or props:
  - Percentage offsets for SVG circular progress rings (`strokeDashoffset`)
  - Dynamic container widths driven by collapse state (e.g., `width: collapsed ? '72px' : '230px'`)
  - Dynamic status colors derived from backend status mappings when a generic CSS class is insufficient.
- All static layout, transitions, font sizes, borders, and paddings must live in `.module.css`.

### C. No Direct DOM Style Mutation in Event Handlers
- **Prohibited**:
  ```tsx
  // ❌ NEVER DO THIS:
  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-elevated)'; }}
  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
  ```
- **Required**: Use native CSS pseudo-classes (`:hover`, `:active`, `:focus`) and state modifier classes (`.navButtonActive`) in the `.module.css` file:
  ```css
  /* ✅ ALWAYS DO THIS in MyComponent.module.css: */
  .button:hover {
    background-color: var(--bg-elevated);
  }
  .button.active {
    background-color: #1890FF;
    color: #FFFFFF;
  }
  ```

### D. Design System & CSS Variables
- Always use the semantic theme tokens defined in `UI/frontend/src/index.css`:
  - Backgrounds: `var(--bg-card)`, `var(--bg-elevated)`, `var(--sidebar-bg)`, `var(--header-bg)`
  - Text: `var(--text-primary)`, `var(--text-secondary)`, `var(--text-muted)`
  - Accents: `var(--accent-blue)`, `var(--accent-cyan)`, `var(--accent-red)`
  - Status: `var(--status-running)`, `var(--status-completed)`, `var(--status-failed)`, `var(--status-retrying)`, `var(--status-blocked)`
- Do not introduce raw hardcoded hex codes (`#1f2937`, `#000000`) for standard theme-aware elements.

---

## 2. Test Integrity & Selector Preservation (`data-testid`)

- **Never remove, rename, or omit `data-testid` attributes** during refactoring.
- Automated Playwright and pytest suites rely directly on these attributes:
  - `data-testid="stage-card-{id}"`
  - `data-testid="stage-status-{id}"`
  - `data-testid="stage-run-btn-{id}"`
  - `data-testid="stage-stop-btn-{id}"`
  - `data-testid="sidebar-nav-{id}"`
  - `data-testid="stage-nav-tab-{id}"`
- When adding new interactive features (buttons, modal triggers, status pills, tabs), always add an intuitive, kebab-case `data-testid`.

---

## 3. Component Architecture & Code Cleanliness

- **Target Component Size**: Keep components focused. Target < 250 lines; hard ceiling at 450 lines. Extract sub-views, drawers, or child cards when complexity grows.
- **Strict TypeScript**:
  - Maintain type declarations in `src/types/pipeline.ts`.
  - Do not use `any` when formal pipeline or stage types exist.
  - Keep CSS module type support active in `src/vite-env.d.ts`.
- **Preserve Performance Optimizations**:
  - Retain `React.memo` and custom comparator functions on high-frequency rendering components like `StageCard`.
  - Avoid creating anonymous inline objects or handler functions inside tight render loops when memoization is active.

---

## 4. Mandatory Verification Gate

Before committing changes or concluding any task:
1. **Frontend Compilation**: Run `npm --prefix UI/frontend run build` (`tsc && vite build`).
   - Must complete with **0 TypeScript errors** and **0 build warnings/errors**.
2. **Automated Testing**: Run Playwright end-to-end tests to ensure navigation, layout spacing, drawer toggles, and status updates function without visual regression.

---

## 5. Superpowers Engineering Discipline (`.agents/skills`)

This project integrates the `obra/superpowers` agentic framework. When designing, implementing, or debugging features, adhere to the core skills located in `.agents/skills/`:
1. **Systematic Debugging (`systematic-debugging`)**:
   - Always find the root cause before attempting fixes.
   - Formulate a testable hypothesis and create a reproducible test or probe.
   - Never apply random speculative changes or multi-component trial-and-error edits.
2. **Atomic Planning & Execution (`writing-plans`, `executing-plans`)**:
   - For any non-trivial change (> 50 lines or across multiple files), write a structured, step-by-step plan.
   - Execute step-by-step with clear verification gates at each milestone.
3. **Test-Driven Development (`test-driven-development`)**:
   - Write failing automated tests (Playwright or pytest) before implementing new stage logic or UI components.
   - Verify that tests fail for the right reason, then implement minimal clean code to make them pass.
4. **Verification Before Completion (`verification-before-completion`)**:
   - Never claim a task is completed based on assumption. Verify evidence (build logs, test outputs, screenshots) before concluding.

