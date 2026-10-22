# Motion Validation Agent v2.0.0

- **Agent ID:** `motion_timeline_validation`
- **Stage ID:** `motion_validation`
- **Primary Class:** `MotionValidationAgent` (alias `MotionValidationAdapter`)
- **Version:** `2.0.0`

## Purpose
The Motion Validation Agent provides an evidence-based, four-dimensional quality and technical validation suite for motion and timeline outputs. It preserves the 12 deterministic technical check stages while integrating LLM intelligence, computer vision heuristics on rendered preview stills, semantic alignment verification, and bounded autonomous repair.

## Architecture & Subsystems
1. **Deterministic Technical Core (Preserved 12 Stages):**
   - Input Provenance, Fingerprint Freshness, Scene Mapping, Timing & Frame Integrity, Element Completeness, Animation Presets, Layout & Collision, Audio & Text Sync, Transition Readiness, Buildability & Determinism, Preview Validation, Readiness Gate.
   - Non-negotiable technical blocker gating.
2. **VisualQualityAssessor:**
   - Computer vision heuristics measuring luminance, contrast, edge density, safe area margin violations, and blank frame detection on rendered preview stills (`motion_validation_preview`).
   - LLM Gateway visual reasoning review.
3. **SemanticAlignmentEngine:**
   - Cross-checks visual planning, motion planning, and generated TSX implementations.
   - Assesses 3D graceful fallback metadata from `motion_generation_report.json` (supported 3D, 2D/2.5D CSS approximations, and safely skipped optional 3D elements).
4. **QualityScoreAggregator (4-Dimensional Quality Architecture):**
   - `Technical` (0-100): Deterministic technical compliance.
   - `Visual` (0-100): Composition balance, contrast, readability, and safe margins.
   - `Semantic` (0-100): Visual plan fidelity, narrative alignment, and 3D fallback health.
   - `Runtime` (0-100): Preview decode stability, duration sync, and determinism.
   - `Overall`: Weighted combination (35% Tech, 25% Visual, 25% Semantic, 15% Runtime).
5. **AutonomousRepairCoordinator:**
   - Coordinates bounded repair attempts (max 2 attempts) for actionable defects (`visual_composition` safe margins, `text_readability` contrast, missing elements).
   - Re-verifies using deterministic rules and preview checks before finalizing reports.

## Canonical Findings Categories
- `visual_composition`
- `text_readability`
- `element_overlap`
- `missing_visual`
- `semantic_mismatch`
- `fallback_quality`
- `temporal_uncertainty`
- `preview_failure`
- `resource_failure`

## Output Artifacts
- `motion_timeline_validation[_9x16].json`: Technical validation report and readiness verdict.
- `motion_validation_intelligence[_9x16].json`: 4D quality scores, categorized findings, and visual metrics.
- `motion_validation_preview[_9x16]/`: Rendered low-resolution preview stills.
