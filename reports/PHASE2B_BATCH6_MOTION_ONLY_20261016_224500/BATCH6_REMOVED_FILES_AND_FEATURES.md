# Phase 2B — Batch 6: Removed Files and Obsolete Features Inventory

- **Date/Time**: 2026-10-16 22:45:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Scope**: Documentation of deleted files, functions, legacy features, and their former responsibilities

---

## 1. Overview of Removed Files

A total of 9 file instances (representing 4 dead logical subsystems plus 1 bridge file) were permanently deleted in Batch 6:

```text
backend/
├── bg_remove.py               [DELETED]
├── fill_slots.py              [DELETED]
├── image_gate.py              [DELETED]
└── prompts_writer.py          [DELETED]

UI/
└── backend/
    └── fill_slots.py          [DELETED]

VIDEO_ENGINE/
└── stages/
    ├── bg_remove.py           [DELETED]
    ├── fill_slots.py          [DELETED]
    ├── image_gate.py          [DELETED]
    └── prompts_writer.py      [DELETED]
```

---

## 2. Detailed Technical Breakdown of Removed Modules

### 2.1 `image_gate.py`
- **Former Path**: `backend/image_gate.py`, `VIDEO_ENGINE/stages/image_gate.py`
- **Line Count**: 126 lines
- **Primary Exports**: `status(pdir, uploads)`, `can_continue(pdir)`
- **Former Purpose**:
  - Implemented the verification gate for legacy Image Generation.
  - Read `match_report.json` and computed whether each required prompt slot had an assigned image (`matched`, `review`, `missing`, or `failed`).
  - Blocked pipeline execution until all image slots had valid image assignments.
- **Why It is Obsolete**:
  - The pipeline has permanently shifted to Motion-Only mode (`use_images: false`).
  - Motion graphics, animation templates, and programmatic Remotion compositions do not use image prompt gates.

### 2.2 `bg_remove.py`
- **Former Path**: `backend/bg_remove.py`, `VIDEO_ENGINE/stages/bg_remove.py`
- **Line Count**: 52 lines
- **Primary Exports**: `cutout(src, dst)`, `_white_key(rgb)`
- **Former Purpose**:
  - Used `rembg` (with `u2netp.onnx`) or OpenCV border flood-filling (`_white_key`) to strip backgrounds from stock photos for "icon" and "object" visual roles.
  - Wrote cutouts to `assets/cutouts/NN.png`.
- **Why It is Obsolete**:
  - Motion graphics are generated with vector shapes, CSS animations, and Remotion components.
  - No raster cutouts are ingested or rendered.

### 2.3 `fill_slots.py`
- **Former Path**: `backend/fill_slots.py`, `VIDEO_ENGINE/stages/fill_slots.py`, `UI/backend/fill_slots.py`
- **Line Count**: 122 lines
- **Primary Exports**: `fill(pdir, aspect)`, `empty_scenes(comp)`
- **Former Purpose**:
  - Injected matched image file paths and camera pan/zoom crop coordinates (`crops.json`) into `composition.json` and `composition_9x16.json`.
  - Copied images to `remotion/public/projects/<pid>/`.
- **Why It is Obsolete**:
  - Motion scenes do not rely on external slot filling from `match_report.json`.
  - Scenes render Remotion component code directly via `remotion/src/scenes/` and `remotion/src/generated/`.

### 2.4 `prompts_writer.py`
- **Former Path**: `backend/prompts_writer.py`, `VIDEO_ENGINE/stages/prompts_writer.py`
- **Line Count**: 29 lines
- **Primary Exports**: `build(pdir)`, `WHITE_BG`
- **Former Purpose**:
  - Formatted text prompts into a numbered `prompts.txt` file for external image generator models (Midjourney, DALL-E, SD).
  - Appended style suffixes (e.g., `, photographic, 16:9`) and white background tags.
- **Why It is Obsolete**:
  - The Motion-Only workflow does not generate image prompts.
  - Prompt planning focuses exclusively on visual storytelling, motion scene parameters, and code generation schemas.

---

## 3. Preserved Features and Critical Exceptions

### `motion_template_selection.py` (PRESERVED)
- **Path**: `VIDEO_ENGINE/stages/motion_template_selection.py` & `backend/motion_template_selection.py`
- **Audit Findings**:
  - An earlier audit loosely flagged this module as a candidate for deletion because the UI page `MotionTemplateSelectionPage.tsx` was deprecated.
  - However, in-depth architectural analysis revealed that the backend module is **actively required** by Stage 5 of the Motion Generation pipeline.
  - It manages the routing logic determining whether a scene should use a prebuilt template or trigger Claude-assisted custom React/Remotion code generation (`motion_codegen.py`).
  - It is imported by `motion_animation.py`, tested by `tests/test_motion_codegen.py` (which passed 7/7 tests), referenced in `motion_validation_rules.py`, and registered in `SYSTEM/agents/system_agents/capability_finder/agent_registry.py`.
- **Resolution**: **STRICTLY PRESERVED**. It is a core component of the Motion-Only engine.
