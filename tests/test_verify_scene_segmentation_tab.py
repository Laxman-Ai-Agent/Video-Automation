"""
Automated Playwright test to verify Scene Segmentation tab and full-page drawer view.
"""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# All 12 stages are completed for this project, so every stage card is clickable
# (a fresh project's later cards are disabled until their prior stage finishes).
TEST_PROJECT_ID = "my-first-project-01-df7f"

def test_scene_segmentation_tab():
    artifacts_dir = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(f"http://localhost:5173/?projectId={TEST_PROJECT_ID}", wait_until="load", timeout=15000)
        page.locator("[data-testid='stage-card-segmentation']").wait_for(state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        seg_card = page.locator('[data-testid="stage-card-segmentation"]')
        seg_card.click()
        page.wait_for_timeout(800)

        full_view = page.locator('[data-testid="stage-detail-full-view"]')
        assert full_view.is_visible(), "stage-detail-full-view not visible"

        back_btn = page.locator('[data-testid="stage-drawer-back-btn"]')
        assert back_btn.is_visible(), "Back button not visible"

        scenes_tab = page.locator('[data-testid="stage-drawer-tab-scenes"]')
        assert scenes_tab.is_visible(), "Scenes tab button not found"
        scenes_tab.click()
        page.wait_for_timeout(800)

        scenes_content = page.locator('[data-testid="scene-segmentation-tab-content"]')
        assert scenes_content.is_visible(), "scene-segmentation-tab-content not visible"

        search_input = page.locator('[data-testid="scenes-filter-input"]')
        assert search_input.is_visible(), "scenes-filter-input not found"

        page.wait_for_selector('[data-testid="scene-header-0"]', timeout=10000)

        scene_headers = page.locator('[data-testid^="scene-header-"]')
        count = scene_headers.count()
        assert count > 0, "No scene headers rendered"

        # Filter narrows the list, clearing it restores the full list
        search_input.fill("business")
        page.wait_for_timeout(500)
        filtered_count = page.locator('[data-testid^="scene-header-"]').count()
        assert 0 < filtered_count <= count, f"Filter did not narrow the list ({filtered_count} of {count})"

        search_input.fill("")
        page.wait_for_timeout(500)
        restored_count = page.locator('[data-testid^="scene-header-"]').count()
        assert restored_count == count, f"Clearing the filter did not restore all {count} scenes (got {restored_count})"

        page.locator('[data-testid="scene-header-1"]').click()
        page.wait_for_timeout(500)

        page.screenshot(path=str(artifacts_dir / "scene_segmentation_scenes_tab_verified.png"), full_page=False)

        back_btn.click()
        page.wait_for_timeout(800)

        pipeline_cards = page.locator('[data-testid^="stage-card-"]')
        assert pipeline_cards.count() == 12, f"Pipeline canvas not restored properly after Back ({pipeline_cards.count()} cards)"

        page.screenshot(path=str(artifacts_dir / "scene_segmentation_pipeline_restored.png"), full_page=False)

        browser.close()

if __name__ == "__main__":
    test_scene_segmentation_tab()
    print("All Scene Segmentation tab checks passed.")
