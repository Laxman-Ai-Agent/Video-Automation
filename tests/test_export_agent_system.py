"""The export builds the standalone Agent System repository as a filter of the files git tracks, and prunes only what an earlier export wrote."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import export_agent_system as ex  # noqa: E402


def _git_tree(base: Path, files: dict) -> Path:
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=base, check=True)
    subprocess.run(["git", "add", "-A"], cwd=base, check=True)
    return base


SOURCE = {
    "SYSTEM/core/integrations.py": "x = 1\n",
    "SYSTEM/agents/skill_factory/agent.py": "y = 1\n",
    "SYSTEM/agents/video_generation_agents/audio_input/agent.py": "video = 1\n",
    "SYSTEM/core/pipeline_state.py": "video = 1\n",
    "SYSTEM/agents/capability_finder/knowledge/archive/old.json": "{}",
    "SYSTEM/agents/capability_finder/memory/experiences.json": "[]",
    "SYSTEM/agents/capability_finder/memory/.gitkeep": "",
    "SYSTEM/config/llm_usage.json": "{}",
    "SYSTEM/agents/capability_finder/history/learning_cases.jsonl": "{}\n",
    "SYSTEM/skills/catalog.json": json.dumps({"version": "2.0.0", "updated_at": "now", "skills": {"motion.x": {}}}),
    "SYSTEM/skills/installed_skills.json": json.dumps({"version": "2.0.0", "updated_at": "now", "total_installed": 1, "installed_skills": {"a": {}}}),
    "SYSTEM/skills/categories.json": json.dumps({"version": "2.0.0", "total_categories": 1, "categories": [{"category_id": "motion"}]}),
    "VIDEO_ENGINE/stage.py": "video = 1\n",
    "tests/test_llm_client.py": "from backend.main import app\nfrom backend import llm_client\n",
    "tests/test_integrations.py": "ok = 1\n",
    "tests/test_m9.py": "video test\n",
    "tools/check_boundaries.py": "tool = 1\n",
    "README.md": "video readme\n",
}


def test_the_export_keeps_the_agent_system_and_leaves_out_video_runtime_data_and_unrelated_files(tmp_path):
    source = _git_tree(tmp_path / "video", SOURCE)
    target = tmp_path / "abs"
    ex.export(source, target)
    exported = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    assert "SYSTEM/core/integrations.py" in exported and "SYSTEM/agents/skill_factory/agent.py" in exported
    assert "SYSTEM/agents/capability_finder/memory/.gitkeep" in exported                       # the folder a fresh system needs
    assert {"tests/test_llm_client.py", "tests/test_integrations.py", "tools/check_boundaries.py"} <= exported
    for left_out in ("SYSTEM/agents/video_generation_agents/audio_input/agent.py", "SYSTEM/core/pipeline_state.py", "VIDEO_ENGINE/stage.py",
                     "SYSTEM/agents/capability_finder/knowledge/archive/old.json", "SYSTEM/agents/capability_finder/memory/experiences.json",
                     "SYSTEM/config/llm_usage.json", "SYSTEM/agents/capability_finder/history/learning_cases.jsonl", "tests/test_m9.py", "README.md"):
        assert left_out not in exported, left_out


def test_the_skill_data_ships_empty_but_keeps_its_schema_version(tmp_path):
    source = _git_tree(tmp_path / "video", SOURCE)
    target = tmp_path / "abs"
    ex.export(source, target)
    catalog = json.loads((target / "SYSTEM/skills/catalog.json").read_text(encoding="utf-8"))
    installed = json.loads((target / "SYSTEM/skills/installed_skills.json").read_text(encoding="utf-8"))
    categories = json.loads((target / "SYSTEM/skills/categories.json").read_text(encoding="utf-8"))
    assert catalog["skills"] == {} and installed["installed_skills"] == {} and installed["total_installed"] == 0
    assert categories["categories"] == [] and categories["total_categories"] == 0
    assert catalog["version"] == installed["version"] == categories["version"] == "2.0.0"


def test_the_video_alias_in_exported_tests_is_rewritten_to_the_canonical_imports(tmp_path):
    source = _git_tree(tmp_path / "video", SOURCE)
    target = tmp_path / "abs"
    ex.export(source, target)
    text = (target / "tests/test_llm_client.py").read_text(encoding="utf-8")
    assert "from UI.backend.main import app" in text and "from SYSTEM.core import llm_client" in text and "backend import" not in text.replace("UI.backend", "")


def test_a_re_export_prunes_only_what_the_previous_export_wrote(tmp_path):
    source = _git_tree(tmp_path / "video", SOURCE)
    target = tmp_path / "abs"
    ex.export(source, target)
    (target / "README.md").write_text("only in the standalone repository\n", encoding="utf-8")
    (target / "UI/backend").mkdir(parents=True)
    (target / "UI/backend/main.py").write_text("own = 1\n", encoding="utf-8")

    (source / "SYSTEM/agents/skill_factory/agent.py").unlink()                                  # no longer tracked: the next export must not keep it
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    summary = ex.export(source, target)

    assert summary["pruned"] == ["SYSTEM/agents/skill_factory/agent.py"]
    assert not (target / "SYSTEM/agents/skill_factory/agent.py").exists()
    assert (target / "README.md").read_text(encoding="utf-8") == "only in the standalone repository\n"
    assert (target / "UI/backend/main.py").exists()


def test_the_manifest_records_what_was_exported(tmp_path):
    source = _git_tree(tmp_path / "video", SOURCE)
    target = tmp_path / "abs"
    summary = ex.export(source, target)
    manifest = json.loads((target / "EXPORT_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["files"] == sorted(manifest["files"]) and len(manifest["files"]) == summary["files"]
    assert "SYSTEM/skills/catalog.json" in manifest["files"] and "SYSTEM/core/pipeline_state.py" not in manifest["files"]
