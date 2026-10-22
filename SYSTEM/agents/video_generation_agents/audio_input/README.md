# Audio Input Agent

- **Agent ID:** `audio_input`
- **Stage ID:** `audio`
- **Primary Class:** `AudioInputAgent` (alias `AudioInputAdapter`)

## Purpose
Ingests source audio, downsamples to 16kHz mono, and extracts duration parameters.

## Capabilities
- `audio-ingest`
- `sample-rate-conversion`
- `ffprobe-metadata`

## Bound Tools
- `ffmpeg`
- `ffprobe`
- `store`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
