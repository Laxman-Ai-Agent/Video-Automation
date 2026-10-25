---
name: persistent-experience-memory
description: Read, record, and search cross-session experiences, agent learnings, prompt optimizations, and vocabulary corrections in SYSTEM/agents and shared_memory.json to improve Telugu NLP and video generation over time.
---

# Persistent Experience Memory & Continuous Learning

Use this skill to query, update, and persist agent learnings across pipeline runs. When a stage experiences a failure, an LLM vocabulary correction, or an optimization discovery, record it so future runs avoid the same pitfall.

## 1. Memory Structure

Each specialized video agent maintains an authoritative `experiences.json` file under its directory:
`SYSTEM/agents/video_generation_agents/<agent_name>/memory/experiences.json`

Global shared knowledge is stored in:
`config/shared_memory.json`

### Memory Record Schema:
```json
{
  "timestamp": "2026-10-25T16:40:00Z",
  "project_id": "sample-01",
  "stage_id": "segmentation",
  "category": "vocabulary_correction",
  "observation": "Whisper STT mistranscribed Telugu domain term X into Y",
  "correction": "Added domain dictionary mapping X -> Z in prompt prefix",
  "outcome": "Success, semantic beat segmentation verified by LLM review"
}
```

---

## 2. Pre-Stage Memory Recall (Reading Memory)

Before running an LLM prompt for Stage 02 (Scene Segmentation) or Stage 03 (Visual Planning):
1. Read the agent's memory:
   ```python
   import json
   from pathlib import Path

   def load_agent_experiences(agent_name: str):
       mem_path = Path(f"SYSTEM/agents/video_generation_agents/{agent_name}/memory/experiences.json")
       if mem_path.exists():
           try:
               return json.loads(mem_path.read_text(encoding="utf-8"))
           except Exception:
               return []
       return []
   ```
2. Inject learned vocabulary corrections and formatting pitfalls as system instructions into the prompt payload.

---

## 3. Post-Stage Learning Recording (Writing Memory)

When an error is auto-fixed or user approves warnings:
1. Append the resolved learning to the agent's `experiences.json`.
2. Keep the file bounded: retain the top 50 most relevant records to prevent context bloating.
3. Sync any cross-stage discoveries (e.g., Telugu font ligature rendering quirks) into `config/shared_memory.json`.
