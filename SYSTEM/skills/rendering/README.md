# Rendering Domain Skills

## Overview
Skills in the `rendering` domain govern headless Chrome Remotion execution, port allocation, hardware acceleration flags, stream encoding (H.264/AAC), and render telemetry capture.

## Associated Agents
- `render_video` (`RenderVideoAgent`): Remotion CLI executor with dynamic ephemeral port allocation and crash recovery.
- `final_video_delivery` (`FinalVideoDeliveryAgent`): Artifact packaging, SHA-256 provenance auditing, and file serving.

## Operational Standards
- Dynamic port allocation: Render servers must bind to free ports dynamically (avoiding hardcoded port 3000 conflicts).
- Telemetry: Capture render time, frame rate, peak memory, and encoding errors.
- Verification: Delivered video must have a valid MP4 container, valid moov atom, and match audio duration within acceptable tolerance.

## Contribution Guidelines
1. Stage render optimization profiles in `SYSTEM/skills/staging/`.
2. Ensure flags work in headless CI/server environments.
3. Promote approved skills into `SYSTEM/skills/rendering/<skill_name>/SKILL.md`.
