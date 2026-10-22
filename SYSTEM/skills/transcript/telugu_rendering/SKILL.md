---
skill_id: typography.telugu_rendering
name: Telugu Typography and Caption Layout Engine
domain: transcript
version: 1.0.0
summary: Ensures Unicode stability, font glyph compatibility, rhythmic line breaking, and safe-zone placement for Telugu video captions.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - telugu-unicode-shaping
  - caption-line-breaking
  - safe-zone-captioning
  - noto-sans-telugu-config
tags:
  - telugu
  - typography
  - captions
  - subtitles
  - unicode
dependencies: []
compatible_agents:
  - audio_analyzer
  - kinetic_typography
  - timeline_assembly
compatible_project_modes:
  - motion_only
input_contracts:
  telugu_text:
    type: string
    description: Spoken Telugu sentence or phrase to be rendered
  font_family:
    type: string
    default: Noto Sans Telugu
  aspect_ratio:
    type: string
    options:
      - "9:16"
      - "16:9"
    default: "9:16"
  max_words_per_line:
    type: integer
    default: 6
  position_y_pct:
    type: float
    default: 0.82
output_contracts:
  formatted_lines:
    type: list
    description: Balanced caption lines formatted with proper hyphenation and conjunct safety
  font_config:
    type: dict
    description: CSS font properties, font-weight, line-height, and fallback cascade
  safe_bounds:
    type: dict
    description: Bounding rectangle conforming to vertical video UI exclusion zones
---

# Telugu Typography and Caption Layout Engine

## Purpose
Guarantees clean, defect-free Telugu script rendering for subtitles, callouts, and typography.
Handles complex conjunct consonants (vattulu), zero-width non-joiners, line balancing,
and safe placement to prevent occlusion by mobile application interface overlays.

## Core Rules

1. **Unicode Script Stability**:
   - Strictly preserve Telugu Unicode points (`\u0C00` through `\u0C7F`).
   - Never break words across compound glyphs (consonant + virama + consonant combinations).
   - Ensure UTF-8 clean encoding without corruption characters (`\ufffd`).

2. **Font & Rendering Configuration**:
   - Primary typeface: `Noto Sans Telugu` (Google Fonts).
   - Fallback cascade: `'Noto Sans Telugu', 'Gautami', 'Vani', sans-serif`.
   - `font-feature-settings: 'liga' 1, 'clig' 1, 'kern' 1` must be enabled to ensure proper Telugu ligature shaping.
   - Line height multiplier: minimum `1.45` to prevent diacritic clipping on top and bottom vowel signs.

3. **Rhythmic Line Balancing**:
   - `9:16` Canvas: Maximum 6 words per line. Break at grammatical breath points (commas, conjunctions).
   - `16:9` Canvas: Maximum 10 words per line. Center-aligned with subtle text shadow (`0 2px 8px rgba(0,0,0,0.85)`).

4. **Safe Placement for Social Canvas (9:16 Shorts / Reels)**:
   - Captions must sit at `position_y_pct = 0.82` (1574px on a 1920px canvas).
   - Placing captions below `0.85` is strictly forbidden as it collides with account handles, audio badges, and scrub bars.
