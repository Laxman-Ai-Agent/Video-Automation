---
skill_id: audio.bilingual_preservation
name: Bilingual Telugu Script & Orthography Preservation
domain: audio
version: 1.0.0
summary: Principles for maintaining native Telugu vocabulary in Telugu script while retaining technical terms in English.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - telugu-orthography
  - script-routing
  - technical-term-detection
dependencies: []
compatible_agents:
  - audio_analyzer
  - visual_planning
compatible_project_modes:
  - motion_only
---

# Bilingual Telugu Script & Orthography Preservation

## Purpose
Establishes the linguistic boundaries for Telugu speech transcription and visual concept translation.

## Rules
1. **Telugu Script Preservation**:
   - Native Telugu words, verb inflections, conjunctions, and colloquial spoken phrases must be transcribed and preserved strictly in authentic Telugu script (Unicode range U+0C00–U+0C7F).
   - Do not romanize Telugu vocabulary into Latin script (e.g., preserve "నమస్కారం", never "namaskaram").
2. **Technical Loanword Handling**:
   - English technical terminology, brand names, and programming or scientific terms spoken in Telugu narration should be transcribed in standard English orthography (e.g., "AI", "Quantum Computing", "Python", "Rocket").
   - Do not phonetically transliterate English technical nouns into awkward Telugu script when the meaning is clearer in English.
3. **Punctuation & Boundary Snapping**:
   - Align phrase boundaries with spoken natural pauses (> 0.35s).
   - Avoid breaking compound Telugu words across scene boundaries.
