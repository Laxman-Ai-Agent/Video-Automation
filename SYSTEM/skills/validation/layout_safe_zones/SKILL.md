---
skill_id: validation.layout_safe_zones
name: Layout Safe Zones & Collision Guard
domain: validation
version: 1.0.0
summary: Deterministic boundary checks and safe zone enforcement for 9:16 and 16:9 Remotion compositions.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - safe-zone-validation
  - collision-detection
  - bounding-box-audit
dependencies: []
compatible_agents:
  - motion_planning
  - motion_timeline_validation
compatible_project_modes:
  - motion_only
---

# Layout Safe Zones & Collision Guard

## Purpose
Enforces geometric safety boundaries on all generated TSX layout elements to guarantee that text, graphics, and HUD elements are never obscured by social media platform UI overlays (YouTube Shorts buttons, Instagram Reel captions, TikTok sidebars).

## Dimension Bounds (at 30 fps)
1. **9:16 Portrait Canvas (1080 x 1920)**:
   - Action Safe: x in [54, 1026], y in [96, 1824] (5% margin).
   - Title / UI Safe: x in [108, 972], y in [240, 1680] (10% horiz, ~12% vert).
   - Right-side Action Button Exclusion: Reserve [900, 1080] x [1100, 1700] clear of critical focal elements.
2. **16:9 Landscape Canvas (1920 x 1080)**:
   - Action Safe: x in [96, 1824], y in [54, 1026] (5% margin).
   - Title Safe: x in [192, 1728], y in [108, 972] (10% margin).

## Collision Auditing
- Maintain a minimum 32px vertical separation between adjacent kinetic text lines.
- Reject any composition where text bounding box intersects another element with overlapping z-index.
