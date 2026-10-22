# Audio Domain Skills

## Overview
Skills in the `audio` domain govern audio ingestion, downsampling, silence detection, phonetic preservation, and bilingual audio handling.

## Associated Agents
- `audio_input` (`AudioInputAgent`): Ingestion, normalization, duration probing.
- `audio_analyzer` (`AudioAnalyzerAgent`): Phonetics review, pause detection, silence boundaries.

## Active Skills
- `audio.bilingual_preservation` (`bilingual_preservation/SKILL.md`): Preserves non-English phonetic tokens and acronyms during transcription and review.

## Contribution Guidelines
1. Draft new audio skills with complete YAML frontmatter in `SYSTEM/skills/staging/`.
2. Ensure static security audit passes with `SkillFactoryAgent`.
3. Submit for human review before promoting to `SYSTEM/skills/audio/<skill_name>/SKILL.md`.
