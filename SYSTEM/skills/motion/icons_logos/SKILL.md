---
skill_id: motion.icons_logos
name: Icons, Logos & Flags
domain: motion
version: 1.0.0
summary: Professional icons, brand logos and flags as inline SVG.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (@phosphor-icons/react, flag-icons, lucide-react), CC0-1.0 (simple-icons)).
risk_level: low
capabilities:
  - icons
  - logos
  - flags
dependencies:
  - remotion
  - @phosphor-icons/react
  - simple-icons
  - flag-icons
  - lucide-react
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Icons, Logos & Flags

- Icons: `import { Brain, RocketLaunch } from "@phosphor-icons/react"`; `<Brain size={52} weight="duotone" color={...} />` (weights: thin, light, regular, bold, fill, duotone). `lucide-react` is also available.
- Brand logos: `import { siGithub } from "simple-icons"`; draw `<svg viewBox="0 0 24 24"><path d={siGithub.path} fill="#e2e8f0" /></svg>` (brand colour: `"#" + siGithub.hex`). Some brands do not exist (no OpenAI logo): check the name exists, else use a Phosphor icon or text.
- Flags: `flag-icons` SVG files (`flag-icons/flags/4x3/in.svg`), shown with `<Img src={...} />`.
- Style: icon inside a glass chip (96px, radius 26) with a soft glow; entrance `scale 0.6 to 1` + opacity via `spring`, stagger 4 frames per icon.
- Never load icons or fonts over the network (no Iconify API, no CDN).
