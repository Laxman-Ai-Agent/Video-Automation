from SYSTEM.core.backend_alias import install

install()   # the same `backend` alias the API and the CLI use (SYSTEM registers it on import); kept explicit so the tests never depend on import order

import os

import pytest

from UI.backend import autoplan

# Motion Generation draws one still per scene in a browser after the type check (motion_animation.render_errors_by_scene). Off in the suite, for the module-scoped fixtures too (a function-scoped
# fixture would come too late for them); the tests that cover the check turn it on with monkeypatch.
os.environ.setdefault("MOTION_RENDER_CHECK", "0")


@pytest.fixture(autouse=True)
def no_autoplan(monkeypatch):
    monkeypatch.setattr(autoplan, "ENABLED", False)


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Safety guard: prevents any test from reaching a live LLM, whichever provider config/llm_settings.json holds on this machine (the Claude CLI process or a paid/limited API)."""
    try:
        from backend import llm_client
        def fake(*args, **kwargs):
            raise llm_client.LlmError("Tests are prohibited from reaching a live LLM.")
        for name in ("_call_claude_cli", "_call_gemini", "_call_openai_compatible", "_call_anthropic"):
            monkeypatch.setattr(llm_client, name, fake)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def isolate_projects_dir(tmp_path, monkeypatch):
    """Safety guard: prevents any test from polluting the real workspace projects directory."""
    test_projects = tmp_path / "projects"
    test_projects.mkdir(parents=True, exist_ok=True)
    try:
        from backend import config as be_config, store as be_store
        monkeypatch.setattr(be_config, "PROJECTS_DIR", test_projects)
        monkeypatch.setattr(be_store, "PROJECTS_DIR", test_projects)
    except Exception:
        pass
    try:
        from SYSTEM.core import config as sys_config
        monkeypatch.setattr(sys_config, "PROJECTS_DIR", test_projects)
    except Exception:
        pass
    try:
        from SYSTEM.memory import store as sys_store
        monkeypatch.setattr(sys_store, "PROJECTS_DIR", test_projects)
    except Exception:
        pass


# Measured 2026-10-27, each module run on its own on the i5-1235U: 45 s or more (20 of them did not finish in 90 s).
SLOW_MODULES = {
    "test_audio_visual_agents_integration.py", "test_asset_collection.py", "test_dome_render.py", "test_e2e_production_readiness.py",
    "test_final_qc.py", "test_improve_p1.py", "test_main_orchestrator_intelligence.py", "test_motion_animation_intelligence.py",
    "test_motion_approved_libraries.py", "test_motion_codegen.py", "test_motion_codegen_and_concurrency.py", "test_motion_generation.py",
    "test_motion_library.py", "test_motion_only_mode.py", "test_motion_planning.py", "test_motion_validation.py",
    "test_motion_validation_intelligence.py", "test_phase2_capability_system.py", "test_phase3_capability_learning.py", "test_sound_design.py",
    "test_phase9_e2e_integration.py", "test_render_smoke.py", "test_render_video.py", "test_scene_segmentation.py",
    "test_stage5_desktop_delivery_auto_qc.py", "test_stage_lifecycle_and_gate_removal.py", "test_timeline_approval.py",
    "test_timeline_approval_intelligence.py", "test_timeline_build.py", "test_timeline_render_qc_delivery.py",
}
# Browser tests against the running app (API :8000, frontend :5173).
LIVE_UI_MODULES = {
    "test_playwright_about_tab_all_stages.py", "test_playwright_agent_intelligence_system.py", "test_playwright_audio_analysis_card.py",
    "test_playwright_e2e_features.py", "test_playwright_e2e_visible_video_generation.py", "test_playwright_fixed_layout_scroll.py",
    "test_playwright_live_pipeline_status.py", "test_playwright_no_blinking.py", "test_playwright_pipeline_11_stages.py",
    "test_playwright_ui_smoke.py", "test_verify_all_pipeline_cards_fullpage.py",
    "test_verify_backend_stability.py", "test_verify_realtime_status_indicators.py", "test_verify_scene_segmentation_tab.py",
    "test_verify_sidebar_buttons_removed.py",
}


def pytest_collection_modifyitems(items):
    """Marks the slow and the live-UI modules, so the fast suite is `-m "not slow and not live_ui"` (nothing is skipped by default)."""
    for item in items:
        name = item.path.name
        if name in SLOW_MODULES:
            item.add_marker(pytest.mark.slow)
        if name in LIVE_UI_MODULES:
            item.add_marker(pytest.mark.live_ui)


@pytest.fixture(autouse=True)
def isolate_repo_state(tmp_path, monkeypatch):
    """Tests never write the repository's own state files: the approvals queue and audit log and the central skill catalog live in tmp_path
    (the catalog starts as a copy of the real one), and the skill registry's memory is restored after the test."""
    import shutil
    from SYSTEM.approvals import approval_engine as ae
    from SYSTEM.registries import skill_registry as sr
    state = tmp_path / "repo_state"
    state.mkdir(exist_ok=True)
    monkeypatch.setattr(ae.approval_engine, "_audit_file", state / "approvals_audit.jsonl")
    monkeypatch.setattr(ae.approval_engine, "_queue_file", state / "approvals_queue.json")
    if sr.CATALOG_FILE.exists():
        shutil.copy(sr.CATALOG_FILE, state / "catalog.json")
    monkeypatch.setattr(sr, "CATALOG_FILE", state / "catalog.json")
    monkeypatch.setattr(sr.registry, "_skills", dict(sr.registry._skills))
    monkeypatch.setattr(sr.registry, "_initialized", sr.registry._initialized)


