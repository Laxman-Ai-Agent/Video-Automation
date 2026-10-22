# Resource Manager: audit and verification evidence (2026-10-15)

Design and rules: `docs/resources.md`. Raw evidence stays in the JSON files of this folder; this file only summarises them.

## Audits (`audits/`)
| Audit | Source | Decision | Note |
|---|---|---|---|
| 20261015-070218-83c9e2 | tabler/tabler-icons v3.49.0 (MIT) | import | every hard gate passed, score 99.9 (39 outline icons) |
| 20261015-070226-c72fb1 | google/fonts, Hind Guntur | skip | gate files_safe_and_valid: a Telugu glyph was missing |
| 20261015-070300-c72fb1 | google/fonts, Hind Guntur (OFL-1.1) | import | gates passed, score 91.2; native Telugu digits remain absent (disclosed) |

**Why the font skipped, then passed (established from the two audit files and `resource_audit.py`):** same repository commit (`67bc647ce1…`), same two font files. The first audit (07:02:26) required the ten native Telugu digits U+0C66-U+0C6F; they are missing in Hind Guntur, so `files_safe_and_valid` failed (179 glyphs checked). The second audit (07:03:00) came from changed code: the digits moved into `TELUGU_OPTIONAL` (code comment: modern Telugu text and this project use ASCII digits), 169 glyphs required, the same ten recorded as `telugu_optional_missing` and a new `limitations` entry added. So the font did not change; the rule did, after the first skip. Whether that relaxation is acceptable is a judgement for you; the gap is disclosed in the audit, the registry entry and `docs/resources.md`. No log records who decided it beyond the code comment.

## Registry now (52 entries, all `verified`, none stale)
icon 39 (Tabler, MIT) · font 1 (Hind Guntur, OFL-1.1) · background 3 · chart 3 · diagram 4 · effect 1 · react_component 1 (the last 12 are project code, LicenseRef-project).

## Verification (`verification/`, 4 runs)
Run 20261015-072121 verified 45, failed 3 (line chart, particles, radar sweep) and skipped 4 diagram entries. Later runs re-verified those 7 after the fixes below; the registry now holds 52 verified.
Causes found: the sample layers of the diagram graphics, radar sweep and particles lasted 1 s but the still is taken at 1.6 s (the effect had ended); the particles sample was too faint (dots enlarged, `k` 7).
**Threshold:** the chart threshold is back at its original 0.01. The line-chart sample now has 8 points (`_LINE_DATA`); re-verified alone: 16:9 ratio 0.029, 9:16 ratio 0.0172, both above 0.01. Pixel evidence: the change lies inside the chart box only (16:9 bbox x 205-754, y 118-437 of 960x540; 9:16 bbox x 51-488, y 322-572 of 540x960), not spread over the frame.
Method: pixel change against an empty baseline in 16:9 and 9:16, same frame twice identical, local resolution. It is not a visual review. No person has looked at `resource-library/previews/`.

## Pipeline integration checks (this session)
- Fixed: the Python check read `fontSha256` while the renderer and gallery write `fontSha`, so any composition using a registry font was flagged `resource_hash_missing`; regression test added.
- Fixed: `resource_library` hashed source files under the current `config.PROJECT_ROOT` but read the registry from the import-time root; with a moved root every resource looked stale. Now one fixed root (`BASE`).
- Fixed: Stage 10 ran the resource check twice (duplicated block in `motion_validation_rules.py`), reporting each failure twice.
- `test_motion_planning` primitive-list test updated: it now expects the verified registry icons as `resource:` ids.
- Tested: a used resource turning stale changes its fingerprint; an unrelated composition's fingerprint does not change.

## Visual inspection and chart label fix (Claude, 2026-10-15; not the human-review record)
Looked at contact sheets of the 13 single previews (16:9 and 9:16) and both icon sheets. All graphics visible and unclipped in both aspects; Telugu text shapes correctly; no icon defect (corner icons are ~20% dimmer from the scene vignette). Defect: line-chart value labels were crossed by the line in both aspects. Fix: dark halo on the line labels in `remotion/src/components/Chart.tsx` (shared file, so bar, line, pie were re-verified, nothing else): bar 0.1155 / 0.0719, line 0.0312 / 0.0181, pie 0.0918 / 0.0574 (16:9 / 9:16), threshold 0.01. Test `test_a_blank_chart_fails...` shows a blank or hairline chart still fails at 0.01.
Browser check of `/resources` (own backend 8001, Vite 5174, stopped afterwards): see PROJECT_STATUS.md. Registry consistency checked: 52 verified, files match hashes, evidence files exist, licence texts exist, aspect lists equal the verified aspects, bundle hashes match.

## Real project refresh
See PROJECT_STATUS.md, section "Real project `my-video-project-c2e8`: stale artifacts refreshed". First stale artifact: Motion Planning (renderer source digest). Rebuilt: planning, generation, Stage 10, Stage 11. Stale and preserved: approval, render, Final QC.
