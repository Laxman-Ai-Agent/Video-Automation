# Visual upgrade: repository audit (2026-10-15)

**Status: AUDIT v1, catalogue level. NOT a completed code audit.** Every repository was checked for existence, licence, dependencies and what its own README claims. **No source file of any candidate was opened, nothing was cloned, installed, built or rendered**, so claims about "backgrounds" below are the repositories' own descriptions, not tested behaviour. Section 5 lists what is still unverified. No decision here is final until the user decides.

## 1. What was checked (and what was not)
Checked over HTTP, read-only: repo exists (GitHub API) | stars, last push, archived, size, fork | licence: API `spdx_id`, the root `LICENSE` file head (only that filename was tried), the README's own licence section, and the `license` field of root `package.json` | README first ~2.5 KB | root `package.json` dependencies | latest release | for GSAP and Remotion also the **installed** `package.json` in `remotion/node_modules`.
**Not checked:** source code, individual effect files, whether the npm package exists/works, peer-dependency resolution, render speed on this CPU, visual quality, security of dependencies or install scripts, licence of bundled assets (fonts, images, audio), other licence filenames (`LICENSE.md`, `COPYING`). "No licence detected" means GitHub reports none and no root `LICENSE` exists: not proof there is none.

## 2. Our stack (the filter)
React 19.3, Remotion 4.0.534 (installed: transitions, shapes, noise, paths, motion-blur, google-fonts, captions, layout-utils, media-utils, player), `gsap` 3.15.0 (licence field: "Standard 'no charge' license", terms at gsap.com NOT read), d3, lucide-react, zod 4. Node 24, Windows, CPU only, render concurrency 2-4. CLAUDE.md rules: no Framer Motion in videos, no external LLM API, ask before installing, no parallel animation systems, accent colour is never a background.
Already in the project (so not a gap): 41 text presets, 50+ graphics (particles, dust, vignette, HUD, charts), 12 mask transitions, `FilmLook` (vignette + grain), `Grade`, `LightLeak`, `Camera`. The gap is the `background` layer, which was a two-colour gradient.

