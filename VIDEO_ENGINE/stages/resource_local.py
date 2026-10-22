"""The project's OWN render components, registered in the Resource Library (docs/resources.md): the plan ranks existing tested code first, so these are entered as `local` resources
(licence LicenseRef-project, pinned by the hash of their source files) instead of being re-imported from anywhere. Registered here: the three background looks, the three SVG charts, four diagram
graphics and two motion components. `sample` is the layer the verification gallery draws for it (a real layer of the existing renderer, never code). The builder tags the layers it makes with
`resource_id` + `resource_sha256` through `adapter.layer_match`; nothing about how they are drawn changes."""
from __future__ import annotations

import json

from . import config, resource_library as rl

BG = ["VIDEO_ENGINE/remotion/src/components/Background.tsx"]
CHART = ["VIDEO_ENGINE/remotion/src/components/Chart.tsx"]
GFX = ["VIDEO_ENGINE/remotion/src/motion/graphics.tsx"]
DIAGRAM = ["VIDEO_ENGINE/remotion/src/motion/graphics.tsx"]            # the drawing; diagram.ts only places it (a change there is checked by motion_checks, not by this hash)
_STAGES = ["motion_planning", "motion_generation", "validation", "timeline", "approval", "render", "qc"]
_DATA = [{"label": "2020", "value": 12}, {"label": "2030", "value": 20}, {"label": "2040", "value": 31}, {"label": "2050", "value": 44}]

# a line chart is thin ink: the verification sample gives it more points and a clear rise and fall, so it is measurable in portrait too (the threshold stays 0.01)
_LINE_DATA = [{"label": str(2020 + 5 * i), "value": v} for i, v in enumerate([8, 31, 14, 40, 22, 46, 18, 50])]

LOCAL: list[dict] = [
    *[{"id": f"background.look.{k}", "name": f"Background look: {k}", "cat": "background", "tags": ["background", "look", k, "gradient", "light"], "files": BG, "adapter": "background-look",
       "entry": "VIDEO_ENGINE/remotion/src/components/Background.tsx", "match": {"type": "background", "look": k}, "deps": [],
       "sample": {"type": "background", "look": k, "seed": "gallery", "colors": ["#0b1220", "#2a9d9f"]}} for k in ("aurora", "mesh", "spotlight")],
    *[{"id": f"chart.svg.{k}", "name": f"SVG chart: {k}", "cat": "chart", "tags": ["chart", k, "data", "svg", "d3"], "files": CHART, "adapter": "svg-chart", "entry": "VIDEO_ENGINE/remotion/src/components/Chart.tsx",
       "match": {"type": "chart", "kind": k}, "deps": ["d3-scale", "d3-shape"], "sample": {"type": "chart", "kind": k, "data": _LINE_DATA if k == "line" else _DATA, "at": 0, "dur": 1.0, "title": "sample"}} for k in ("bar", "line", "pie")],
    *[{"id": f"diagram.{p}", "name": f"Diagram graphic: {p}", "cat": "diagram", "tags": ["diagram", p, "route", "link", "svg"], "files": DIAGRAM, "adapter": "motion-gfx", "entry": "VIDEO_ENGINE/remotion/src/motion/diagram.ts",
       "match": {"type": "motion_gfx", "preset": p}, "deps": [], "sample": {"type": "motion_gfx", "preset": p, "at": 0, "dur": 2.0, "box": [0.1, 0.3, 0.8, 0.4], "data": [1, 1, 1]}}
      for p in ("route-line", "timeline-dots", "node-network", "dashed-flow")],
    {"id": "motion.hud.radar-sweep", "name": "Motion component: radar sweep", "cat": "react_component", "tags": ["hud", "radar", "scan", "motion", "frame-driven"], "files": GFX, "adapter": "motion-gfx",
     "entry": "VIDEO_ENGINE/remotion/src/motion/graphics.tsx", "match": {"type": "motion_gfx", "preset": "radar-sweep"}, "deps": [], "sample": {"type": "motion_gfx", "preset": "radar-sweep", "at": 0, "dur": 2.0, "box": [0.3, 0.2, 0.4, 0.6]}},
    {"id": "effect.cinematic.particles-float", "name": "Effect: floating particles", "cat": "effect", "tags": ["effect", "particles", "cinematic", "seeded", "atmosphere"], "files": GFX, "adapter": "motion-gfx",
     "entry": "VIDEO_ENGINE/remotion/src/motion/graphics.tsx", "match": {"type": "motion_gfx", "preset": "particles-float"}, "deps": [], "sample": {"type": "motion_gfx", "preset": "particles-float", "at": 0, "dur": 2.0, "box": [0, 0, 1, 1], "seed": 7, "k": 7}},
]


def _dep(name: str) -> rl.Dependency:
    p = config.REMOTION_DIR / "node_modules" / name / "package.json"
    j = json.loads(p.read_text(encoding="utf-8"))
    return rl.Dependency(name=name, version=j["version"], direct=True, license=j.get("license"))


def build_entry(d: dict, previous: rl.Entry | None = None) -> rl.Entry:
    """The registry entry of one local component. If the files are unchanged since the previous (verified) entry, that entry is kept as it is (nothing to re-verify)."""
    sha = rl.combined_sha(d["files"])
    if previous and previous.integrity.sha256 == sha and previous.data.get("sample") == d["sample"] and previous.status in ("imported", "verified"):
        return previous
    return rl.Entry(
        resource_id=d["id"], display_name=d["name"], category=d["cat"], tags=d["tags"], status="imported",
        source=rl.Source(kind="local", url="local://" + d["entry"], audit_date=rl.now()[:10]),
        license=rl.License(spdx_id="LicenseRef-project", verified=True, notices_path=None, asset_license_notes="Code written in this project; no third-party material."),
        integrity=rl.Integrity(sha256=sha, pinned=True, source_files=d["files"]),
        dependencies=[_dep(n) for n in d["deps"]],
        compatibility=rl.Compatibility(react=True, remotion=True, node=True, aspect_ratios=["16:9", "9:16"]),
        adapter=rl.Adapter(adapter_id=d["adapter"], entrypoint=d["entry"], props_schema_ref="renderer-layer", animation_presets=[], bounds_supported=True, layer_match=d["match"]),
        usage=rl.Usage(import_mode="local_component", offline_required=True, used_by_pipeline_stages=_STAGES),
        decision=rl.Decision(decision="reference_only", rationale="existing tested project code: registered so its use is tracked, not re-imported", alternatives_considered=[]),
        data={"sample": d["sample"]})


def register() -> dict:
    """Add or refresh the local entries (an entry whose files changed goes back to `imported`: it has to be verified again). Returns what changed."""
    cur = {e.resource_id: e for e in rl.load()}
    new, changed = [], []
    for d in LOCAL:
        e = build_entry(d, cur.get(d["id"]))
        if cur.get(d["id"]) is not e:
            new.append(e)
            changed.append(d["id"])
    if new:
        rl.upsert(new)
        rl.build_bundle()
    return {"registered": changed, "total": len(LOCAL)}
