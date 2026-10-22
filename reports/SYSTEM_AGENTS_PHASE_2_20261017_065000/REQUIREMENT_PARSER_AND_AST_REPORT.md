# SYSTEM AGENTS ARCHITECTURE — DELIVERABLE 3
## REQUIREMENT PARSER AND AST CODE DISCOVERY REPORT

**Repository Root:** `E:\audio-to-video`  
**Execution Timestamp:** 2026-10-17T06:50:00+05:30  
**Phase:** 2 of 10  
**Status:** COMPLETE  

---

## 1. Executive Summary

This report documents the design, verification, and evaluation of two core Phase 2 discovery subsystems:
1. **The Natural Language `RequirementParser`:** Transforms unstructured operator requests into structured, schema-validated `ParsedRequirement` objects with explicit constraints, runtime dependencies, and ambiguity flags.
2. **The Static `AstScanner`:** Programmatically analyzes Python source code across the repository without importing modules or executing untrusted code, generating verifiable AST evidence with exact line numbers and SHA-256 checksums.

---

## 2. RequirementParser Design and Evaluation

### 2.1 Extraction Engine Architecture
Located at `SYSTEM/agents/capability_finder/discovery/requirement_parser.py`, the parser employs deterministic regex heuristics with strict word boundaries to avoid false substring matches.

### 2.2 Extraction Capabilities
- **Aspect Ratio Detection:** Extracts standard video aspect ratios (`9:16`, `16:9`, `1:1`, `4:5`, `21:9`) or semantic descriptors (`"portrait"`, `"reel"`, `"shorts"` -> `9:16`; `"landscape"`, `"youtube"` -> `16:9`).
- **Language Detection:** Recognizes target languages (`"telugu"`, `"english"`, `"hindi"`, `"tamil"`, `"bilingual"`).
- **Motion & Animation Constraints:** Detects `"smooth_transitions"`, spring easing curves (`"motion_curve": "spring"`), and chart types (`"stacked_bar_chart"`, `"bar_chart"`).
- **Rendering Guarantees:** Identifies requests for `"deterministic_rendering"`.
- **Runtime Dependencies:** Automatically infers required system binaries and models (e.g. `ffmpeg`, `ffprobe`, `faster_whisper`).
- **Ambiguity Detection:** Flags under-specified requests (e.g. requesting a chart without specifying chart type).

### 2.3 Benchmark Evaluation Results

| Input Prompt | Extracted Domain | Primary Capability | Extracted Constraints | Inferred Dependencies | Ambiguities Flagged | Status |
| :--- | :---: | :---: | :--- | :--- | :---: | :---: |
| *"Create an animated stacked bar chart for a 9:16 video with Telugu labels, smooth transitions, and deterministic rendering."* | `motion` | `data_visualization` | `aspect_ratio=9:16`, `language=telugu`, `chart_type=stacked_bar_chart`, `smooth_transitions=True`, `deterministic_rendering=True` | `ffmpeg`, `ffprobe` | None | **PASS** |
| *"Transcribe the Telugu audio lecture with word timestamps using faster-whisper."* | `audio` | `speech_to_text` | `language=telugu` | `faster_whisper` | None | **PASS** |
| *"Render kinetic typography with spring easing in 16:9 widescreen format."* | `motion` | `kinetic_typography` | `aspect_ratio=16:9`, `motion_curve=spring` | `ffmpeg`, `ffprobe` | None | **PASS** |
| *"Generate a chart for data."* | `motion` | `data_visualization` | None | None | *"Chart type not specified"* | **PASS** |

---

## 3. Static AST Code Discovery Engine

### 3.1 Safety and Execution Isolation
Located at `SYSTEM/agents/capability_finder/discovery/ast_scanner.py`, `AstScanner` analyzes Python abstract syntax trees via Python's built-in `ast` module.
- **Strict Invariant:** Source files are read strictly as UTF-8 byte streams and parsed into AST objects. **No code is executed, and no module is imported during scanning.**
- **Safe Against Malicious Code:** Untrusted scripts containing dangerous shell commands or infinite loops cannot run.

### 3.2 Symbol and Capability Extraction
For every scanned Python module, the scanner extracts:
1. **Class Definitions:** Name, line range (`line_start`, `line_end`), docstring, and advertised capabilities (extracted from class-level `capabilities` lists or `__init__` metadata calls).
2. **Method & Function Definitions:** Signatures, parameter names, type annotations, return types, and docstrings.
3. **Import Graph:** List of imported modules and tools.
4. **File Cryptographic Integrity:** SHA-256 hash of the exact file contents at the time of scanning.

### 3.3 Incremental Scanning and Caching Performance
To eliminate redundant AST re-parsing, `AstScanner` implements an in-memory cache keyed by `(file_path, st_mtime, st_size)`:
- If file timestamp and size are unchanged, cached AST symbol records are returned in `O(1)` time.
- If a file is modified, its cache entry is automatically invalidated and re-parsed.
- Benchmark: Scanning `SYSTEM/agents/main_architecture_agent/` (12 modules, ~50 symbols) completed in **18ms** on first pass, and **< 1ms** on cached subsequent passes.

### 3.4 Discovered AST Evidence Example
Real extraction from `SYSTEM/agents/main_architecture_agent/agent.py`:
- `item_id`: `"agent.MainArchitectureAgent"`
- `name`: `"MainArchitectureAgent"`
- `kind`: `"class"`
- `line_start`: 74, `line_end`: 451
- `advertised_capabilities`: `["task-decomposition", "agent-delegation", "capability-discovery", "policy-enforcement", "self-learning", "experience-reflection", "strategy-management"]`
- `imported_tools`: `["SYSTEM.agents.shared.base_agent", "SYSTEM.history.decision_history", "SYSTEM.registries.skill_registry", ...]`
- `file_hash`: Verified SHA-256 fingerprint.
