---
skill_id: motion.real_media
name: Real Photos & Video Clips in Scenes
domain: motion
version: 1.0.0
summary: How to place a collected real photo or clip (element with a real_media object) in a scene, with a mandatory credit caption and honest framing.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - real-media-placement
  - credit-chips
  - honest-framing
dependencies:
  - remotion
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Real Photos & Video Clips in Scenes

An element with a `real_media` object is a REAL photograph or video clip that Asset Collection found, checked and licensed. The file is already prepared (clips are trimmed, scaled to the canvas, 30 fps, no sound). Draw it; never recreate it.

## Drawing it
- Photo: `import { Img, staticFile } from "remotion"` then `<Img src={staticFile(real_media.file)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />`.
- Clip: `<OffthreadVideo src={staticFile(real_media.file)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />`. If the scene is longer than the clip (`real_media.duration_s`), wrap it in `<Loop durationInFrames={Math.round(real_media.duration_s * 30)}>` from remotion.
- Use exactly the path in `real_media.file`; never `<img>`, `<video>`, fetch, canvas or a path you invented. Put the element's `data-element-id` on the node that holds the media.

## Framing (pick one per scene, one real-media hero per scene)
- Hero: full-bleed behind everything, with a dark gradient scrim (top 0.75 to 0 opacity) so the headline stays readable.
- Card: a rounded (28px) frame with a 1px light border and a soft shadow, next to the text or a chart, when the scene also carries data.
- Keep the main subject visible: `objectPosition: "50% 40%"`; never crop it out.

## Captured page (`real_media.kind` is "page")
A screenshot of one element (infobox or table) of a reference page. Always a framed card (`objectFit: "contain"`, never cropped, never full-bleed, at most 70% of the width) on the dark background so its small text stays readable; the credit names the page ("Title, Wikipedia contributors, CC BY-SA 4.0").

## Motion (frame-driven only)
- Photo: a slow push-in with `interpolate(frame, [0, durationInFrames], [1, 1.06])` on `scale`. Clip: at most 1.03, the clip already moves.
- Enter with a 10 to 14 frame fade (and a 1.04 to 1 settle); exit with a short fade. No blur, no hue or sepia filters, no speed changes.

## Credit (mandatory)
Show `real_media.credit` in a small chip near the bottom edge, bottom-left: `fontSize` 20 or more, `rgba(0,0,0,0.45)` background, `padding: "6px 12px"`, `borderRadius: 10`, light text. It appears with the media and stays until the media leaves. It must not overlap the headline.

## Honesty
The media is evidence. Do not recolour it, do not draw generated graphics that look like part of the photograph, and label any annotation (arrow, circle, caption) as an obvious vector overlay on top. Never say or imply the media is generated or a reconstruction.
