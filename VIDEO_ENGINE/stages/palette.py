"""Palette and contrast helpers (M9). The numbers come from VIDEO_ENGINE/remotion/src/theme.json, the same file the renderer reads.
python -m backend.palette projects/demo  -> palette warnings for composition.json (also part of plan_checks)."""
import json
import re
import sys

from . import config
from .theme import THEME

HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
COLOR_KEYS = ("color", "fill", "stroke", "markColor")        # layer fields that hold one color
MIN_TEXT_CONTRAST = 4.5                                      # white body text on the base color (WCAG AA)


def norm(c: str) -> str:
    """'#FFF' / '#f2a541' -> '#ffffff' / '#f2a541'."""
    c = c.lower()
    return "#" + "".join(ch * 2 for ch in c[1:]) if len(c) == 4 else c


def _rgb(c: str) -> tuple[int, int, int]:
    c = norm(c)
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def luminance(c: str) -> float:
    """WCAG relative luminance (same formula as theme.ts)."""
    lin = lambda v: v / 12.92 if (v := v / 255) <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4   # noqa: E731
    r, g, b = (lin(v) for v in _rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def roles(palette: list[str]) -> dict[str, str]:
    """base = darkest, accent = brightest of the rest, secondary = the remaining one. Order of the palette does not matter."""
    base, *rest = sorted(palette, key=luminance)
    if not rest:
        return {"base": base, "accent": base, "secondary": base}
    return {"base": base, "accent": rest[-1], "secondary": rest[0] if len(rest) > 1 else rest[-1]}


def layer_colors(comp: dict) -> list[tuple[int, str, str]]:
    """(scene id, layer type, hex color) for every explicit hex color on a layer. rgba()/names are not palette colors."""
    out = []
    for sc in comp["scenes"]:
        for layer in sc["layers"]:
            values = [layer.get(k) for k in COLOR_KEYS] + list(layer.get("colors") or [])
            out += [(sc["id"], layer["type"], norm(v)) for v in values if isinstance(v, str) and HEX.match(v)]
    return out


def check(comp: dict, palette: list[str]) -> list[str]:
    """Warnings: colors outside the palette (plus neutrals), and palettes whose text or accent colors are hard to read."""
    W: list[str] = []
    allowed = {norm(c) for c in palette} | {norm(c) for c in THEME["neutrals"]}
    seen = set()
    for sid, kind, color in layer_colors(comp):
        if color not in allowed and (kind, color) not in seen:
            seen.add((kind, color))
            W.append(f"scene {sid}: {kind} layer uses {color}, which is not in the palette {palette}")
    r = roles(palette)
    if contrast(r["accent"], r["base"]) < THEME["minContrast"]:
        W.append(f"palette: accent {r['accent']} on base {r['base']} has contrast {contrast(r['accent'], r['base']):.1f}:1 (< {THEME['minContrast']}:1)")
    if contrast("#ffffff", r["base"]) < MIN_TEXT_CONTRAST:
        W.append(f"palette: white text on base {r['base']} has contrast {contrast('#ffffff', r['base']):.1f}:1 (< {MIN_TEXT_CONTRAST}:1)")
    return W


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    plan = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    print("roles:", roles(plan["style"]["palette"]))
    warnings = check(comp, plan["style"]["palette"])
    print(*warnings, sep="\n")
    print(f"palette: {len(warnings)} warnings")
