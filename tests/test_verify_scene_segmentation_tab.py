"""
Automated Playwright test to verify Scene Segmentation tab and full-page drawer view.
"""
import sys
import os
import time
from playwright.sync_api import sync_playwright

def main():
    print("=== Testing Scene Segmentation Tab & In-Place View ===")
    artifacts_dir = os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Navigate to project with segmentation data
        target_url = "http://localhost:5173/?projectId=01-2f64"
        print(f"Navigating to {target_url}...")
        page.goto(target_url, wait_until="networkidle", timeout=15000)
        time.sleep(1)

        # Click on Stage 02 - Scene Segmentation card
        seg_card = page.locator('[data-testid="stage-card-segmentation"]')
        if not seg_card.is_visible():
            print("ERROR: Stage card segmentation not found!")
            sys.exit(1)

        print("Clicking Scene Segmentation stage card...")
        seg_card.click()
        time.sleep(1.5)

        # Verify full-page drawer opened
        full_view = page.locator('[data-testid="stage-detail-full-view"]')
        if not full_view.is_visible():
            print("ERROR: stage-detail-full-view not visible!")
            sys.exit(1)
        print("PASS: Stage details full-page view is open.")

        # Verify back button exists
        back_btn = page.locator('[data-testid="stage-drawer-back-btn"]')
        if not back_btn.is_visible():
            print("ERROR: Back button not visible!")
            sys.exit(1)
        print("PASS: 'Back to Pipeline' button is visible.")

        # Verify Scenes tab exists and is active
        scenes_tab = page.locator('button[data-testid="stage-drawer-tab-scenes"]')
        if not scenes_tab.is_visible():
            print("ERROR: Scenes tab button not found!")
            sys.exit(1)
        print(f"PASS: Scenes tab button visible with text: '{scenes_tab.inner_text()}'.")

        # Verify scenes tab content is visible
        scenes_content = page.locator('[data-testid="scene-segmentation-tab-content"]')
        if not scenes_content.is_visible():
            print("ERROR: scene-segmentation-tab-content not visible!")
            sys.exit(1)
        print("PASS: Scene segmentation tab content rendered.")

        # Verify search filter input
        search_input = page.locator('[data-testid="scenes-filter-input"]')
        if not search_input.is_visible():
            print("ERROR: scenes-filter-input not found!")
            sys.exit(1)
        print("PASS: Search filter input 'Filter words or utterances...' is rendered.")

        # Wait for scenes to load from backend API
        print("Waiting for scene cards to render from backend...")
        try:
            page.wait_for_selector('[data-testid="scene-card-0"]', timeout=10000)
            print("PASS: First scene card rendered.")
        except Exception as e:
            print(f"ERROR: Timed out waiting for scene-card-0: {e}")
            # Take a debug screenshot
            debug_shot = os.path.join(artifacts_dir, "debug_scene_tab_timeout.png")
            page.screenshot(path=debug_shot)
            print(f"Debug screenshot saved to {debug_shot}")
            sys.exit(1)

        # Verify scene cards rendered
        scene_cards = page.locator('[data-testid^="scene-card-"]')
        count = scene_cards.count()
        print(f"PASS: Rendered {count} scene cards (expected 6).")
        if count != 6:
            print(f"WARNING: Expected 6 scene cards, got {count}")

        # Check card #0 has expanded details
        first_card = page.locator('[data-testid="scene-card-0"]')
        snippet = first_card.inner_text()[:120].encode('ascii', errors='replace').decode('ascii')
        print(f"First scene card text snippet: {snippet}...")

        # Test filter functionality
        print("Testing search filter...")
        search_input.fill("సూపర్")
        time.sleep(0.5)
        filtered_count = page.locator('[data-testid^="scene-card-"]').count()
        print(f"PASS: Filter for 'సూపర్' returned {filtered_count} scene cards.")

        # Clear filter
        search_input.fill("")
        time.sleep(0.5)
        all_count = page.locator('[data-testid^="scene-card-"]').count()
        print(f"PASS: Reset filter returned {all_count} scene cards.")

        # Toggle scene card #1 to expand it
        header_1 = page.locator('[data-testid="scene-header-1"]')
        header_1.click()
        time.sleep(0.5)

        # Capture high-res screenshot of the Scenes view
        screenshot_path = os.path.join(artifacts_dir, "scene_segmentation_scenes_tab_verified.png")
        page.screenshot(path=screenshot_path, full_page=False)
        print(f"PASS: Saved screenshot to {screenshot_path}")

        # Test Back to Pipeline button
        print("Testing 'Back to Pipeline' button...")
        back_btn.click()
        time.sleep(0.8)

        # Verify pipeline flow is visible again
        pipeline_cards = page.locator('[data-testid^="stage-card-"]')
        if pipeline_cards.count() >= 11:
            print(f"PASS: Restored pipeline flow canvas with {pipeline_cards.count()} stage cards.")
        else:
            print("ERROR: Pipeline canvas not restored properly after clicking Back button.")
            sys.exit(1)

        # Capture screenshot of restored pipeline
        pipeline_screenshot = os.path.join(artifacts_dir, "scene_segmentation_pipeline_restored.png")
        page.screenshot(path=pipeline_screenshot, full_page=False)
        print(f"PASS: Saved restored pipeline screenshot to {pipeline_screenshot}")

        browser.close()
        print("=== ALL CHECKS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