## 3. Repositories inspected (facts)
| # | Repository | Purpose | Animation / background capability (README claim) | Licence (how verified) | Declared dependencies | Activity |
|---|---|---|---|---|---|---|
| 1 | ssuuppeerrmmaann/remotion-graphic-templates (README/LICENSE say `lifeprompt-team/remotion-scenes`) | 201 ready scenes | BackgroundAnimations 10 (gradients, aurora, mesh, grid), ParticleAnimations 10, EffectAnimations 10 (film grain, VHS, chromatic aberration), CinematicAnimations 10, LiquidAnimations 10, TextAnimations 12 | MIT: LICENSE head read ("Copyright (c) 2026 lifeprompt-team") | remotion ^4, **react ^18**, three ^0.160, **@react-three/fiber ^8**, @remotion/three, drei | 1 star, push 2026-02-05, 910 KB |
| 2 | reactvideoeditor/remotion-templates | 81 templates | charts and data, text, transitions | README states MIT; **no LICENSE file, no root package.json** | not declared | 261 stars, push 2026-04-21 |
| 3 | Thedurancode/locomotion-templates | 67 templates | property tour, data viz | **none detected** (API none, package.json none) | remotion ^4.0.441, react ^19, **framer-motion**, supabase, anthropic sdk | 1 star, 23 MB |
| 4 | RenderComp/free-remotion-templates | 50 templates | KPI/stat and other single-file components | MIT: LICENSE head read ("Trimora Inc.") | remotion 4.0.518, react ^19 only; "no fonts, images or audio bundled" | 11 stars, push 2026-09-07 |
| 5 | github.com/remotion-dev | the Remotion organisation, not a repo | official packages | installed `remotion` package: "SEE LICENSE IN LICENSE.md" (text not read; check remotion.dev/license for company use) | n/a | n/a |
| 6 | remotion-dev/template-three | Remotion + r3f boilerplate | 3D scene starter | API says MIT, **its package.json says UNLICENSED** (discrepancy, LICENSE not read) | remotion ^4, react 19.2.3, three 0.178, r3f 9.2 | 111 stars, push 2026-10-12 |
| 7 | eohjun/remotion-studio | Korean AI-agent video system | many (captions, light-leaks, gif, r3f) | **none detected**, package.json UNLICENSED | remotion 4.0.427, react 19, fal-ai client, r3f 9 | 0 stars, 202 MB |
| 8 | omnidotdev/remotion-bits | **URL returns 404** | - | not applicable | - | name search finds `av/remotion-bits` (489 stars, README says MIT): a different owner, only its README header seen |
| 9 | omnidotdev/remotion-ui | **404** | - | - | - | search finds `riaz37/remotion-ui` (66 stars, MIT per API): different project, not read |
| 10 | ondavideo/onda | **404** | - | - | - | no match found |
| 11 | ali-abassi/remotion-templates | templates for AI agents | captions etc. | **none detected** | remotion 4.0.514, **react 18.3.1** | 35 stars, 352 MB |
| 12 | ANVEAI/motion-pack | Python video parts + 6 AI agent skills | not a component library | MIT: LICENSE head read | Python | v0.1.0 (2026-10-13), 134 MB |
| 13 | itsjwill/react-video-toolkit | cinematic effects for Remotion | FilmGrain, ColorGrade (8 presets), Parallax (noise drift), motion blur | MIT: package.json field + README (no LICENSE file) | remotion 4.0.409, react 19.2.3, @remotion/noise, motion-blur, paths, shapes, transitions | 1 star, 55 KB |
| 14 | imshreekumarOPS/remotion-open-fx | npm `remotion-open-fx` | 30+ easings, springs, transitions, overlays, VHS/retro effects, letterbox | MIT: LICENSE head read | peers: react >=18, remotion >=4 | 1 star, 49 KB, push 2026-02-28 |
| 15 | greensock/GSAP | timeline animation | not background related | installed package: "Standard 'no charge' license" (terms not read) | none | already installed |
| 16 | airbnb/lottie-web | After Effects JSON player | needs Lottie JSON files | MIT (API; package.json field MIT) | `@remotion/lottie` needed | 32k stars, last push 2025-09-01 |
| 17 | pmndrs/react-three-fiber | React renderer for three | 3D | MIT: LICENSE head read | three, drei, `@remotion/three` | v9.8.1, active |
| 18 | motion-canvas/motion-canvas | own animation framework + editor | own runtime | MIT: LICENSE head read | own | push 2026-07-02, last release 2024-12 |
| 19 | ManimCommunity/manim | Python maths animation | clips | MIT: LICENSE head read | Python; LaTeX/Cairo/ffmpeg are general knowledge, not verified here | active |
| 20 | rive-app/rive-react | Rive runtime | needs `.riv` files | MIT: LICENSE head read | @rive-app/canvas, wasm | v4.36.0 |
| 21 | transloadit/uppy | file uploader | not animation related | MIT: LICENSE head read | @uppy/* packages | v6.0.4 |
| 22 | vincent/damask | digital asset manager | not animation related | Apache-2.0: head read | Go service | v0.3.9 |
| 23 | immich-app/immich | photo/video server | not animation related | **AGPL-3.0**: head read | server + database + ML (general knowledge, not verified here) | active |
| 24 | ssrajadh/sentrysearch | semantic video search | not animation related | Apache-2.0: head read | **Gemini Embedding API** or Qwen3-VL | 4.5k stars |
| 25 | aramadan0096/Stax | stock-footage manager | not animation related | **none detected** | Python app | 8 stars |
| 26 | alexrienzie/open-post-production | media asset management | not animation related | NOASSERTION: head read | Python app | v0.1.0 |
| 27 | google/fonts | font files | typography | per family (not read) | 3.3 GB repo | active |
| 28 | airbnb/lottie-web | duplicate of #16 | - | - | - | - |

## 4. Assessment
| # | Integration effort (estimate) | Compatibility with our stack | Recommendation | Why |
|---|---|---|---|---|
| 1 | Medium per component: scenes have fixed content, must become props + seed + palette driven; difficulty NOT inspected | **Declares react ^18 and r3f ^8**; our app is React 19 (r3f 8 needs React 18). Non-3D scenes may be fine: untested | **Extract components, after a code inspection** of Background/Particle/Effect folders | Only candidate with a directly relevant, MIT-verified background and particle catalogue |
| 2 | Low-Medium | Remotion hooks only; versions unknown | **Optional** | Overlaps our charts/counters; licence file missing |
| 3 | - | Framer Motion, supabase, anthropic sdk | **Reject** | No licence detected; forbidden dependencies |
| 4 | Low | remotion 4.0.518 / react 19 match ours | **Optional (few components)** | Clean and MIT-verified; no background content claimed |
| 5 | None | already installed | **Use official packages only if a need is shown** | e.g. `@remotion/lottie`, `@remotion/three`, `@remotion/light-leaks` |
| 6 | Medium | react 19 + r3f 9 matches; WebGL on this CPU untested/slow | **Optional, reference for 3D** | Licence discrepancy to resolve first |
| 7 | - | huge, agent system | **Reject** | No licence, parallel pipeline |
| 8-10 | - | cannot assess | **Not assessed** | Wrong URLs: user to confirm the intended repositories |
| 11 | - | react 18.3.1 | **Reject** | No licence detected, 352 MB |
| 12 | - | not a Remotion library | **Reject** | Wrong kind of project |
| 13 | Low | react 19 / remotion 4.0.409 | **Optional (ideas)** | Grain, grade and parallax duplicate our `FilmLook`, `Grade`, `Camera`; new idea: 8 grade presets |
| 14 | Low-Medium | peers fit | **Optional** | Easings/transitions duplicate ours; retro/VHS overlay is the only gap; npm package not verified |
| 15 | None | installed | **Keep as is** | Used only as a paused timeline |
| 16 | Low | needs `@remotion/lottie` (not installed) and Lottie files | **Optional** | CLAUDE.md: only with user-supplied files |
| 17 | High | `@remotion/three`, three, drei; CPU WebGL speed unknown | **Optional / defer** | Only for dedicated 3D scenes |
| 18 | High | own time model | **Reject** | Parallel animation system |
| 19 | High | Python + LaTeX | **Reject for now** | Heavy runtime |
| 20 | Medium | needs Rive assets | **Reject for now** | No assets |
| 21 | Medium | MIT, v6 | **Optional** | We already use `react-dropzone`; the missing part is matching and video support, not the uploader |
| 22, 23, 25, 26 | - | services / unclear licence | **Reject** | Separate apps; AGPL / unlicensed |
| 24 | - | needs Gemini API | **Reject** | CLAUDE.md forbids external LLM APIs |
| 27 | None | `@remotion/google-fonts` installed | **Use the existing package** | Do not clone 3.3 GB |

External sources (not repositories, not verified in this audit): Pexels and Pixabay (own content licences), NASA Images, Wikimedia Commons (per-file licences, attribution), Google Fonts. `backend/stock.py` and `credits.json` already exist for them.

## 5. Open questions before any decision
1. **Background effects were never inspected in code.** To decide what to extract from #1 (and #13, #14) someone must read their background/particle/grain files (file list, size, dependencies, how hard to make seed-driven) and render a sample.
2. #1 is React 18 / r3f 8: which scenes need three? Untested against React 19.
3. Which repositories did the user mean by #8, #9, #10?
4. #6 licence: API says MIT, its package.json says UNLICENSED.
5. Remotion's own licence terms apply to this product if it is used commercially: verify at remotion.dev.
6. Licences of bundled assets (fonts, images, audio, Lottie files) in any template were not examined.
