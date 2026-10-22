---
skill_id: motion.design_kit
name: Professional Design Kit (palette, glass, gradients, depth)
domain: motion
version: 1.0.0
summary: Premium look: dark gradient background, glass cards, gradient text, soft glow, one accent pair per video.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (@radix-ui/colors, culori)).
risk_level: low
capabilities:
  - palette
  - glassmorphism
  - gradients
  - depth
dependencies:
  - remotion
  - @radix-ui/colors
  - culori
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Professional Design Kit

## Palette
`import { slateDark, violetDark, cyanDark, amberDark } from "@radix-ui/colors"`. Pick ONE accent pair per video (e.g. cyan + violet) and an optional warm highlight (amber). Background: `slateDark.slate1` with two large radial gradients (`violetDark.violet4`, `cyanDark.cyan4`) at opposite corners.

## Surfaces
- Glass card: `background: linear-gradient(145deg, rgba(255,255,255,0.10), rgba(255,255,255,0.03))`, `border: 1px solid rgba(255,255,255,0.14)`, `borderRadius: 28`, `boxShadow: 0 30px 80px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.18)`.
- Subtle grid: 80px lines at 5% white, opacity 0.35. Glow: `filter: drop-shadow(0 0 18px <accent>66)`.
- Gradient text: `linear-gradient(90deg, #fff, <violet11>)` with `WebkitBackgroundClip: "text"` and `color: "transparent"`.

## Variety (avoid the same look in every video)
- One hero per scene: a single element (a big number, the chart, one word) carries the scene; everything else is quiet and smaller.
- No identical card grids: sizes and radii follow importance, not one radius and one shadow for everything.
- Let the subject pick the mood (finance, health, tech, history): choose the accent pair and background from it, not always dark + cyan.
- Number markers (01, 02, 03) only when the content really is a sequence.

## Do not use (slow on this CPU)
canvas, WebGL, shaders, `backdrop-filter`, SVG `feTurbulence`/heavy blur filters over large areas, 3D transforms with perspective on many layers.

## Motion
Everything enters with `spring` + short stagger (see motion.remotion_spring_curves); exits are 8 to 12 frames. One idea per scene, generous spacing.
