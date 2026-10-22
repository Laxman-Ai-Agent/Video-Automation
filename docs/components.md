# Remotion Components & Composition Patterns

Planner (Claude) picks a `pattern` per scene and fills parameters. It never writes component code.
Components live in `VIDEO_ENGINE/remotion/src/components/`; each reads props from composition.json layers.

## Core components
| Component | Purpose | Key props |
|-----------|---------|-----------|
| `SceneRoot` | wraps a scene: camera + layers + transition | scene object |
| `Camera` | push-in, pull-out, pan, zoom-to-focus | move, from, to, focus |
| `ImageLayer` | image with Ken Burns, parallax, mask reveal | file, anim, parallax, pos |
| `IconPop` | Lucide icon with spring pop / stroke draw | lucide, pos, enter |
| `Effect` | sparkle, burst, glow, checkmark, particles (SVG) | name, at, pos |
| `HighlightText` | big typography, word highlight, underline | text, style, at |
| `Caption` | animated lower-third / label | text, at |
| `Subtitles` | Telugu word-highlight captions (toggle) | words[] |
| `Counter` | number count-up with unit | from, to, unit, dur |
| `Chart` | bar / line / pie animated (d3-scale/shape) | kind, data |
| `MapLayer` | SVG map (d3-geo), highlight regions, draw route | region, highlight, route |
| `Callout` | arrow, circle, box, underline, line draw | kind, target |
| `ShapeAnim` | line/rect/circle draw, mask shapes | kind, from, to |
| `StockVideo` | looping background clip with opacity | file, opacity |
| `Background` | gradient / noise backgrounds | colors |
| `FilmLook` | grain + vignette + light leak overlay | amount |
| `Transition` | wrapper for scene exits | type, dur |

## Transitions
Built in (`@remotion/transitions`): fade, slide, wipe, flip, clock-wipe.
Custom (build in M2): `zoom-through`, `light-leak`, `blur`, `particle`, `mask-shape`, `match-move`.
Planner rule: never repeat the previous scene's transition; choose by mood.

## Composition patterns (planner picks one name)
| Pattern | Layers | Use when |
|---------|--------|----------|
| `hero_only` | 1 full image + camera move | single strong visual |
| `hero_text` | hero + big highlight text | key phrase or name |
| `hero_icon` | hero + icon pop | concept symbol |
| `hero_map_icon` | hero + map slide-in + icon | place + importance |
| `split_two` | two images left/right + divider line | comparison |
| `triple_stack` | main + 2 supporting at different depth | rich scene, 3 images |
| `grid_four` | 4 images in animated grid | list of examples |
| `collage_five` | 5 images layered with parallax | montage / many things |
| `stat_counter` | background + counter + chart | a number is the story |
| `chart_focus` | chart + label + callout | data comparison |
| `map_route` | map + route draw + pins | journey / geography |
| `timeline` | line draw + dated nodes + small images | history / steps |
| `quote_type` | gradient + large typography | quote, definition |
| `object_float` | cutout object over gradient + glow | single product/object |
| `stock_overlay` | stock video + text/icon | atmosphere, B-roll |
| `before_after` | wipe reveal between two images | change over time |

Each pattern defines default positions and timings; planner overrides `at` and `text` only.
Pattern code lives in `VIDEO_ENGINE/remotion/src/patterns/<name>.tsx` and outputs a layers array.

## Positions
Presets: full, left-third, right-third, center, top-left, top-right, bottom-left, bottom-right.
Custom `[x,y]` in px on the 1920x1080 canvas. Safe margin 5%.

## Image handling
- Hero images are 16:9 and larger than the frame to allow pan/zoom (scale 1.1-1.2 headroom).
- `focus` = [0..1, 0..1] from OpenCV saliency; Camera zooms toward it.
- Icons/objects use cutouts (PNG with alpha) from rembg.
- Parallax: layers move at different speeds (z-based factor 0.1-0.4); no depth map in v1.