@pytest.fixture(scope="session", autouse=True)
def no_leftover_browser_profiles():
    """Tests that start Remotion's browser leave puppeteer_dev_chrome_profile-* folders in the temp folder (Windows cannot delete them while Chrome closes): remove the ones this run made."""
    from backend import browser_profiles
    before = browser_profiles.snapshot()
    yield
    browser_profiles.sweep(before)


def _codegen_stub_execute():
    """Stub LLM gateway call for Motion Animation: returns a Scene component that draws every listed visual element with its data-element-id."""
    import json as _json
    from backend import llm_gateway

    def execute(req):
        sid, els, headline = "1", [], ""
        for line in req.user_prompt.splitlines():
            if line.startswith("Generate React TSX animation code for Scene "):
                sid = line.split("Scene ")[1].split(".")[0].strip()
            elif line.startswith("Visual elements: "):
                els = [e for e in _json.loads(line[len("Visual elements: "):]) if e.get("element_id")]
            elif line.startswith("Headline:"):
                headline = line[len("Headline:"):].strip()
            elif line.startswith("On-screen texts (draw every one, verbatim): "):
                extra = [t for t in _json.loads(line.split(": ", 1)[1]) if t != headline]
                headline = " ".join([headline, *extra]).strip()
        nodes = "\n".join(f"      <div data-element-id={_json.dumps(e['element_id'])} data-spec={{{_json.dumps(_json.dumps(e))}}} />" for e in els)
        tsx = (f'import React from "react";\nimport {{ AbsoluteFill, useCurrentFrame, useVideoConfig }} from "remotion";\n'
               f'export const Scene{sid}: React.FC<{{ layer?: any }}> = () => {{\n  const frame = useCurrentFrame();\n  const {{ fps }} = useVideoConfig();\n'
               f'  return (\n    <AbsoluteFill style={{{{ justifyContent: "center", color: "#f8fafc" }}}}>\n      <h1 style={{{{ fontSize: 56 }}}}>{headline}</h1>\n{nodes}\n    </AbsoluteFill>\n  );\n}};\nexport default Scene{sid};\n')
        return llm_gateway.LlmGatewayResponse(
            request_id=req.request_id, correlation_id=req.correlation_id, project_id=req.project_id, stage_id=req.stage_id,
            agent_id=req.agent_id, purpose=req.purpose, status="passed", raw_text=tsx, structured_data=None,
            model_profile=req.model_profile, provider="stub", model="stub", latency_ms=1, attempt_count=1)

    return execute


def _codegen_over(inner):
    """Motion Animation's generation/repair requests get the codegen stub; every other gateway call goes to `inner` (the asset planner, reviews...)."""
    stub = _codegen_stub_execute()

    def execute(req):
        if req.agent_id == "motion_animation" and req.stage_id == "motion_gen" and req.purpose in ("generation", "repair"):
            return stub(req)
        return inner(req)
    return execute


