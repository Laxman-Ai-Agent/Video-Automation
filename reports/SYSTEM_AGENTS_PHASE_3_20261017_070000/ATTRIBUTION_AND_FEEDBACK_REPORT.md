# Attribution and Feedback Report: Capability Finder Self-Learning Subsystem

## 1. Causal Attribution Framework

The [OutcomeAnalyzer](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/learning/outcome_analyzer.py) performs structured causal attribution on downstream execution failures. It prevents the system from misattributing external environmental or data issues as capability discovery failures.

### Attribution Decision Matrix

| Execution Outcome Pattern | Primary Failure Category | Discovery Succeeded? | Task Succeeded? | Is Attributable to Capability Finder? | Action Taken by Self-Learning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Task finished with zero errors | `NONE` | `True` | `True` | `True` | Reinforce positive route confidence. |
| `"binary not found in PATH"`, timeout, OOM | `ENVIRONMENTAL` | `True` | `False` | `False` | Ignored; triggers environment alert, not capability routing penalty. |
| `"corrupt header"`, zero bytes, invalid WAV | `INPUT_DEFECT` | `True` | `False` | `False` | Ignored; attributed to upstream stage defect. |
| `"unsupported action"`, `"missing capability"` | `CAPABILITY_MISMATCH` | `False` | `False` | `True` | Attributed to discovery error; eligible for lesson clustering. |
| Missing font, aspect ratio mismatch | `MISSING_CONSTRAINT` | `False` | `False` | `True` | Attributed to constraint mismatch; eligible for constraint override proposal. |
| Unrecognized or ambiguous error detail | `INCONCLUSIVE` | `False` | `False` | `False` | Quarantined; not treated as learning evidence. |

---

## 2. Reviewer Feedback Ingestion and Defense

The [FeedbackProcessor](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/learning/feedback_processor.py) ingests human operator reviews, automated QC feedback, and Main Architecture Agent reflections.

### Defensive Safeguards:
1. **Prompt Injection & Policy Override Detection**:
   Input text is evaluated against compiled regex patterns:
   - `r"ignore\s+(?:all\s+)?prior\s+instructions"`
   - `r"override\s+system\s+policy"`
   - `r"bypass\s+security"`
   Any feedback containing these patterns is immediately assigned status `quarantined` and rejected.
2. **Duplicate Submission Suppression**:
   Feedback is fingerprinted by `(reviewer_id, suggested_action, suggested_delegate_id, notes)`. Duplicate submissions for the same case are rejected.
3. **Accuracy Score Clamping**:
   Reviewer accuracy ratings are bounded between `0.0` and `1.0`.

---

## 3. Anti-Overfitting Evidence Thresholds

The [LessonGenerator](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/learning/lesson_generator.py) aggregates recorded cases and reviewer feedback:
- **Minimum Evidence Threshold**: Requires $\ge 2$ independent supporting cases before a `LessonProposal` candidate is generated.
- **Counterexample Ratio**: A proposal is blocked if counterexamples exceed $\lfloor \text{supporting\_cases} / 2 \rfloor$.
- **Isolated Anomaly Handling**: Single-occurrence reviewer corrections remain marked as `OBSERVED` in history and do not generate proposals until corroborating evidence appears.
