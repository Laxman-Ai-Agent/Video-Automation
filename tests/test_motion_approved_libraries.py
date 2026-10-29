"""Generated scenes may import only the approved, frame-safe libraries (no 3D / WebGL); the design skills are registered; the codegen prompt names the libraries."""
import json
from pathlib import Path

from backend import llm_gateway, motion_animation as ma, skill_registry

GOOD = '''import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Bar } from "@nivo/bar";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { Brain } from "@phosphor-icons/react";
import { siGithub } from "simple-icons";
import { interpolate } from "flubber";
import { slateDark } from "@radix-ui/colors";
import { FONT } from "../fonts";
'''


def test_approved_libraries_pass_and_others_are_rejected():
    assert ma.unapproved_imports(GOOD) == []
    assert ma.audit_scene_tsx_security(GOOD)["passed"]
    bad = 'import l from "left-pad";\nimport * as e from "echarts";\nimport * as T from "three";\nimport f from "flag-icons/flags/4x3/in.svg";\n'
    assert ma.unapproved_imports(bad) == ["echarts", "left-pad", "three"]          # the flag file is part of an approved package; bare echarts (canvas/WebGL parts) is not
    # every data file the design skills tell the LLM to import must pass the audit (the skills and the allowlist must not contradict each other)
    assert ma.unapproved_imports('import world from "world-atlas/countries-110m.json"; import f from "flag-icons/flags/4x3/in.svg";') == []
    res = ma.audit_scene_tsx_security(bad)
    assert not res["passed"] and any("Unapproved library import" in f for f in res["findings"])


