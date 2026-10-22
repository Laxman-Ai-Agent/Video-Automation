"""VIDEO_ENGINE/remotion/src/theme.json loaded once: the renderer and these checks read the same numbers (palette, type scale, camera, boxes)."""
import json

from . import config

THEME: dict = json.loads((config.REMOTION_DIR / "src/theme.json").read_text(encoding="utf-8"))
