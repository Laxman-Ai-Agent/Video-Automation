import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_all_pipeline_cards_fullpage():
    artifacts_dir = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)

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

        # Stages to test
        test_stages = [
            ("analyzer", "Audio Analysis", "audio-analysis-back-btn", "pipeline-audio-analysis-fullpage-container"),
            ("segmentation", "Scene Segmentation", "stage-drawer-back-btn", "pipeline-stage-fullpage-container"),
            ("planning", "Visual Planning", "stage-drawer-back-btn", "pipeline-stage-fullpage-container"),
            ("approval", "Timeline Approval", "stage-drawer-back-btn", "pipeline-stage-fullpage-container"),
            ("render", "Render Video", "stage-drawer-back-btn", "pipeline-stage-fullpage-container"),
            ("final", "Final Delivery", "stage-drawer-back-btn", "pipeline-stage-fullpage-container"),
        ]

        for stage_id, label, back_testid, container_testid in test_stages:
            print(f"\n[ACTION] Testing Stage '{label}' ({stage_id})...")
            card = page.locator(f"[data-testid='stage-card-{stage_id}']")
            card.wait_for(state="visible", timeout=10000)
            card.click()
            page.wait_for_timeout(800)

            # 1. Verify full-page container is rendered on the same page
            full_container = page.locator(f"[data-testid='{container_testid}']")
            assert full_container.is_visible(), f"Full-page container for {label} ({stage_id}) is not visible!"
            print(f"  [OK] Full-page container for '{label}' is visible on the same page.")

            # 2. Verify Back to Pipeline button
            back_btn = page.locator(f"[data-testid='{back_testid}']")
            assert back_btn.is_visible(), f"Back button for {label} is not visible!"
            print(f"  [OK] 'Back to Pipeline' button is visible.")

            # 3. Take screenshot for key stages
            if stage_id in ["segmentation", "approval", "render"]:
                ss_path = artifacts_dir / f"stage_{stage_id}_fullpage_view.png"
                page.screenshot(path=str(ss_path))
                print(f"  [OK] Saved screenshot to {ss_path}")

            # 4. For stage 'segmentation', test tabs navigation in full-page mode
            if stage_id == "segmentation":
                subtasks_tab = page.locator("[data-testid='stage-drawer-tab-subtasks']")
                if subtasks_tab.is_visible():
                    subtasks_tab.click()
                    page.wait_for_timeout(400)
                    print("  [OK] Switched to Subtasks tab in full-page mode.")

                agent_tab = page.locator("[data-testid='stage-drawer-tab-agent']")
                if agent_tab.is_visible():
                    agent_tab.click()
                    page.wait_for_timeout(400)
                    print("  [OK] Switched to Agent tab in full-page mode.")

            # 5. Click Back Button and verify return to pipeline
            print(f"  [ACTION] Clicking Back to Pipeline button...")
            back_btn.click()
            page.wait_for_timeout(600)

            assert not full_container.is_visible(), f"Full-page view did not close for {label}!"
            assert card.is_visible(), f"Pipeline stage card did not reappear for {label}!"
            print(f"  [OK] Successfully returned to Pipeline Execution Flow from '{label}'.")

        # Test inspecting from StageExecutionTracking side panel
        print("\n[ACTION] Testing 'View Full Stage Details & Logs' from StageExecutionTracking...")
        tracking_inspect_btn = page.locator("[data-testid='tracking-open-stage-details-btn']")
        if tracking_inspect_btn.is_visible():
            tracking_inspect_btn.click()
            page.wait_for_timeout(800)

            stage_container = page.locator("[data-testid='pipeline-stage-fullpage-container']")
            assert stage_container.is_visible(), "Full-page container did not open from tracking panel!"
            print("  [OK] Stage opened in full-page mode from tracking panel.")

            back_btn = page.locator("[data-testid='stage-drawer-back-btn']")
            back_btn.click()
            page.wait_for_timeout(600)
            assert not stage_container.is_visible(), "Full-page container did not close after back!"
            print("  [OK] Successfully returned to Pipeline flow from tracking panel full-page view.")

        # Take final return screenshot
        final_ss = artifacts_dir / "all_stages_pipeline_flow_verified.png"
        page.screenshot(path=str(final_ss))
        print(f"\n[OK] Final return screenshot saved to {final_ss}")

        browser.close()
        print("\nAll pipeline cards full-page navigation tests passed with 100% success!")

if __name__ == "__main__":
    test_all_pipeline_cards_fullpage()
