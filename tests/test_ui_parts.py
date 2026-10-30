"""The UI parts the scene writer is told about (UI_HINT) are the parts src/ui/index.tsx really exports, and a scene may import them."""
import re

from SYSTEM.core import config
from VIDEO_ENGINE.stages import motion_animation as ma

UI_SRC = config.REMOTION_DIR / "src" / "ui" / "index.tsx"


def test_every_part_in_the_hint_is_exported():
    exported = set(re.findall(r"export const (\w+)", UI_SRC.read_text(encoding="utf-8")))
    named = set(re.findall(r"<([A-Z]\w+)", ma.UI_HINT))
    assert named and named <= exported, sorted(named - exported)


def test_every_exported_part_is_in_the_hint():
    exported = set(re.findall(r"export const ([A-Z]\w+)", UI_SRC.read_text(encoding="utf-8")))
    assert {n for n in exported if f"<{n}" not in ma.UI_HINT} == set()


def test_a_scene_may_import_the_ui_parts():
    src = 'import { GlassPanel, StarField } from "../ui";\nexport default () => null;'
    assert ma.audit_scene_tsx_security(src)["passed"]
