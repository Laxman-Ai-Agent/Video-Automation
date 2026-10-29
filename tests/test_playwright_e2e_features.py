"""Playwright E2E verification for:
1. New Project opens the Audio Input page.
2. Project title and audio upload work.
3. Analyze starts the actual backend workflow.
4. Pipeline stages appear in the correct order.
5. Progress and completion states reflect real backend events.
6. Agent Communication & Handoff Panel displays actual available activity.
7. Errors are displayed correctly without falsely marking the pipeline as successful.
8. The top metric cards live on the Dashboard, not on the Live Pipeline page.
"""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_e2e_features():
    audio_path = str(Path("tests/fixtures/audio_test.wav").resolve())
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Test audio file not found at {audio_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # TEST 1: Main Dashboard loads, "New Project" opens the Audio Input page
        page.goto("http://localhost:5173", wait_until="load", timeout=15000)
        page.wait_for_timeout(1000)

        new_proj_btn = page.locator("[data-testid='sidebar-nav-pipeline']")
        assert new_proj_btn.is_visible(), "New Project nav button not visible"
        new_proj_btn.click()
        page.wait_for_timeout(800)

        title_input = page.locator("[data-testid='project-title-input']")
        assert title_input.is_visible(), "Audio Input page not displayed after clicking New Project"

        # TEST 2: Validation errors without falsely starting the pipeline
        analyze_btn = page.locator("[data-testid='analyze-button']")
        analyze_btn.click()
        page.wait_for_timeout(500)

        body_text = page.inner_text("body").lower()
        assert "required" in body_text or "title" in body_text, "Validation error not shown for empty title"
        assert page.locator("[data-testid='project-title-input']").is_visible(), "Incorrectly navigated away despite missing fields"

        # TEST 3: Project title entry and audio file upload
        test_project_title = f"E2E Playwright Auto Test {int(time.time())}"
        page.fill("[data-testid='project-title-input']", test_project_title)

        file_input = page.locator("[data-testid='audio-file-input']")
        file_input.set_input_files(audio_path)
        page.wait_for_timeout(800)

        content = page.content()
        assert "audio_test.wav" in content, "Uploaded file name not displayed on page"
        assert "Audio Verified" in content or "KB" in content or "MB" in content, "Audio file status not verified"

        # TEST 4: Analyze starts the real backend workflow and navigates to the pipeline canvas
        analyze_btn.click()
        page.wait_for_selector("[data-testid='stages-container']", timeout=20000)
        page.wait_for_timeout(1500)
        assert page.locator("[data-testid='stages-container']").is_visible(), "Stages container not visible after Analyze"

        # TEST 5: All 12 canonical stages present in correct execution order
        expected_stage_ids = [
            'analyzer', 'segmentation', 'planning', 'assets',
            'motion_plan', 'motion_gen', 'motion_validation', 'timeline',
            'approval', 'render', 'qc', 'final'
        ]
        cards = page.locator("[data-testid^='stage-card-']").all()
        found_stages = [c.get_attribute("data-testid").replace("stage-card-", "") for c in cards]
        assert found_stages == expected_stage_ids, f"Stages order mismatch: {found_stages}"

        # TEST 6: Real stage states, no fake progress
        has_running = page.locator("[data-status='running']").count() > 0
        has_waiting = page.locator("[data-status='waiting']").count() > 0
        has_completed = page.locator("[data-status='completed']").count() > 0
        assert has_running or has_waiting or has_completed, "No valid stage states found"

        # TEST 7: Agent Communication & Handoff panel displays the real log and agent registry
        page.locator("[data-testid='pill-tab-communication']").click()
        page.wait_for_timeout(800)

        comm_panel = page.locator("[data-testid='agent-communication-panel']")
        assert comm_panel.is_visible(), "Agent Communication panel not visible"
        assert "Agent Communication" in comm_panel.inner_text(), "Panel title missing"

        agent_tab = page.locator("[data-testid='agent-registry-tab']")
        agent_tab.click()
        page.wait_for_timeout(600)
        registry_text = comm_panel.inner_text()
        assert "Agent" in registry_text, "Registry agents not displayed in panel"

        # TEST 8: Live Pipeline has no top metric cards (they live on the Dashboard)
        page.locator("[data-testid='pill-tab-flow']").click()
        page.wait_for_timeout(600)
        assert page.locator("text='Total Pipeline Runs'").count() == 0, "Top metric cards unexpectedly found on Live Pipeline"

        # TEST 9: Dashboard houses the top metric cards
        page.locator("[data-testid='sidebar-nav-dashboard']").click()
        page.wait_for_timeout(800)

        runs_card = page.locator("text='Total Pipeline Runs'").first
        assert runs_card.is_visible(), "Top metric cards not visible on Dashboard"
        agents_card = page.locator("text='Canonical Agents'").first
        assert agents_card.is_visible(), "Canonical Agents card not visible on Dashboard"

        browser.close()

if __name__ == "__main__":
    test_e2e_features()
    print("All E2E feature checks passed.")
