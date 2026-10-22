# Timeline Build Agent v2.0.0

- **Agent ID:** `timeline_build`
- **Stage ID:** `timeline`
- **Primary Class:** `TimelineBuildAgent` (alias `TimelineBuildAdapter`)
- **Version:** `2.0.0`

## Purpose
The Timeline Build Agent compiles validated scene components, narration audio, dynamic background music, subtitles, and overlays into an exact, frame-accurate Remotion timeline (`timeline[_9x16].json`). It enforces 30fps arithmetic, half-open intervals $[start\_frame, end\_frame)$, speech-aware background music ducking, and semantic cinematic transitions.

## Architecture & Subsystems
1. **Deterministic 12-Stage Compiler (Preserved Authority):**
   - Stage 1: Request & Lock
   - Stage 2: Input Discovery
   - Stage 3: Freshness & Readiness Gate (Stage 10 clearance)
   - Stage 4: Project Settings Normalization
   - Stage 5: Scene Mapping & Coverage
   - Stage 6: Frame Timing Normalization (30fps `mp.fr`)
   - Stage 7: Video Track Assembly
   - Stage 8: Audio & Narration Track Assembly
   - Stage 9: Transition & Gap Policy Application (`hold_previous_scene`)
   - Stage 10: Timeline Assembly & Duration
   - Stage 11: Post-Build Structural Validation
   - Stage 12: Persist, Read Back, & Publish
2. **AudioDuckingEngine:**
   - Extracts authoritative speech intervals from `transcript.json` / `transcript_fixed.json`, `cuts.json`, and `audio_analysis.json`.
   - Generates piecewise linear volume automation curves for background music:
     - 15% volume during speech (`speech_gain: 0.15`)
     - 40% volume during pauses > 0.5s (`pause_gain: 0.40`)
     - 150ms smooth linear attack/decay ramps to eliminate auditory pumping.
3. **CinematicTransitionSelector:**
   - Recommends transitions from supported Remotion library: `fade`, `slide`, `wipe`, `flip`, `clock-wipe`, `zoom-through`, `light-leak`, `blur`, `mask-shape`, `match-move`, `particle`.
   - Validates that transition duration fits within scene boundaries without modifying narration synchronization.
4. **SceneContinuityAssessor:**
   - Evaluates cross-scene pacing, motion energy continuity, and duration boundaries.
5. **TimelineRecoveryCoordinator:**
   - Bounded autonomous repair (max 2 attempts) for compiler-solvable defects (transition window overflow, unsupported transition substitution).

## Outputs & Artifacts
- `timeline[_9x16].json`: Master multi-track timeline manifest.
- `timeline_build_report[_9x16].json`: 12-stage technical compiler report.
- `timeline_intelligence[_9x16].json`: Ducking profile, transition recommendations, and continuity assessment.
