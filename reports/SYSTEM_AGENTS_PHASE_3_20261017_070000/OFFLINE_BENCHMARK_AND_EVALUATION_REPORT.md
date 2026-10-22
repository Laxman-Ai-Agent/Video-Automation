# Offline Benchmark and Evaluation Report: Capability Finder Self-Learning Subsystem

## 1. BENCHMARK_V1 Suite Specification

The offline benchmark suite [BENCHMARK_V1](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/learning/lesson_evaluator.py) provides a deterministic, fixed test suite of 10 representative scenarios across audio, motion, visual, media, validation, and agent domains:

| Scenario ID | Task Query Description | Domain | Expected Action | Expected Delegate |
| :--- | :--- | :--- | :--- | :--- |
| `bench_01_speech_to_text` | Speech to text transcription with word-level timestamps | `audio` | `REUSE` | `tool.faster_whisper.speech_to_text` |
| `bench_02_kinetic_typography` | Kinetic typography layout and text animations | `motion` | `REUSE` | `skill.motion.kinetic_typography.typography_layout` |
| `bench_03_loudness_normalize` | Media audio loudness normalization to EBU standards | `media` | `REUSE` | `tool.ffmpeg.audio_normalize` |
| `bench_04_spring_physics` | Remotion spring physics and curve math interpolation | `motion` | `REUSE` | `skill.motion.remotion_spring_curves.spring_physics` |
| `bench_05_safe_zone_validation`| Layout safe zones and collision boundary detection | `validation` | `REUSE` | `skill.validation.layout_safe_zones.safe_zone_validation` |
| `bench_06_scene_segmentation` | Video scene cut detection and segmentation | `visual` | `REUSE` | `agent.split_scenes.scene_segmentation` |
| `bench_07_custom_particle_glsl`| Custom GLSL particle emitter shader (new skill) | `motion` | `CREATE_SKILL` | `skill_factory` |
| `bench_08_3d_avatar_agent` | Full 3D autonomous talking avatar system (new agent) | `avatar` | `CREATE_AGENT` | `main_architecture_agent` |
| `bench_09_watermark_inpaint` | Video watermark removal inpainting filter (new skill) | `visual` | `CREATE_SKILL` | `skill_factory` |
| `bench_10_neural_voice_agent` | End-to-end neural voice cloning model (new agent) | `orchestrator` | `CREATE_AGENT` | `main_architecture_agent` |

---

## 2. Benchmark Metrics and Non-Regression Equations

For any evaluation run, [LessonEvaluator](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/learning/lesson_evaluator.py) computes:

1. **Recommendation Accuracy**:
   $$\text{Accuracy} = \frac{N_{\text{correct}}}{N_{\text{total}}}$$
2. **False Reuse Rate**:
   $$\text{FRR} = \frac{N_{\text{actual}=\text{REUSE} \land \text{expected}\in\{\text{CREATE\_SKILL}, \text{CREATE\_AGENT}\}}}{N_{\text{expected}\in\{\text{CREATE\_SKILL}, \text{CREATE\_AGENT}\}}}$$
3. **False Creation Rate**:
   $$\text{FCR} = \frac{N_{\text{actual}\in\{\text{CREATE\_SKILL}, \text{CREATE\_AGENT}\} \land \text{expected}=\text{REUSE}}}{N_{\text{expected}=\text{REUSE}}}$$

### Baseline Metrics (Version 1.0.0):
- **Total Scenarios**: 10
- **Recommendation Accuracy**: 0.8000 (8 / 10)
- **False Reuse Rate**: 0.0000 (0 / 4)
- **False Creation Rate**: 0.0000 (0 / 6)

---

## 3. Candidate Proposal Evaluation and Regression Gate

When a candidate `LessonProposal` is evaluated:
- **Accuracy Delta**: $\Delta \text{Acc} = \text{Accuracy}_{\text{candidate}} - \text{Accuracy}_{\text{baseline}}$
- **Regression Detection**: A candidate triggers `has_regression = True` and fails the gate if:
  1. $\Delta \text{Acc} < 0.0$ (accuracy drops).
  2. $\text{FRR}_{\text{candidate}} > \text{FRR}_{\text{baseline}}$ (false reuse increases).
  3. $\text{FCR}_{\text{candidate}} > \text{FCR}_{\text{baseline}}$ (false creation increases).

Unit tests in [test_lesson_evaluator.py](file:///E:/audio-to-video/SYSTEM/agents/capability_finder/tests/test_lesson_evaluator.py) verify that improving proposals achieve $\Delta \text{Acc} \ge +0.1000$ and pass the gate, while regressive proposals are rejected.
