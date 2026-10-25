---
name: dynamic-asset-generator
description: Generate dynamic infographics, data charts via QuickChart, SVG location maps via OpenStreetMap/Nominatim, curate motion sound effects (SFX), and fetch high-res stock photos via Unsplash for video scenes.
---

# Dynamic Asset Generator & Media Toolkit

Use this skill when scene scripts require dynamic data visualizations (charts/infographics), geographic location maps, motion sound effect cues (whooshes, pops, risers), or high-resolution stock photography.

## 1. QuickChart Dynamic Infographics & Charts

When explanatory scenes present statistics, percentages, or growth metrics:

```python
from VIDEO_ENGINE.stages.chart_generator import build_chart_config, render_and_save_chart
from pathlib import Path

# Bar, line, pie, or doughnut chart
config = build_chart_config(
    chart_type="bar",
    labels=["Q1", "Q2", "Q3", "Q4"],
    data=[45.0, 78.5, 92.0, 115.0],
    title="Quarterly Growth",
    label="Revenue (Lakhs)",
    dark_mode=True
)
render_and_save_chart(config, Path("projects/sample-01/assets/collected/chart_growth.png"), width=1280, height=720)
```

### API Endpoint:
- `POST /projects/{pid}/assets/generate-chart`
  - Body: `{"chart_type": "bar", "labels": [...], "data": [...], "title": "...", "dark_mode": true}`

---

## 2. OpenStreetMap & Nominatim Location Maps

When scenes reference countries, cities, or historical locations:

```python
from VIDEO_ENGINE.stages.map_generator import render_location_map
from pathlib import Path

# Generates clean, dark-mode SVG map with location pin and coordinates
render_location_map(
    place_name="Hyderabad, Telangana, India",
    out_svg_path=Path("projects/sample-01/assets/collected/map_hyderabad.svg"),
    width=1280,
    height=720
)
```

### API Endpoint:
- `POST /projects/{pid}/assets/generate-map`
  - Body: `{"place_name": "Hyderabad, India", "width": 1280, "height": 720}`

---

## 3. Motion Sound Effects (SFX) Manager

When kinetic typography, camera zooms, or scene transitions occur:

```python
from VIDEO_ENGINE.stages.sfx_manager import list_builtin_sfx, find_sfx_for_cue

# Retrieve built-in cues: whoosh_fast, pop_clean, impact_sub, chime_bell, riser_tension
sfx_list = list_builtin_sfx()
matched = find_sfx_for_cue("whoosh")
```

### SFX Cues & Composition Track:
- Motion SFX should be aligned with kinetic text transitions in Stage 6 (Composition Engine).
- Standard preset cues:
  - `whoosh_fast`: Fast typography slam or camera whip.
  - `pop_clean`: Icon appearance or list item reveal.
  - `impact_sub`: Dramatic emphasis or key statistic highlight.
  - `chime_bell`: Positive takeaway or conclusion point.
  - `riser_tension`: Climax or cliffhanger question.

---

## 4. Unsplash Stock Media Provider

Unsplash provides editorial and photography assets for visual requirements:
- Ensure `UNSPLASH_ACCESS_KEY` is configured in `.env`.
- Integrates automatically into Stage 5 (`VIDEO_ENGINE/stages/stock.py`) alongside Pexels, Wikimedia Commons, and NASA.
