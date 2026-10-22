# Audio Analyzer Agent

- **Agent ID:** `audio_analyzer`
- **Stage ID:** `analyzer`
- **Primary Class:** `AudioAnalyzerAgent` (alias `AudioAnalyzerAdapter`)

## Purpose
Transcribes audio with faster-whisper, performs bilingual phonetics review, and detects pauses.

## Capabilities
- `speech-to-text`
- `silence-detection`
- `phonetic-review`

## Bound Tools
- `faster-whisper`
- `silencedetect`
- `llm_client`
- `llm_gateway`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
