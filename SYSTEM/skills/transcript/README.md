# Transcript Domain Skills

## Overview
Skills in the `transcript` domain manage speech-to-text token processing, word-level timestamp alignment, punctuation formatting, and bilingual transcript correction.

## Associated Agents
- `audio_analyzer` (`AudioAnalyzerAgent`): Transcribes audio using faster-whisper and aligns word timestamps.

## Domain Standards
- Word-level timestamps must be strictly monotonic (`start < end`).
- Bilingual terms (e.g. Telugu/Hindi terms in English script) must be preserved verbatim.
- Transcript edits never touch the raw `transcript.json`: corrections go to `transcript_review.json` and `transcript_corrected.json` (`VIDEO_ENGINE/stages/transcript_review.py`).

## Contribution Guidelines
1. Author candidate skills via `SkillFactoryAgent`.
2. Verify tokenization safety and regex boundaries.
3. Promote approved skills into `SYSTEM/skills/transcript/<skill_name>/SKILL.md`.
