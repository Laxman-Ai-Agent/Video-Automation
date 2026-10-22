# Final QC Agent

- **Agent ID:** `final_qc`
- **Stage ID:** `qc`
- **Primary Class:** `FinalQcAgent` (alias `FinalQcAdapter`)

## Purpose
Performs comprehensive technical QC (ffprobe, black/freeze frames, A/V sync, audio clipping).

## Capabilities
- `automated-qc`
- `black-frame-detection`
- `freeze-frame-detection`
- `audio-clipping-detection`

## Bound Tools
- `ffprobe`
- `ffmpeg`
- `qc_runner`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
