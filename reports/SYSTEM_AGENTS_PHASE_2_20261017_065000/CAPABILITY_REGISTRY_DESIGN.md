# SYSTEM AGENTS ARCHITECTURE — DELIVERABLE 2
## CAPABILITY REGISTRY DESIGN SPECIFICATION

**Repository Root:** `E:\audio-to-video`  
**Location:** `SYSTEM/registries/capability_registry.py`  
**Execution Timestamp:** 2026-10-17T06:50:00+05:30  
**Phase:** 2 of 10  
**Status:** COMPLETE  

---

## 1. Overview and Architectural Purpose

The central `CapabilityRegistry` serves as the authoritative, cross-domain capability index for the Laxman-Autonomous Master System. 

Prior to Phase 2, capability discovery was fragmented:
- `AgentRegistry` held metadata for 17 discrete agents.
- `SkillRegistry` tracked versioned skills in `catalog.json`.
- `ToolRegistry` tracked system-level execution utilities.
- There was no unified index allowing the `MainArchitectureAgent` or `CapabilityFinderAgent` to search across all three domains simultaneously or trace code-level implementation provenance.

The `CapabilityRegistry` bridges these domains **without duplicating their authority**:
- `AgentRegistry` remains the sole authority on agent lifecycles.
- `SkillRegistry` remains the sole authority on skill validation and staging.
- `ToolRegistry` remains the sole authority on executable tool permissions.
- `CapabilityRegistry` indexes the capabilities advertised by each, linking them with structured metadata, verification states, and provenance references.

---

## 2. Canonical Data Model

### 2.1 Field Specification
The `CapabilityRecord` dataclass is defined in `SYSTEM/registries/capability_registry.py`:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `capability_id` | `str` | Globally unique, stable identifier (e.g. `agent.audio_input.speech_to_text`, `skill.motion.kinetic_typography`). |
| `name` | `str` | Human-readable capability title. |
| `description` | `str` | Technical description of the functionality provided. |
| `source_type` | `CapabilitySourceType` | Origin category: `"agent"`, `"skill"`, `"tool"`, `"ast_discovered"`, `"external"`. |
| `source_id` | `str` | Identifier of the originating entity (e.g. `"audio_input"`, `"ffmpeg"`). |
| `source_path` | `str` | Relative file path or entrypoint to implementation. |
| `domain` | `str` | Functional domain: `"audio"`, `"visual"`, `"motion"`, `"timeline"`, `"qc"`, `"system"`, `"general"`. |
| `tags` | `list[str]` | Normalized indexing tags. |
| `keywords` | `list[str]` | Searchable keywords and terms. |
| `input_contract` | `dict[str, Any]` | Expected input parameters and data types. |
| `output_contract` | `dict[str, Any]` | Generated output artifacts and return schemas. |
| `dependencies` | `list[str]` | Required tools or libraries. |
| `constraints` | `dict[str, Any]` | Operational limitations (e.g. `risk_level`, `is_frozen`, `permission_level`). |
| `provenance` | `str` | Tracking origin (`"agent_registry"`, `"skill_registry"`, `"tool_registry"`, `"ast_scanner"`). |
| `verification_status` | `CapabilityVerificationStatus` | Verification lifecycle state: `"registered"`, `"discovered"`, `"verified"`, `"deprecated"`. |
| `evidence_refs` | `list[dict[str, Any]]` | Cryptographic evidence, SHA-256 hashes, file line ranges. |
| `first_seen_at` | `str` | ISO-8601 UTC timestamp of creation. |
| `last_inspected_at` | `str` | ISO-8601 UTC timestamp of latest inspection. |
| `last_verified_at` | `str \| None` | ISO-8601 UTC timestamp of test verification. |
| `schema_version` | `int` | Record schema version (currently `1`). |

### 2.2 Verification Statuses
- **`registered`**: Capability is declared in an authoritative registry but has not been exercised by an end-to-end integration test.
- **`discovered`**: Found during static AST analysis of the codebase.
- **`verified`**: The backing entity (e.g., approved skill or passing agent) has successfully passed its validation test suite.
- **`deprecated`**: Outdated capability maintained for legacy backwards compatibility.

---

## 3. Safe Cross-Domain Synchronization

The `sync_with_registries()` method executes an idempotent cross-domain scan:

```mermaid
sequenceDiagram
    participant CR as CapabilityRegistry
    participant AR as AgentRegistry
    participant SR as SkillRegistry
    participant TR as ToolRegistry

    CR->>AR: list_all_agents()
    AR-->>CR: 17 AgentMetadata records
    Note over CR: Upsert agent.* capabilities with allowed_tools dependencies

    CR->>SR: list_skills(status=None)
    SR-->>CR: Approved & review_required SkillRecords
    Note over CR: Upsert skill.* capabilities; preserve draft/quarantine states

    CR->>TR: list_tools()
    TR-->>CR: 9 ToolDefinition records
    Note over CR: Upsert tool.* capabilities with permission levels

    CR-->>CR: Rebuild tag, domain, and source indexes
```

### Safety Invariants
1. **Zero Side Effects on Source Registries:** Reading from `AgentRegistry`, `SkillRegistry`, and `ToolRegistry` does not mutate their records, disk files, or configuration.
2. **Quarantine Confinement:** Skills in `quarantined` or `draft` state are not promoted to `verified` capability records.
3. **Circular Import Protection:** Registries are imported dynamically inside methods or via lazy properties, preventing circular initialization chains between `agent_registry` and `capability_finder`.

---

## 4. Querying and Indexing Performance

`CapabilityRegistry` maintains secondary in-memory indexes using Python sets:
- `_tag_index: dict[str, set[str]]` (maps lowercase tag to capability IDs)
- `_domain_index: dict[str, set[str]]` (maps lowercase domain to capability IDs)
- `_source_index: dict[str, set[str]]` (maps source type to capability IDs)

The `search_capabilities()` method supports composable filters:
- Filter by exact `domain` (e.g. `domain="motion"`)
- Filter by exact `source_type` (e.g. `source_type="skill"`)
- Filter by `verification_status` (e.g. `verification_status="verified"`)
- Tag intersection matching (e.g. `tags=["typography", "animation"]`)
- Keyword and full-text substring search across corpus (`capability_id`, `name`, `description`, `keywords`, `tags`)
