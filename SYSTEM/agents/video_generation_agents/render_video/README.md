# Render Video Agent (v2.0.0)

- **Agent ID:** `render_video`
- **Stage ID:** `render`
- **Primary Class:** `RenderVideoAgent` (alias `RenderVideoAdapter`)
- **Version:** `2.0.0`

## Purpose
Executes headless Chrome Remotion video rendering with adaptive resource optimization, real-time telemetry capture, autonomous self-healing error recovery, and deep FFprobe media stream verification.

## Architecture & Subsystems
1. **AdaptiveResourceEngine**:
   - Detects host CPU cores and free memory headroom.
   - Dynamically selects safe Remotion worker concurrency (`1` to `3`) to prevent OOM.
2. **RenderFailureClassifier**:
   - Classifies render execution and runtime exceptions into 17 canonical machine-readable categories.
3. **LLMRenderDiagnostician**:
   - Reuses central `SYSTEM.core.llm_gateway` (`reasoning_review` profile) for root cause analysis.
   - Recommends actionable recovery strategies strictly constrained to an explicit allowlist.
   - Features deterministic fallback if LLM is offline or times out.
4. **AutonomousRenderRecoveryCoordinator**:
   - Manages bounded recovery loop (max 2 attempts).
   - Supported actions:
     - `reduce_concurrency`: Drops concurrency to 1.
     - `software_gl_fallback`: Switches to `--gl=angle` when hardware GPU crashes.
     - `reallocate_port`: Requests fresh ephemeral socket port.
     - `restage_assets`: Re-synchronizes audio and motion TSX components.
     - `report_upstream_blocker`: Reports non-recoverable deterministic syntax/contract errors without looping.
5. **OutputIntegrityAuditor**:
   - Uses FFprobe to verify container format (MP4), video stream dimensions, frame rate (30fps), H.264 codec, duration tolerance (±0.15s), and audio synchronization (±0.25s).
6. **Strict Approval Gate**:
   - Enforces cryptographic verification (`timeline_gate.require_approved`) before execution and immediately prior to atomic publishing.
   - Refuses to render or publish when approvals are stale, missing, or invalidated.

## Bound Tools
- `remotion`
- `ffmpeg`
- `browser_profiles`
- `media_probe`
- `llm_gateway`

## Output Artifacts
- `out.mp4` / `out_9x16.mp4` (Atomic published video)
- `render_report.json` / `render_report_9x16.json`
- `render_job.json` / `render_job_9x16.json`
- `render_manifest.json` / `render_manifest_9x16.json`
- `render_intelligence.json` / `render_intelligence_9x16.json` (Diagnostic telemetry, recovery history, output audit)