@pytest.fixture
def llm_codegen_stub(monkeypatch):
    from backend import llm_gateway
    monkeypatch.setattr(llm_gateway.gateway, "execute", _codegen_over(llm_gateway.gateway.execute))


@pytest.fixture(scope="module")
def llm_codegen_stub_module():
    from backend import llm_gateway
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(llm_gateway.gateway, "execute", _codegen_over(llm_gateway.gateway.execute))
        yield


@pytest.fixture
def llm_review_pass(llm_review_says):
    """Opt-in: every stage LLM review passes (the API-flow tests fake Whisper/CLIP/Remotion the same way)."""


@pytest.fixture(autouse=True)
def _no_remotion_preview(monkeypatch, request):
    """Validation makes its preview stills itself: in tests the Remotion bundle and stills are fakes (a small PNG shaped like a real frame: a plain dark background with its
    content inside the safe margin, so the visual checks see contrast and clean edges); the sampling, checks and manifest stay real."""
    from PIL import Image, ImageDraw
    from backend import motion_validation_preview as pv

    def still(bundle, comp_file, frame, dest):
        im = Image.new("RGB", (96, 54), (12, 18, 32))
        ImageDraw.Draw(im).rectangle((30, 18, 66, 36), fill=(240, 240, 240))
        im.save(dest)

    monkeypatch.setattr(pv, "_bundle", lambda dest: dest.mkdir(parents=True, exist_ok=True))
    if not request.node.get_closest_marker("real_remotion_still"):
        monkeypatch.setattr(pv, "_still", still)


@pytest.fixture(autouse=True)
def _fresh_circuit_breaker():
    """The LLM circuit breaker is process-global: failures in one test must not block the gateway calls of the next."""
    from SYSTEM.core.resilience import circuit_breaker
    circuit_breaker.reset()
    yield
    circuit_breaker.reset()


def _link_dir(link, target):
    """A directory link that needs no admin rights on Windows (a junction)."""
    import os
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


@pytest.fixture(scope="session", autouse=True)
def _per_run_remotion_dir(tmp_path_factory):
    """Stages write generated scenes into config.REMOTION_DIR/src/generated (tracked files): tests get their own Remotion folder for the run.
    src and the config files are copied; node_modules, public and scripts are linked (read-mostly, too large to copy). The repo layout is mirrored
    (<base>/VIDEO_ENGINE/remotion + <base>/resource-library): src imports the Resource Library bundle by a relative path. A test that patches REMOTION_DIR itself still wins."""
    import shutil
    from SYSTEM.core import config
    base = tmp_path_factory.mktemp("remotion_run")
    real, run = config.REMOTION_DIR, base / "VIDEO_ENGINE" / "remotion"
    _link_dir(base / "resource-library", config.PROJECT_ROOT / "resource-library")
    shutil.copytree(real / "src", run / "src")
    for f in ("package.json", "tsconfig.json", "remotion.config.ts"):
        if (real / f).is_file():
            shutil.copyfile(real / f, run / f)
    for d in ("node_modules", "public", "scripts"):
        if (real / d).is_dir():
            _link_dir(run / d, real / d)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "REMOTION_DIR", run)
        yield run


@pytest.fixture(scope="session", autouse=True)
def _stub_motion_codegen_for_the_session():
    """Motion Animation code generation never reaches the live Claude CLI in tests (it fails closed without an LLM): its generation/repair requests get the stub;
    every other gateway call goes through unchanged, and a test that patches execute itself still wins."""
    from backend import llm_gateway
    real = llm_gateway.gateway.execute

    def no_assets(req):
        if req.agent_id == "asset_collection" and req.purpose == "decision":           # the asset planner: no scene needs real media (tests never reach a stock provider)
            return llm_gateway.LlmGatewayResponse(
                request_id=req.request_id, correlation_id=req.correlation_id, project_id=req.project_id, stage_id=req.stage_id,
                agent_id=req.agent_id, purpose=req.purpose, status="passed", raw_text="", structured_data={"requirements": []},
                model_profile=req.model_profile, provider="stub", model="stub", latency_ms=1, attempt_count=1)
        return real(req)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(llm_gateway.gateway, "execute", _codegen_over(no_assets))
        yield
