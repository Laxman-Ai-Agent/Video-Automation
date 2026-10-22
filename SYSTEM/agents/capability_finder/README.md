# Capability Finder Agent

- **Canonical Path:** `SYSTEM/agents/capability_finder/`
- **Agent ID:** `capability_finder`
- **Category:** `SYSTEM_SUBAGENT`
- **Primary Class:** `CapabilityFinderAgent`
- **Owner:** `system-core`

## Purpose
System agent responsible for discovering registered agents, skills, and tools, as well as inspecting runtime environment prerequisites (FFmpeg, local Whisper weights, etc.).

## Capabilities
- `capability-query`
- `skill-discovery`
- `prerequisite-inspection`

## Allowed Tools
- `agent_registry`
- `skill_registry`
- `tool_registry`
