---
skill_id: motion.remotion_spring_curves
name: Remotion Spring Physics & Curve Math
domain: motion
version: 1.0.0
summary: Standard spring curves, damping coefficients, and interpolation mechanics for smooth Remotion animations.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - spring-physics
  - interpolation-math
  - frame-clamping
dependencies:
  - remotion
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Remotion Spring Physics & Curve Math

## Purpose
Provides calibrated physics parameters for Remotion's `spring()` and `interpolate()` primitives to achieve punchy, broadcast-quality motion without oscillations or jitter.

## Recommended Spring Configurations (at 30 fps)
1. **Snappy Entry (Text & Cards)**:
   - `damping: 15`
   - `mass: 0.6`
   - `stiffness: 120`
   - Yields a crisp ~12-frame entrance with subtle overshoot (< 4%).
2. **Smooth Float / Ambient Motion**:
   - `damping: 25`
   - `mass: 1.2`
   - `stiffness: 60`
   - Overdamped; smooth deceleration without bounce.
3. **High Impact (Punches & Accents)**:
   - `damping: 10`
   - `mass: 0.4`
   - `stiffness: 180`
   - Fast, tactile pop settling within 8-10 frames.

## Frame Clamping Invariant
Always clamp interpolations to prevent visual overflow:
```typescript
const scale = interpolate(frame, [start, start + 15], [0.8, 1.0], {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
});
```
Never omit clamping when driving transforms near canvas boundaries.
