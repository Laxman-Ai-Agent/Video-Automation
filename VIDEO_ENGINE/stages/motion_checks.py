"""Motion rules (M9): camera limits and effect timing. python -m backend.motion_checks projects/demo
Camera: slow moves only (docs/rules.md: 1.0 -> ~1.12), a focus point away from the edge. Effects: only at emphasis moments."""
import json
import sys

from . import config
from .theme import THEME

CAM = THEME["camera"]
MAX_PARTICLES = 60          # VIDEO_ENGINE/remotion/src/components/Effect.tsx clamps to this
MAX_EFFECTS_PER_SCENE = 2
MAX_EFFECT_SECONDS = 4.0    # a short accent; particles may drift longer (they are ambient)
NEAR_EVENT = 0.8            # an effect must start within this many seconds of an emphasis event
NON_EVENT_LAYERS = {"effect", "image", "background", "stock-video", "light-leak", "shape", "map", "chart"}


def camera_warnings(comp: dict) -> list[str]:
    W: list[str] = []
    for sc in comp["scenes"]:
        cam = sc.get("camera") or {}
        move, lo, hi = cam.get("move", "static"), cam.get("from", 1.0), cam.get("to", 1.0)
        limit = CAM["focusScale"] if move == "zoom-to-focus" else CAM["maxScale"]
        if max(lo, hi) > limit + 1e-9:
            W.append(f"scene {sc['id']}: camera zoom {max(lo, hi)} is above {limit} (slow moves only)")
        if min(lo, hi) < 1.0 - 1e-9:
            W.append(f"scene {sc['id']}: camera scale {min(lo, hi)} is below 1 and would show the frame edge")
        fx, fy = cam.get("focus", [0.5, 0.5])
        if not (0.15 <= fx <= 0.85 and 0.15 <= fy <= 0.85) and move != "static":
            W.append(f"scene {sc['id']}: camera focus {[fx, fy]} is close to the edge; the {move} would crop the subject")
        if not 0 <= cam.get("drift", 0) <= 1:
            W.append(f"scene {sc['id']}: camera.drift {cam['drift']} must be between 0 and 1")
    return W


def effect_warnings(comp: dict, plan: dict) -> list[str]:
    """Effects belong to emphasis moments: a keyword being spoken, or another layer (icon, text, counter ...) entering."""
    W: list[str] = []
    keywords = {s["id"]: [k["at"] for k in s.get("keywords", [])] for s in plan["scenes"]}
    for sc in comp["scenes"]:
        effects = [l for l in sc["layers"] if l["type"] == "effect"]
        events = list(keywords.get(sc["id"], []))
        for l in sc["layers"]:
            if l["type"] not in NON_EVENT_LAYERS:
                events += [t for t in (l.get("at"), (l.get("enter") or {}).get("at")) if isinstance(t, (int, float))]
        if len(effects) > MAX_EFFECTS_PER_SCENE:
            W.append(f"scene {sc['id']}: {len(effects)} effects (max {MAX_EFFECTS_PER_SCENE}); effects only at emphasis moments")
        for l in effects:
            name, at = l.get("name"), l.get("at", 0)
            if name == "particles" and l.get("count", 40) > MAX_PARTICLES:
                W.append(f"scene {sc['id']}: particles count {l['count']} is capped at {MAX_PARTICLES}")
            if name != "particles" and l.get("dur", 1.2) > MAX_EFFECT_SECONDS:
                W.append(f"scene {sc['id']}: {name} effect lasts {l['dur']:.1f}s (accents are short, default 1.2s)")
            if not any(abs(at - t) <= NEAR_EVENT for t in events):
                W.append(f"scene {sc['id']}: {name} effect at {at:.2f}s is not near a keyword or an entering element")
    return W


def check(comp: dict, plan: dict) -> list[str]:
    return camera_warnings(comp) + effect_warnings(comp, plan)


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    warnings = check(json.loads((pdir / "composition.json").read_text(encoding="utf-8")),
                     json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8")))
    print(*warnings, sep="\n")
    print(f"motion_checks: {len(warnings)} warnings")