## Style tokens (from scene_plan.style)
One theme per video, in `VIDEO_ENGINE/remotion/src/theme.json` (read by `theme.ts` and by `backend/palette.py`).
- Palette roles come from the colors, not their order: base = darkest, accent = brightest of the rest, secondary = the other.
  `fill` copies `scene_plan.style.palette` (and optional `grade`: warm | cool | teal-orange) into `composition.meta`.
- Type scale (px at 1080p): map 34, chart 44, body 56 (caption, label, lower-third, subtitles), unit 90, display 144, hero 224.
- Safe margin 5%. Long headlines shrink to 70% to fit, then wrap. Text on a photo gets a 0.45 dark scrim (3:1 contrast on white).
- `python -m backend.palette <id>` lists colors outside the palette and weak contrast; `plan_checks` includes it.
- Camera (`camera.ts`, pure functions): easing per move kind (push/pull, pan, zoom-to-focus) from theme.json, slow and even.
  Optional `camera.drift` 0..1 = seeded handheld sway (max 0.3% shift, 0.15 deg), off by default. `fill` converts the photo's
  focus point to FRAME coordinates (`backend/focus.py frame_focus`, same `boxes` table as ImageLayer) before the zoom aims at it.
- Accents (`accent.ts`): a small pulse (x1.045) when a highlight finishes, at the scene's later keywords (`pulses`, set by
  build_composition) and when a counter lands. `pulse: false` turns it off per layer.
- `python -m backend.motion_checks <id>`: zoom limits, focus away from the edge, effects only near a keyword or an entering
  element, at most 2 per scene, particles capped at 60; `plan_checks` includes it.

## 9:16 export (optional; 16:9 is the default and its output is byte-identical)
- `python -m backend.cli build <id> --aspect 9:16 [--preview]` -> `composition_9x16.json` (1080x1920) -> `out_9x16.mp4` (`out_preview_9x16.mp4`, 540x960).
  Same scene plan, same images, same audio; the `fill-9x16` step runs `build_composition.ts --aspect 9:16` and fills the slots.
- Frame-dependent values come from `layoutFor(w, h)` in theme.ts: portrait has its own box table (theme.json `portrait.boxes`;
  left/right-half = top/bottom half), type scale x0.85, captions above the bottom 18-20% (phone apps cover it).
- Patterns with pixel positions have a tall branch (`tall(p)`): split_two divides horizontally, timeline runs vertically, grid_four is 4 rows.
- A wide photo is cropped, not squeezed: fill writes `crop` = the photo's focus point (ImageLayer sets object-position to it) and
  aims the camera at it (`frame_focus(..., crop=True)`). A 16:9 photo shows about 32% of its width. New 9:16 prompts would look better.
- Not covered: motion_checks/palette checks on the 9:16 file, a UI toggle (needs an API field), subtitles are off as always.

## Adding a component (checklist)
1. Props typed with zod; defaults provided.
2. Pure function of `useCurrentFrame()`; test in Remotion Studio with sample JSON.
3. Add to `registry.ts` so composition.json `type` resolves to it.
4. Add one example to `tests/fixtures/composition.sample.json`.
5. Update this file (keep under 200 lines).

## Implemented in M2 (reference)
- Patterns: `VIDEO_ENGINE/remotion/src/patterns/index.ts` (`PATTERNS`, `buildScene(id, name, PP, transition)`); gallery: `npm run gallery` in `remotion/`.
- Extra image `pos` presets: left-half, right-half, grid-0..3, top-right, bottom-left, small-center. `anim`: ken-burns | float (cutout).
- Text accepts `pos:[x,y]` and `mark:"word"`; chart accepts `box:[x,y,w,h]`; stock-video accepts `clipDur` (loop length, s).
- Map: world-atlas countries only (highlight by country name, route as [lon,lat]); no state borders.
- Transitions: `VIDEO_ENGINE/remotion/src/transitions/index.ts` (`getPresentation`, `pickTransition(prev, mood, index)`).
