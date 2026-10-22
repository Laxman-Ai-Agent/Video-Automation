import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_about_tab_all_stages():
    artifacts_dir = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()

        print("[NAVIGATE] Opening http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Ensure we are in Pipeline Execution Flow tab
        flow_tab = page.locator("[data-testid='tab-pipeline-flow']")
        if flow_tab.is_visible():
            flow_tab.click()
            page.wait_for_timeout(500)

        canonical_stages = [
            ("analyzer", "Audio Analysis", "audio-analysis-back-btn", "audio-tab-about"),
            ("segmentation", "Scene Segmentation", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("planning", "Visual Planning", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("motion_plan", "Motion Planning", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("motion_gen", "Motion Generation", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("motion_validation", "Motion Validation", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("timeline", "Timeline Build", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("approval", "Timeline Approval", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("render", "Render Video", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("qc", "Final QC", "stage-drawer-back-btn", "stage-drawer-tab-about"),
            ("final", "Final Delivery", "stage-drawer-back-btn", "stage-drawer-tab-about"),
        ]

        verified_stages = []

        for stage_id, label, back_testid, about_tab_testid in canonical_stages:
            print(f"\n[ACTION] Testing About Tab for Stage '{label}' ({stage_id})...")
            card = page.locator(f"[data-testid='stage-card-{stage_id}']")
            card.wait_for(state="visible", timeout=10000)
            card.click()
            page.wait_for_timeout(600)

            # Locate and click the About tab
            about_tab = page.locator(f"[data-testid='{about_tab_testid}']")
            about_tab.wait_for(state="visible", timeout=5000)
            assert about_tab.is_visible(), f"About tab button for {label} is not visible!"
            about_tab.click()
            page.wait_for_timeout(600)

            # Verify Agent About Tab container is visible
            about_container = page.locator("[data-testid='agent-about-tab-container']")
            about_container.wait_for(state="visible", timeout=5000)
            assert about_container.is_visible(), f"Agent About container for {label} is not rendered!"

            # Verify presence of key sections
            overview_sec = page.locator("[data-testid='agent-about-section-overview']")
            assert overview_sec.is_visible(), f"Overview section missing for {label}"

            resp_sec = page.locator("[data-testid='agent-about-section-responsibilities']")
            assert resp_sec.is_visible(), f"Responsibilities section missing for {label}"

            flow_sec = page.locator("[data-testid='agent-about-section-internal-flow']")
            assert flow_sec.is_visible(), f"Internal flow section missing for {label}"

            source_sec = page.locator("[data-testid='agent-about-section-source-code']")
            assert source_sec.is_visible(), f"Source code section missing for {label}"

            print(f"  [OK] Successfully verified all core About sections for '{label}'.")
            verified_stages.append(stage_id)

            # Take screenshot for illustrative stages
            if stage_id in ["analyzer", "planning", "approval", "render", "final"]:
                ss_path = artifacts_dir / f"about_tab_{stage_id}.png"
                page.screenshot(path=str(ss_path))
                print(f"  [OK] Saved screenshot to {ss_path.name}")

            # Return back to pipeline canvas
            back_btn = page.locator(f"[data-testid='{back_testid}']")
            if back_btn.is_visible():
                back_btn.click()
                page.wait_for_timeout(400)

        browser.close()

    print(f"\n[SUMMARY] All {len(verified_stages)}/11 canonical stages verified successfully with full About tabs!")

if __name__ == "__main__":
    test_about_tab_all_stages()
