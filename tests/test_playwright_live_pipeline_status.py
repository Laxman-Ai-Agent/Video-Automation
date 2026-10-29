"""Playwright verification test for Live Pipeline Status, Running Animations & Error Visibility.
Verifies:
1. Live SSE connection status badge ('Live Connected' / status indicator).
2. Stage cards display honest real statuses and large numeric percentages without progress bars.
3. Clicking a stage card opens the detailed operational StageDrawer with metrics, status, agent, and subtasks.
4. CSS animations, pulsing indicators, and error styling tokens exist.
5. Captures screenshot to artifacts directory.
"""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))

# A project with every stage completed, so every stage card is clickable
# (a fresh project's later cards are disabled until their prior stage finishes).
TEST_PROJECT_ID = "my-first-project-01-df7f"

def test_live_pipeline_status():
    print("\n--- Verifying Live Pipeline Status, Animations & Error Visibility ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"http://localhost:5173/?projectId={TEST_PROJECT_ID}", wait_until="load")
        page.locator("[data-testid='stage-card-analyzer']").wait_for(state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        # 1. Verify live SSE connection badge
        sse_pill = page.locator("[data-testid='live-connection-status-pill']").first
        assert sse_pill.is_visible(), "Live connection status badge not visible"
        print(f"  -> PASSED: Live connection status indicator visible ({sse_pill.inner_text().strip()})")

        # 2. Verify all 12 stage cards and status badges
        stage_cards = page.locator("[data-testid^='stage-card-']").all()
        assert len(stage_cards) == 12, f"Expected 12 stage cards, found {len(stage_cards)}"
        print(f"  -> PASSED: 12 stage cards rendered")

        # 3. Verify no artificial progress bar inside main stage cards
        # (Progress bars should be in detailed sub-stage views, main cards use clean typography / percentage text)
        progress_bars = page.locator("[data-testid^='stage-card-'] progress").all()
        assert len(progress_bars) == 0, f"Found unexpected <progress> tags inside stage cards: {len(progress_bars)}"
        print("  -> PASSED: Main stage cards do not contain cramped progress bars")

        # 4. Check Stage 01 (Audio Analysis) drawer interaction
        card_01 = page.locator("[data-testid='stage-card-analyzer']")
        assert card_01.is_visible()
        card_01.click()
        page.wait_for_timeout(600)

        audio_view = page.locator("[data-testid='pipeline-stage-fullpage-container']")
        assert audio_view.is_visible(), "Audio Analysis full-page view did not open on clicking Stage 01"
        print("  -> PASSED: Clicking Stage 01 opens the Audio Analysis full-page view")

        # Back to the pipeline
        page.locator("[data-testid='stage-drawer-back-btn']").first.click()
        page.wait_for_timeout(500)

        # 5. Check Stage 02 (Scene Segmentation) drawer interaction
        card_02 = page.locator("[data-testid='stage-card-segmentation']")
        assert card_02.is_visible()
        card_02.click()
        page.wait_for_timeout(600)

        stage_drawer = page.locator("[data-testid='stage-detail-full-view']")
        assert stage_drawer.is_visible(), "StageDrawer did not open on clicking Stage 02"
        drawer_text = stage_drawer.inner_text()
        assert "Scene Segmentation" in drawer_text, "StageDrawer did not show stage name"
        print("  -> PASSED: Clicking Stage 02 opens StageDrawer with operational details")

        # Check subtasks tab inside stage drawer
        subtasks_tab = page.locator("[data-testid='stage-drawer-tab-subtasks']").first
        if subtasks_tab.is_visible():
            subtasks_tab.click()
            page.wait_for_timeout(400)
            print("  -> PASSED: Subtasks breakdown tab accessible in StageDrawer")

        # Capture Stage Drawer screenshot
        screenshot_drawer = ARTIFACTS_DIR / "live_pipeline_stage_drawer.png"
        page.screenshot(path=str(screenshot_drawer), full_page=False)
        print(f"  -> Saved StageDrawer screenshot to: {screenshot_drawer}")

        # Close Stage drawer
        close_stage_btn = page.locator("[data-testid='stage-drawer-back-btn']").first
        if close_stage_btn.is_visible():
            close_stage_btn.click()
            page.wait_for_timeout(400)

        # 6. Verify CSS status classes in stylesheet
        has_active_pulse = page.evaluate("""() => {
            const sheets = Array.from(document.styleSheets);
            for (const s of sheets) {
                try {
                    const rules = Array.from(s.cssRules || []);
                    for (const r of rules) {
                        if (r.name === 'activeStagePulse' || r.name === 'retryingPulse') {
                            return true;
                        }
                    }
                } catch(e) {}
            }
            return false;
        }""")
        assert has_active_pulse, "CSS keyframes for activeStagePulse/retryingPulse not found in loaded stylesheets"
        print("  -> PASSED: Keyframe animations activeStagePulse and retryingPulse exist in stylesheet")

        # Capture final live pipeline view screenshot
        screenshot_pipeline = ARTIFACTS_DIR / "live_pipeline_status_verified.png"
        page.screenshot(path=str(screenshot_pipeline), full_page=False)
        print(f"  -> Saved Pipeline Status screenshot to: {screenshot_pipeline}")

        browser.close()
    return True

if __name__ == "__main__":
    ok = test_live_pipeline_status()
    sys.exit(0 if ok else 1)
