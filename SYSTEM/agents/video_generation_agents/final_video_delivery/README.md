# Final Video Delivery Agent

- **Agent ID:** `final_video_delivery`
- **Stage ID:** `final`
- **Primary Class:** `FinalVideoDeliveryAgent` (alias `FinalVideoDeliveryAdapter`)

## Purpose
End-to-end delivery verification, artifact packaging, publishing, and provenance auditing.

## Capabilities
- `artifact-packaging`
- `delivery-verification`
- `provenance-hash-generation`

## Bound Tools
- `store`
- `hasher`
- `notifier`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