def test_every_approved_library_is_installed():
    pkg = json.loads((Path(__file__).resolve().parent.parent / "VIDEO_ENGINE" / "remotion" / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg["dependencies"], **pkg.get("devDependencies", {})}
    pkg_of = lambda a: "/".join(a.split("/")[:2]) if a.startswith("@") else a.split("/")[0]       # "@remotion/transitions/fade" belongs to "@remotion/transitions"
    missing = [a for a in ma.APPROVED_IMPORTS if a != "react/jsx-runtime" and pkg_of(a) not in deps]
    assert missing == [], f"approved in the audit but not installed: {missing}"
    assert "echarts" in deps


def test_design_skills_are_registered_for_the_motion_agent():
    ids = {s.skill_id for s in skill_registry.registry.search_skills(domain="motion", status="approved")}
    assert {"motion.design_kit", "motion.charts_nivo_echarts", "motion.icons_logos", "motion.svg_morph_paths", "motion.lottie_overlays", "motion.diagrams_layout"} <= ids


def test_the_codegen_prompt_names_the_approved_libraries(tmp_path, monkeypatch):
    seen = []

    def execute(req):
        seen.append(req)
        raise RuntimeError("stop")
    monkeypatch.setattr(llm_gateway.gateway, "execute", execute)
    try:
        ma.generate_scene_tsx_via_llm(tmp_path, 1, 3.0, "Title", "Sub", [], ["#0f172a"], "16:9")
    except ma.AnimationCodegenError:
        pass
    prompt = seen[0].system_prompt
    assert "@nivo/*" in prompt and "echarts/core" in prompt and "no 3D" in prompt and "frame" in prompt


# ---- compile-error repair: type errors of a generated scene go back to the LLM; the stage still fails closed when they cannot be fixed ----
import importlib

import pytest

from backend import store

_mp = importlib.import_module("test_motion_planning")


def test_compiler_errors_are_grouped_by_scene():
    out = ("src/generated/scene_1.tsx(327,13): error TS2322: Type X is not assignable.\n  Property 'minValue' does not exist on type 'Y'.\n"
           "src/generated/scene_2.tsx(10,5): error TS2304: Cannot find name 'Foo'.\nsrc/other.ts(1,1): error TS1000: not a scene")
    got = ma.tsc_errors_by_scene(out)
    assert set(got) == {"1", "2"} and "minValue" in got["1"][0] and got["2"][0].startswith("line 10: TS2304")


def test_the_type_check_pins_a_plain_output_so_its_errors_can_be_parsed(tmp_path, monkeypatch):
    """With FORCE_COLOR in the environment tsc prints a coloured `file:line:col - error` layout that no compile error of a scene could be parsed from, so the repair loop never ran."""
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(cmd=cmd, env=kw["env"])
        return type("R", (), {"returncode": 1, "stdout": "src/generated/scene_2.tsx(3,10): error TS2305: no member\n", "stderr": ""})()
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setattr(ma.subprocess, "run", fake_run)
    ok, out = ma.run_tsc(tmp_path)
    assert not ok and "--pretty false" in seen["cmd"] and seen["env"]["FORCE_COLOR"] == "0" and seen["env"]["NO_COLOR"] == "1"
    assert set(ma.tsc_errors_by_scene(out)) == {"2"}


def _project(tmp_path):
    d, *_ = _mp.make(tmp_path / "proj_tsc")
    store.set_reusable_motion_templates(d, False)
    return d


def test_a_type_error_is_sent_back_to_the_llm_and_recompiled(tmp_path, monkeypatch):
    d = _project(tmp_path)
    results = iter([(False, "src/generated/scene_1.tsx(3,1): error TS2322: bad prop\n"), (True, "")])
    monkeypatch.setattr(ma, "run_tsc", lambda remotion_dir: next(results))
    repairs = []
    monkeypatch.setattr(ma, "repair_scene_compile_errors", lambda pdir, sid, code, errs, motion_kit=False: repairs.append((sid, errs)) or code + "\n// fixed\n")
    manifest = ma.generate_custom_motion_code(d, "16:9")
    assert [r[0] for r in repairs] == ["1"] and "bad prop" in repairs[0][1][0]
    assert manifest["status"] == "generated" and manifest["scenes"][0]["generation"]["compile_repairs"] == 1
    assert "// fixed" in (d / "generated_motion" / "scene_1.tsx").read_text(encoding="utf-8")


def test_a_type_error_that_cannot_be_repaired_fails_the_stage(tmp_path, monkeypatch):
    d = _project(tmp_path)
    monkeypatch.setattr(ma, "run_tsc", lambda remotion_dir: (False, "src/generated/scene_1.tsx(3,1): error TS2322: bad prop\n"))
    monkeypatch.setattr(ma, "repair_scene_compile_errors", lambda *a: None)
    with pytest.raises(ma.AnimationCodegenError, match="TypeScript compilation failed"):
        ma.generate_custom_motion_code(d, "16:9")


RUNTIME_ERROR = "runtime error while the scene was drawn at frame 9: Error  inputRange must be strictly monotonically increasing but got [1,1]"


def test_a_scene_that_throws_when_drawn_is_sent_back_to_the_llm_and_drawn_again(tmp_path, monkeypatch):
    """The type check passes, the scene still throws at runtime (interpolate with an input range of [1, 1]): the error goes to the same repair as a compiler error."""
    d = _project(tmp_path)
    monkeypatch.setattr(ma, "run_tsc", lambda remotion_dir: (True, ""))
    results = iter([{"1": [RUNTIME_ERROR]}, {}])
    monkeypatch.setattr(ma, "render_errors_by_scene", lambda *a: next(results))
    repairs = []
    monkeypatch.setattr(ma, "repair_scene_compile_errors", lambda pdir, sid, code, errs, motion_kit=False: repairs.append((sid, errs)) or code + "\n// fixed\n")
    manifest = ma.generate_custom_motion_code(d, "16:9")
    assert [r[0] for r in repairs] == ["1"] and "inputRange" in repairs[0][1][0]
    assert manifest["status"] == "generated" and manifest["scenes"][0]["generation"]["compile_repairs"] == 1
    assert "// fixed" in (d / "generated_motion" / "scene_1.tsx").read_text(encoding="utf-8")


def test_a_scene_that_throws_when_drawn_and_cannot_be_repaired_fails_the_stage(tmp_path, monkeypatch):
    d = _project(tmp_path)
    monkeypatch.setattr(ma, "run_tsc", lambda remotion_dir: (True, ""))
    monkeypatch.setattr(ma, "render_errors_by_scene", lambda *a: {"1": [RUNTIME_ERROR]})
    monkeypatch.setattr(ma, "repair_scene_compile_errors", lambda *a: None)
    with pytest.raises(ma.AnimationCodegenError, match="fails when it is drawn: scene 1: runtime error.*inputRange"):
        ma.generate_custom_motion_code(d, "16:9")


def test_the_render_check_can_be_turned_off_and_a_check_that_cannot_run_fails_closed(tmp_path, monkeypatch):
    pv = importlib.import_module("VIDEO_ENGINE.stages.motion_validation_preview")
    assert ma.render_errors_by_scene(tmp_path, "9:16", [], []) == {}                  # MOTION_RENDER_CHECK=0 (the suite's default): nothing is drawn
    monkeypatch.setenv("MOTION_RENDER_CHECK", "1")
    monkeypatch.setattr(ma, "custom_composition", lambda *a: {})
    monkeypatch.setattr(pv, "smoke", lambda *a: (_ for _ in ()).throw(pv.ValidationError("the Remotion bundle could not be made")))
    with pytest.raises(ma.AnimationCodegenError, match="render check of the generated scenes could not run"):
        ma.render_errors_by_scene(tmp_path, "9:16", [], [])


def test_the_smoke_render_draws_one_still_per_scene_once_and_names_the_scene_that_throws(tmp_path, monkeypatch):
    import contextlib
    import types
    pv = importlib.import_module("VIDEO_ENGINE.stages.motion_validation_preview")
    monkeypatch.setattr(pv, "_pipeline_modules", lambda: (types.SimpleNamespace(cleaned_after=contextlib.nullcontext), types.SimpleNamespace(RENDER_LOCK=contextlib.nullcontext()), None))
    monkeypatch.setattr(importlib.import_module("VIDEO_ENGINE.stages.render"), "stage_audio", lambda *a: None)
    monkeypatch.setattr(importlib.import_module("VIDEO_ENGINE.stages.asset_collection"), "stage_assets", lambda *a: None)
    monkeypatch.setattr(pv, "_bundle", lambda dest: None)
    drawn = []

    def still(bundle, comp_file, frame, dest, attempts=pv.ATTEMPTS):
        drawn.append((frame, attempts))
        if frame == 90:
            raise pv.ValidationError(f"the still at frame {frame} could not be rendered after {attempts} tries:  Error  inputRange must be strictly monotonically increasing but got [1,1]")
    monkeypatch.setattr(pv, "_still", still)
    comp = {"meta": {"fps": 30}, "scenes": [{"id": 1, "start": 0, "end": 2}, {"id": 2, "start": 2, "end": 4}]}
    errors = pv.smoke(tmp_path, "9:16", comp)
    assert drawn == [(30, 1), (90, 1)]                                                  # the middle of each scene, one try each (a real error fails every time)
    assert list(errors) == ["2"] and "frame 90" in errors["2"][0] and "inputRange" in errors["2"][0]


def test_a_scenes_own_helper_named_like_a_legacy_preset_is_not_a_prohibited_preset():
    """A scene's own `Counter`/`Chart` component (or the word in text/comments) is fine; importing or using the legacy preset is not."""
    own = 'const Counter: React.FC = () => <div>Chart of growth</div>;\nexport const Scene1 = () => <Counter />; // Chart\n'
    assert ma.scan_prohibited_presets(own) == []
    assert ma.scan_prohibited_presets('import { Chart } from "../components/Chart";') == ["Chart"]
    assert ma.scan_prohibited_presets('import {\n  Counter,\n} from "../components/x";') == ["Counter"]
    assert ma.scan_prohibited_presets('export const S = () => <Callout text="x" />;') == ["Callout"]


# ---- Lottie: every file has a licence record; the prompt lists them; unlisted files are rejected ----
def test_every_lottie_file_has_a_licence_record_and_is_small_and_self_contained():
    lot = Path(__file__).resolve().parent.parent / "VIDEO_ENGINE" / "remotion" / "src" / "lottie"
    listed = ma.lottie_manifest()
    assert {a["file"] for a in listed} == {f.name for f in lot.glob("*.json") if f.name != "manifest.json"}, "every Lottie file must be in manifest.json (and the reverse)"
    for a in listed:
        data = json.loads((lot / a["file"]).read_text(encoding="utf-8"))
        assert a["license"] and a["author"] and a["source"], f"{a['file']} has no licence record"
        assert (lot / a["file"]).stat().st_size <= 300 * 1024, f"{a['file']} is larger than 300 KB"
        assert data["fr"] == 30 and data["op"] > data["ip"] and data["w"] > 0 and data["h"] > 0
        assert not data.get("assets"), f"{a['file']} embeds or links external assets (images/precomps)"


def test_the_prompt_lists_the_lottie_files_and_unlisted_ones_are_rejected():
    hint = ma.approved_libraries_hint()
    assert "success_check.json" in hint and "../lottie/" in hint
    assert ma.audit_scene_tsx_security('import a from "../lottie/success_check.json";')["passed"]
    res = ma.audit_scene_tsx_security('import a from "../lottie/stolen.json";')
    assert not res["passed"] and any("licence record" in f for f in res["findings"])


def test_a_skill_file_has_the_same_hash_with_lf_and_crlf_line_endings(tmp_path):
    """Registration and verification use one hash; a CRLF checkout (git on Windows) must not break a pinned skill."""
    from SYSTEM.registries import skill_registry as sr
    lf, crlf = tmp_path / "a.md", tmp_path / "b.md"
    lf.write_bytes(b"line one\nline two\n")
    crlf.write_bytes(b"line one\r\nline two\r\n")
    assert sr.compute_file_sha256(lf) == sr.compute_file_sha256(crlf)


# ---- second wave: captions, infographics, effects, audio, HUD, math/code, regions; WebGL libraries stay out ----
def test_webgl_libraries_and_transitions_are_rejected_dom_ones_allowed():
    for bad in ('import { LightLeak } from "@remotion/light-leaks";', 'import { blurSlide } from "@remotion/transitions";', 'import { filmBurn } from "@remotion/transitions/film-burn";',
                'import { crossZoom } from "@remotion/transitions/cross-zoom";'):
        res = ma.audit_scene_tsx_security(bad)
        assert not res["passed"] and any("WebGL" in f for f in res["findings"]), bad
    ok = ('import { TransitionSeries, linearTiming } from "@remotion/transitions"; import { fade } from "@remotion/transitions/fade"; import { slide } from "@remotion/transitions/slide"; '
          'import katex from "katex"; import { Highlight, themes } from "prism-react-renderer"; import { useAudioData, visualizeAudio } from "@remotion/media-utils"; import us from "us-atlas/states-10m.json";')
    assert ma.audit_scene_tsx_security(ok)["passed"]
    assert not ma.audit_scene_tsx_security('import { loadFont } from "@remotion/google-fonts/Poppins";')["passed"]        # fonts are self-hosted: no network font loader


def test_every_import_the_skills_document_passes_the_audit():
    """The skills tell the LLM what to import; the audit must accept all of it (they were contradicting each other once: world-atlas files)."""
    import re
    spec = re.compile(r"""(?:from\s+|import\s+)["']([^"']+)["']""")
    root = Path(__file__).resolve().parent.parent / "SYSTEM" / "skills" / "motion"
    problems = {}
    for f in sorted(root.glob("*/SKILL.md")):
        code = "\n".join(f'import x from "{s}";' for s in spec.findall(f.read_text(encoding="utf-8")))
        bad = ma.unapproved_imports(code)
        if bad:
            problems[f.parent.name] = bad
    assert problems == {}, problems


def test_the_second_wave_skills_are_registered():
    ids = {s.skill_id for s in skill_registry.registry.search_skills(domain="motion", status="approved")}
    assert {"motion.captions_subtitles", "motion.infographic_layouts", "motion.transitions_scene_effects", "motion.particles_ambient_effects", "motion.audio_visualizer",
            "motion.hud_technical_overlays", "motion.backgrounds_reveals_camera", "motion.math_code_visuals", "motion.maps_regions"} <= ids


def test_scenes_get_audio_and_spoken_words_through_sceneData():
    rem = Path(__file__).resolve().parent.parent / "VIDEO_ENGINE" / "remotion" / "src"
    assert "useSceneData" in (rem / "sceneData.ts").read_text(encoding="utf-8")
    assert "SceneData.Provider" in (rem / "Main.tsx").read_text(encoding="utf-8")


def test_the_composition_carries_the_spoken_words(tmp_path):
    d, *_ = _mp.make(tmp_path / "proj_words")
    store.set_reusable_motion_templates(d, False)
    ma.generate_custom_motion_code(d, "16:9")
    comp = json.loads((d / "composition.json").read_text(encoding="utf-8"))
    assert isinstance(comp.get("words"), list) and all({"w", "start", "end"} <= set(w) for w in comp["words"])


def test_official_remotion_skills_are_one_canonical_registered_copy():
    root = Path(__file__).resolve().parent.parent
    reg = skill_registry.registry
    reg.initialize()
    for sid, folder in (("remotion.markup", "markup"), ("remotion.captions", "captions")):
        rec = reg._skills[sid]
        f = root / "SYSTEM" / "skills" / rec.entrypoint
        assert rec.status == "review_required" and rec.domain == "remotion"          # approval needs the operator PIN, so it is not 'approved', and it never reaches the motion codegen prompt
        assert rec.content_sha256 == skill_registry.compute_file_sha256(f)
        assert "Project overrides" in f.read_text(encoding="utf-8") and f.parent.name == folder
        pointer = (root / ".claude" / "skills" / f"remotion-{folder}" / "SKILL.md").read_text(encoding="utf-8")
        assert rec.entrypoint in pointer.replace("SYSTEM/skills/", "")                  # Claude Code's copy only points at the canonical one (no second copy of the skill)
    assert sum(1 for k in reg._skills if k.startswith("remotion.")) == 2
    assert not [s for s in reg.search_skills(domain="motion", status="approved") if s.skill_id.startswith("remotion.")]
