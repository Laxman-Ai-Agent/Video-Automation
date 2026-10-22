# Experience Memory Report: Capability Finder Self-Learning Subsystem

## 1. Purpose and Storage Format

The Capability Finder's experience memory records discovery decisions and downstream execution outcomes in an immutable, append-only JSONL format:
- **Location**: `SYSTEM/agents/capability_finder/history/cases.jsonl`
- **Concurrency Control**: Protected by a global reentrant thread lock (`threading.RLock`) ensuring safe concurrent writes across pipeline agents.
- **Indexation**: Dual in-memory hash maps indexing cases by both `case_id` (prefixed `lcase_`) and `task_id` / `correlation_id` for $O(1)$ lookups.

---

## 2. LearningCase Schema Definition

The experience memory record adheres strictly to [learning_case.schema.json](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/schemas/learning_case.schema.json):

```json
{
  "case_id": "lcase_3fa85f64c92a",
  "schema_version": 1,
  "task_id": "task_20261017_001",
  "correlation_id": "corr_98124",
  "agent_id": "capability_finder",
  "project_id": "proj_demo",
  "timestamp": "2026-10-17T07:15:00+00:00",
  "query": "Transcribe audio speech to text with timestamps",
  "parsed_requirement": {
    "domain": "audio",
    "primary_capability": "speech_to_text",
    "constraints": {"timestamps": true}
  },
  "candidates_considered": [
    {"source_id": "tool.faster_whisper.speech_to_text", "score": 0.85}
  ],
  "decision_recommendation": "REUSE",
  "suggested_delegate_id": "tool.faster_whisper.speech_to_text",
  "actual_outcome": "succeeded",
  "outcome_detail": "Execution completed in 2.3s with 120 words transcribed",
  "verification_status": "passed",
  "reviewer_feedback": [],
  "applied_knowledge_version": "1.0.0",
  "is_redacted": true
}
```

---

## 3. Secret and Credential Sanitization Engine

All cases recorded through `CaseCollector.record_case()` pass through a deterministic secret scrubbing engine before being written to disk:

```python
SECRET_PATTERNS = [
    (re.compile(r'(?:sk-[a-zA-Z0-9_-]{20,})'), "[REDACTED_API_KEY]"),
    (re.compile(r'(?:ghp_[a-zA-Z0-9]{20,})'), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]{16,}', re.IGNORECASE), "Bearer [REDACTED_BEARER]"),
    (re.compile(r'(?:api_key|apiKey|password|secret|token|pin)\s*=\s*[^\s&;]+', re.IGNORECASE), "secret=[REDACTED]"),
]
```

Unit test evidence in [test_learning_cases.py](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/tests/test_learning_cases.py) confirms that API keys, passwords, PINs, and Bearer tokens are scrubbed without altering requirement semantics.
