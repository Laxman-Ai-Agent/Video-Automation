# Timeline Domain Skills

## Overview
Skills in the `timeline` domain control multi-track layer compilation, frame-accurate synchronization with narration audio, LLM-decided approval gating, and SHA-256 fingerprint locking.

## Associated Agents
- `timeline_build` (`TimelineBuildAgent`): Compiles scene sequences into a single coherent Remotion sequence graph.
- `timeline_approval` (`TimelineApprovalAgent`): LLM-decided approval gate; locks SHA-256 composition fingerprint.

## Key Rules
- Total timeline frame count must match audio duration within $\pm 1$ frame at 30 fps.
- Zero gap or overlapping frames between adjacent scenes unless explicit cross-dissolve is specified.
- Any modification post-approval automatically invalidates the cryptographic lock.

## Contribution Guidelines
1. Draft timeline synchronization heuristics in `SYSTEM/skills/staging/`.
2. Ensure compliance with approval gate protocol before promoting to `SYSTEM/skills/timeline/<skill_name>/SKILL.md`.
