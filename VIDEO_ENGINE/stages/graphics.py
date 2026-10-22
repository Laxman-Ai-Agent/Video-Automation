"""Video graphics that stay readable on a photo (A2V_ICONS=1): every icon gets the shared dark backing panel (VIDEO_ENGINE/remotion/src/theme.json "backing"), and a
number callout (counter) gets it when its scene shows a picture. Measured in the real renderer (tests/test_improve_p5.py): a bare amber icon on the
sample photos has a contrast of 2.5-2.8:1, below the 3:1 a graphic needs; with the backing it is well above. Nothing else about the layers changes."""


def apply_graphics(comp: dict) -> int:
    """Set `backing: true` where it is needed. Returns how many layers changed. Safe to run twice."""
    changed = 0
    for s in comp["scenes"]:
        has_photo = any(l.get("type") == "image" and l.get("file") for l in s["layers"])
        for l in s["layers"]:
            wants = l.get("type") == "icon" or (l.get("type") == "counter" and has_photo)
            if wants and l.get("backing") is not True and l.get("enabled") is not False:
                l["backing"] = True
                changed += 1
    return changed
