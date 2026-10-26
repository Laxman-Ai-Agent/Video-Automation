"""Motion Generation scene by scene (motion_gen_report.scenes_view): the written code, the elements, the checks and how the code was made, read from the project's own folder."""
import hashlib
import json

from VIDEO_ENGINE.stages import motion_gen_report as mgr

CODE = 'import React from "react";\nconst Scene1: React.FC = () => <div data-element-id="s1_hero" />;\nexport default Scene1;\n'


def _project(tmp_path):
    (tmp_path / "generated_motion").mkdir()
    (tmp_path / "generated_motion" / "scene_1.tsx").write_text(CODE, encoding="utf-8")
    sha = hashlib.sha256(CODE.encode("utf-8")).hexdigest()
    (tmp_path / "motion_animation.json").write_text(json.dumps({
        "mode": "custom_code", "status": "generated", "run_id": "run-1", "typecheck": {"status": "passed"}, "diagnostics": {"compiled_scenes": 1}, "warnings": [],
        "scenes": [{"scene_id": 1, "source_path": "C:/elsewhere/evil.tsx", "source_sha256": sha, "input_fingerprint": "fp1", "duration_frames": 340, "required_elements": ["s1_hero"],
                    "implemented_elements": ["s1_hero"], "missing_required_elements": [], "compile_status": "passed", "security_audit": {"passed": True, "findings": []},
                    "preview_result": {"passed": True, "score": 1.0}, "generation": {"provider": "cache", "model": "reused", "attempt_count": 1}, "repair_attempts": 1, "warnings": []}]}), encoding="utf-8")
    (tmp_path / "motion_generation.json").write_text(json.dumps({"scenes": [{"plan_scene_id": 1, "timing": {"start": 0.0, "end": 11.3}, "validation_notes": [],
                                                                            "descriptors": [{"element_id": "s1_hero", "element_type": "custom_scene", "component_id": "custom_scene", "preset_id": "Scene1", "start": 0.0, "end": 11.3, "props": {"x": 1}}]}]}), encoding="utf-8")
    (tmp_path / "scene_plan.json").write_text(json.dumps({"scenes": [{"id": 1, "start": 0.0, "end": 11.3, "meaning": "Hook"}]}), encoding="utf-8")
    return tmp_path


def test_every_scene_comes_with_its_code_elements_checks_and_descriptors(tmp_path):
    v = mgr.scenes_view(_project(tmp_path), "16:9")
    assert v["status"] == "generated" and v["typecheck"] == {"status": "passed"} and len(v["scenes"]) == 1
    s = v["scenes"][0]
    assert s["code"] == CODE and s["lines"] == 4 and s["file"] == "generated_motion/scene_1.tsx" and s["code_changed"] is False             # the code comes from the project folder, not from the path in the manifest
    assert s["start"] == 0.0 and s["end"] == 11.3 and s["meaning"] == "Hook" and s["implemented_elements"] == ["s1_hero"] and s["input_fingerprint"] == "fp1"
    assert s["descriptors"] == [{"element_id": "s1_hero", "element_type": "custom_scene", "component_id": "custom_scene", "preset_id": "Scene1", "start": 0.0, "end": 11.3}]
    (tmp_path / "generated_motion" / "scene_1.tsx").write_text(CODE + "// edited by hand\n", encoding="utf-8")
    assert mgr.scenes_view(tmp_path, "16:9")["scenes"][0]["code_changed"] is True                                                    # edited after the manifest recorded it


def test_nothing_generated_yet_gives_none(tmp_path):
    assert mgr.scenes_view(tmp_path, "16:9") is None
