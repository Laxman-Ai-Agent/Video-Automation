# Timeline Approval Agent (v2.0.0)

- **Agent ID:** `timeline_approval`
- **Stage ID:** `approval`
- **Primary Class:** `TimelineApprovalAgent` (alias `TimelineApprovalAdapter`)
- **Version:** `2.0.0`

## Purpose
Acts as the immutable cryptographic gate between Stage 9 (Timeline Build) and Stage 11 (Render Video). Verifies SHA-256 timeline fingerprints, performs visual and structural diff inspection across approval cycles, evaluates narrative quality and disclosures via LLM, enforces authenticated operator sign-off or autonomous rubric policies, and writes tamper-evident audit records.

## Architecture & Subsystems
1. **StructuralDiffAnalyzer**:
   - Compares current timeline scenes, intervals `[start_frame, end_frame)`, transitions, and TSX component hashes against previous approval manifests.
   - Categorizes added, removed, modified, and unchanged scenes.
2. **VisualDiffAnalyzer**:
   - Inspects rendered quarter-size preview stills.
   - Accurately compares preview stills between versions when available, and honestly reports when historical baselines are absent.
3. **LLMTimelineAssessor**:
   - Reuses central `SYSTEM.core.llm_gateway` (`reasoning_review` profile) to evaluate narrative pacing, continuity, and material disclosures.
   - Demarcates visual-backed evaluations from metadata-only reviews.
   - Employs deterministic fallback when LLM is unavailable or offline.
4. **ApprovalRiskClassifier**:
   - Separates hard technical blockers (fingerprint mismatches, missing assets, validation failures) from quality warnings (rapid pacing, optional 3D fallback).
   - Enforces strict deterministic policy: technical blockers cannot be overruled by LLM opinions.
5. **Cryptographic Gate & Certificate Issuance**:
   - Uses `VIDEO_ENGINE.stages.timeline_approval.fingerprint()` (timeline digest + build digest + render configuration).
   - Records decisions to `timeline_approval_history.json` and appends audit events to `config/approvals_audit.jsonl`.
   - Enforces fail-closed invalidation on any upstream change.

## Output Artifacts
- `timeline_approval_history.json` / `timeline_approval_history_9x16.json`
- `timeline_review.json` / `timeline_review_9x16.json`
- `timeline_approval_intelligence.json` / `timeline_approval_intelligence_9x16.json`
- `config/approvals_audit.jsonl` (Append-only central audit trail)
