import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_audio_analysis_fullpage():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("[NAVIGATE] Opening http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Ensure we are in Pipeline Execution Flow tab
        flow_tab = page.locator("[data-testid='tab-pipeline-flow']")
        if flow_tab.is_visible():
            flow_tab.click()
            page.wait_for_timeout(500)

        # Click on StageCard for Audio Analysis (Stage 01: Audio Analysis / Audio Analyzer Agent)
        print("[ACTION] Clicking on Audio Analysis Stage Card...")
        audio_card = page.locator("[data-testid='stage-card-analyzer']")
        audio_card.wait_for(state="visible", timeout=10000)
        audio_card.click()
        page.wait_for_timeout(1200)

        # Verify fullpage container is rendered
        full_view = page.locator("[data-testid='pipeline-audio-analysis-fullpage-container']")
        assert full_view.is_visible(), "Full-page Audio Analysis container is not visible!"
        print("  [OK] Full-page Audio Analysis view is visible on the same page.")

        # Verify Back Button is present and visible
        back_btn = page.locator("[data-testid='audio-analysis-back-btn']")
        assert back_btn.is_visible(), "Back to Pipeline button is not visible!"
        print("  [OK] 'Back to Pipeline' button is visible.")

        # Verify no backdrop dimming overlay is blocking the page
        backdrop = page.locator("[data-testid='audio-analysis-backdrop']")
        assert not backdrop.is_visible(), "Dimming backdrop is unexpectedly visible!"
        print("  [OK] Backdrop overlay is absent (full page view confirmed).")

        # Capture screenshot for artifact
        screenshot_path = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
        page.screenshot(path=str(screenshot_path))
        print(f"  [OK] Screenshot saved to {screenshot_path}")

        # Click the Back Button
        print("[ACTION] Clicking 'Back to Pipeline' button...")
        back_btn.click()
        page.wait_for_timeout(800)

        # Verify returning to Pipeline Execution Flow
        assert not full_view.is_visible(), "Full-page Audio Analysis view did not close!"
        assert audio_card.is_visible(), "Pipeline Stage Card did not reappear!"
        print("  [OK] Successfully returned to Pipeline Execution Flow on the same page!")

        screenshot_return_path = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
        page.screenshot(path=str(screenshot_return_path))
        print(f"  [OK] Return screenshot saved to {screenshot_return_path}")

        browser.close()
        print("\nAll UI tests passed successfully!")

if __name__ == "__main__":
    test_audio_analysis_fullpage()
