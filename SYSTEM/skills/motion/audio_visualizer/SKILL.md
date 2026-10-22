---
skill_id: motion.audio_visualizer
name: Audio Visualizer (real, from the narration)
domain: motion
version: 1.0.0
summary: Bars/waveform driven by the actual audio with @remotion/media-utils; audio and words come from useSceneData().
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (Remotion License (@remotion/media-utils)).
risk_level: low
capabilities:
  - audio-visualization
  - sound-reactive
dependencies:
  - remotion
  - @remotion/media-utils
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Audio Visualizer

```
import { staticFile, useVideoConfig } from "remotion";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";
import { useSceneData } from "../sceneData";
import { useAbsFrame } from "../sceneContext";
const { audio } = useSceneData();
const frame = useAbsFrame();                       // global frame: the audio starts at frame 0 of the video
const { fps } = useVideoConfig();
const audioData = useAudioData(staticFile(audio as string));   // null while it loads (Remotion waits for it before rendering)
const spectrum = audioData ? visualizeAudio({ audioData, frame, fps, numberOfSamples: 128 }) : [];   // 128 bins across 0-22 kHz, low frequencies first
const bars = spectrum.slice(0, 48);                // speech lives below ~8 kHz: the first 48 bins; the upper bins are almost always near zero
```
- Bars: values are tiny (speech peaks around 0.02 to 0.1), so boost them hard: `height = 14 + Math.min(1, Math.pow(v * 8, 0.6)) * 240`. Without the `* 8` boost the bars stay almost flat. 10 to 14px wide, radius 8, gradient fill, mirrored around the centre line; `numberOfSamples` must be a power of two.
- Smooth look: average the value with the neighbouring bars; keep a constant minimum height so silence still shows a baseline.
- Alternative waveform line: `createSmoothSvgPath` from `@remotion/media-utils` on the bar values.
- Use it behind or under the headline, never over text.
