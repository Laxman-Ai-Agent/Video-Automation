# Production Operator Runbooks

These runbooks provide authoritative operational guidance for maintaining, debugging, and recovering the Dark World Video Generation Agent pipeline in production.

---

## Runbook 1: Headless Chromium / Browser Capability Blocked

### Symptoms
- Capability check reports `browser_ready: false`.
- The `render` stage or monitoring status reports `blocked` with:
  `"Headless Chromium/Puppeteer is not preconfigured in the environment. Phase 7 live Remotion render remains an unresolved environment prerequisite."`

### Diagnostic Steps
1. Query system capabilities via API:
   ```bash
   curl http://127.0.0.1:8000/projects/{project_id}/orchestrator/capabilities
   ```
2. Verify host browser installation without downloading anything:
   - On Windows: Check whether Chrome exists at:
     `C:\Program Files\Google\Chrome\Application\chrome.exe`
     or Edge at:
     `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
   - On Linux: Check `which google-chrome` or `which chromium-browser`.

### Recovery Action
- If a browser is already installed at a custom path, export the environment variable:
  ```powershell
  $env:PUPPETEER_EXECUTABLE_PATH = "C:\Path\To\chrome.exe"
  ```
- **CAUTION**: Do NOT run package managers or auto-download scripts without explicit administrative authorization.
- Re-query capabilities to confirm `browser_ready: true`.

---

## Runbook 2: Missing or Stale Upstream Artifacts

### Symptoms
- Stage execution fails closed with `ContractValidationError` or `missing_upstream_artifact`.
- Orchestrator DAG eligibility reports `eligible: false` and lists missing artifact dependencies.

### Diagnostic Steps
1. Inspect stage eligibility:
   ```bash
   curl http://127.0.0.1:8000/projects/{project_id}/orchestrator/status
   ```
2. Check `resume_plan` in the response to identify the earliest invalid or incomplete stage.
3. Verify files on disk in `projects/{project_id}/`:
   - `audio`: `audio.*`, `audio_manifest.json`
   - `analyzer`: `transcript.json`
   - `segmentation`: `cuts.json`, `scene_segmentation.json`
   - `planning`: `visual_planning.json`
   - `motion_plan`: `motion_plan.json`
   - `motion_gen`: `motion_manifest.json`, `VIDEO_ENGINE/remotion/src/generated/scene_*.tsx`
   - `timeline`: `timeline.json`, `timeline_build_report.json`

### Recovery Action
- Resume the pipeline from the earliest invalid stage using the orchestrator:
  ```bash
  curl -X POST http://127.0.0.1:8000/projects/{project_id}/orchestrator/run \
       -H "Content-Type: application/json" \
       -d '{"resume": true, "aspect": "16:9"}'
  ```
- Downstream valid stages will be cleanly re-evaluated, and invalid stages re-executed.

---

## Runbook 3: LLM Provider Authentication, Timeout, or Parse Failure

### Symptoms
- Stage status transitions to `failed` or `blocked` with:
  - `llm_gateway_error: authentication_failed`
  - `llm_gateway_error: timeout`
  - `llm_gateway_error: malformed_response`
- Communication event shows `stage_failed` or `review_rejected`.

### Diagnostic Steps
1. Inspect telemetry and provider health:
   ```bash
   curl http://127.0.0.1:8000/llm/status
   curl http://127.0.0.1:8000/llm/usage
   ```
2. Verify that credentials are not expired or revoked. **Never log raw API keys**.
3. Determine if the error is transient:
   - Socket timeout or rate limit (`429`): Handled automatically by bounded retry (up to 3 attempts).
   - Auth error (`401`/`403`) or invalid schema: Non-transient; fails closed immediately.

### Recovery Action
- For transient faults, the orchestrator will retry within bounds.
- For schema parse errors, inspect bounded repair logs in `backend/llm_gateway.py`.
- For persistent auth errors, update the verified credentials in `config/llm_settings.json` and retry the run.

---

## Runbook 4: Custom TSX Compilation or Security Rejection

### Symptoms
- Stage `motion_gen` or `motion_validation` fails with:
  - `tsx_compile_error`
  - `tsx_security_violation: forbidden API (eval/child_process/fs/network)`
  - `layout_safe_zone_violation`

### Diagnostic Steps
1. View the generated scene file in `projects/{project_id}/scenes/scene_{id}.tsx` or `VIDEO_ENGINE/remotion/src/generated/`.
2. Inspect `motion_validation_report.json` for specific static security or TypeScript syntax diagnostics.
3. Check if the bounded repair loop in `motion_animation.py` exhausted its retries (default: 3).

### Recovery Action
- If a security check rejected dynamic code, verify the LLM prompt instructions in `backend/motion_animation.py`.
- Run targeted compilation check:
  ```bash
  npx tsc --noEmit -p VIDEO_ENGINE/remotion/tsconfig.json
  ```
- Re-run `motion_gen` stage with resume flag.

---

## Runbook 5: Video Render or Media Probe Failure

### Symptoms
- `render` stage fails with `RenderError` or `ProbeError`.
- Output file `out.mp4` missing, empty (< 1000 bytes), or corrupt.
- A rejected output is retained as `out.failed-{job_id}.mp4` for diagnosis.

### Diagnostic Steps
1. Inspect `render_job.json` and `render_report.json` in the project folder.
2. Probe the failed file manually if present:
   ```bash
   ffprobe -v error -show_entries stream -of json projects/{project_id}/out.failed-*.mp4
   ```
3. Check available disk space (`check_disk` requires at least 2 GB free).
4. Inspect temporary Chrome profile sweeps in `backend/browser_profiles.py`.

### Recovery Action
- Review error diagnostics in `render_job.json`.
- If render timed out or ran out of disk, clear disk space and restart render.
- Existing known-good output `out.previous.mp4` remains preserved and is never destroyed by failed renders.

---

## Runbook 6: Human Timeline Approval Pending or Invalidated

### Symptoms
- `approval` stage status is `needs_review` or `blocked`.
- `render` stage is blocked with `"current timeline is not approved"`.
- Approval history shows `status: "stale"`.

### Diagnostic Steps
1. Query gate status:
   ```bash
   curl http://127.0.0.1:8000/projects/{project_id}/orchestrator/gates?aspect=16:9
   ```
2. Verify why approval is stale:
   - Fingerprint mismatch between `timeline_approval.json` and current `timeline.json`.
   - Upstream scenes or durations changed after approval was signed.

### Recovery Action
- Rebuild the timeline (`timeline-build`); the LLM approval review then decides the new version automatically.
- If the review rejects it, the stage fails with the exact cause: fix that cause upstream and rebuild.
- **IMPORTANT**: There is no manual approval; only the recorded LLM decision for the exact fingerprint satisfies this gate.

### Symptoms
- `final` stage fails with `delivery_blocked: unsatisfied_gates`.
- Final delivery manifest is not generated or signed.

### Diagnostic Steps
1. Query orchestrator status:
   ```bash
   curl http://127.0.0.1:8000/projects/{project_id}/orchestrator/status
   ```
2. Verify all prerequisite gates:
   - Timeline Approval: Must be approved and matching current timeline fingerprint.
   - Render Output: `out.mp4` must exist, pass media probe, and match recorded SHA-256.
   - Final QC: Deterministic checks passed, LLM review passed, and **the Final QC LLM decision approved** (`final_qc_review.json`).

### Recovery Action
- Satisfy whichever gate is incomplete:
  - If the Final QC LLM decision is missing or not approved: run Final QC again (`POST /projects/{project_id}/final-qc/run`) and fix what the decision's notes name.
  - If render was re-run: re-run Final QC; the old decision belongs to the old file.
- Once all gates are satisfied, resume pipeline to finalize `delivery_manifest.json`.
