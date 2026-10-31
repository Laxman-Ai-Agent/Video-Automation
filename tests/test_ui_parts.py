"""The UI parts the scene writer is told about (UI_HINT) are the parts src/ui/index.tsx really exports, and a scene may import them."""
import re
from pathlib import Path

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


def test_an_element_id_passed_to_a_card_helper_counts_as_drawn():
    helper = 'const Card = ({ elementId }: { elementId: string }) => <div data-element-id={elementId} />;\n'
    code = helper + '<Card elementId="owner" /><Card elementId={"free"} />'
    assert ma.missing_element_ids(code, ["owner", "free", "other"]) == ["other"]
    assert ma.missing_element_ids('<Card elementId="owner" />', ["owner"]) == ["owner"]      # no helper renders the prop: not drawn


def test_a_scene_may_import_the_ui_parts():
    src = 'import { GlassPanel, StarField } from "../ui";\nexport default () => null;'
    assert ma.audit_scene_tsx_security(src)["passed"]


def test_the_codegen_rules_ask_for_phone_sized_text_and_filled_first_frames():
    """Polish rules (CODEGEN_VERSION 5): small card labels were unreadable on a phone and shots opened nearly empty."""
    src = Path(ma.__file__).read_text(encoding="utf-8")
    assert "32px on the 1080x1920 canvas" in src and "FILLED FRAMES" in src
    assert int(ma.CODEGEN_VERSION) >= 5


def test_text_under_the_floor_of_the_canvas_is_found_and_a_credit_line_is_exempt():
    code = 'const a = {fontSize: 28};\nconst b = {fontSize: 36};\nconst c = {fontSize: 20}; // credit'
    assert "28" in ma.small_text(code, "9:16")[0] and ma.small_text(code, "16:9") == []
    assert ma.small_text("const a = {fontSize: 32};", "9:16") == []
