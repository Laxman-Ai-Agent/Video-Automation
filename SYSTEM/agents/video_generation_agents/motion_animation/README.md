# Motion Animation Agent (v2.0.0)

- **Agent ID:** `motion_animation`
- **Stage ID:** `motion_gen`
- **Version:** `2.0.0`
- **Primary Class:** `MotionAnimationAgent` (alias `MotionAnimationAdapter`)

## Purpose
Autonomous LLM synthesis and bounded repair of executable React/TSX animation code using Remotion primitives, featuring graceful 3D fallback approximation, retry storm prevention, lightweight visual verification, and structured diagnostics.

## Capabilities
- `motion-codegen`: Remotion-native React/TSX synthesis.
- `remotion-primitive-synthesis`: Frame-driven springs, interpolation, and inline SVG visual elements.
- `ast-validation`: Static security and prohibited preset scanning.
- `3d-graceful-fallback`: Automatic detection of complex/unsupported 3D cues and element-level approximation into 2D particle drift, 2.5D isometric SVGs, or structured skipping.
- `retry-prevention`: Capability limitation cache preventing repetitive LLM repair calls on uninstalled 3D runtimes.
- `visual-preview-verification`: Lightweight static layout, safe-area margin, typography, and contrast checks.
- `structured-generation-reporting`: Emits `motion_generation_report.json` with per-element statuses and downstream readiness metrics.
- `autonomous-memory-learning`: Automatic experience recording and self-learning in private memory.

## Bound Tools
- `llm_client`
- `llm_gateway` (model profile: `code_generation`)
- `ast_parser`
- `threed_fallback_engine`
- `visual_preview_verifier`
- `structured_generation_reporter`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
Outputs `composition.json`, `motion_animation.json`, `motion_generation_report.json`, and isolated scene components under `projects/<pid>/generated_motion/scene_*.tsx`.
Protected by mutex staging locks during TypeScript compilation checks.
