import os
from pathlib import Path
from playwright.sync_api import sync_playwright

# All 12 stages are completed for this project, so every stage card is clickable
# (a fresh project's later cards are disabled until their prior stage finishes).
TEST_PROJECT_ID = "my-first-project-01-df7f"

def test_all_pipeline_cards_fullpage():
    artifacts_dir = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(f"http://localhost:5173/?projectId={TEST_PROJECT_ID}", wait_until="load")
        page.locator("[data-testid='stage-card-analyzer']").wait_for(state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        # Every stage opens in the same full-page StageDrawer and returns with the same Back button
        test_stages = [
            ("analyzer", "Audio Analysis"),
            ("segmentation", "Scene Segmentation"),
            ("planning", "Visual Planning"),
            ("approval", "Timeline Approval"),
            ("render", "Render Video"),
            ("final", "Final Delivery"),
        ]

        for stage_id, label in test_stages:
            card = page.locator(f"[data-testid='stage-card-{stage_id}']")
            card.wait_for(state="visible", timeout=10000)
            card.click()
            page.wait_for_timeout(800)

            full_container = page.locator("[data-testid='pipeline-stage-fullpage-container']")
            assert full_container.is_visible(), f"Full-page container for {label} ({stage_id}) is not visible!"
            assert label in full_container.inner_text(), f"Full-page view does not name the stage {label}"
            # Full page replaces the pipeline grid on the same page (no overlay on top of it)
            assert not page.locator("[data-testid='stages-container']").is_visible(), f"Pipeline grid still shown behind {label}"

            back_btn = page.locator("[data-testid='stage-drawer-back-btn']")
            assert back_btn.is_visible(), f"Back button for {label} is not visible!"

            if stage_id in ["segmentation", "approval", "render"]:
                page.screenshot(path=str(artifacts_dir / f"stage_{stage_id}_fullpage_view.png"))

            if stage_id == "segmentation":
                for tab in ("subtasks", "agent"):
                    tab_btn = page.locator(f"[data-testid='stage-drawer-tab-{tab}']")
                    assert tab_btn.is_visible(), f"{tab} tab missing in full-page mode"
                    tab_btn.click()
                    page.wait_for_timeout(400)

            back_btn.click()
            page.wait_for_timeout(600)

            assert not full_container.is_visible(), f"Full-page view did not close for {label}!"
            assert card.is_visible(), f"Pipeline stage card did not reappear for {label}!"

        page.screenshot(path=str(artifacts_dir / "all_stages_pipeline_flow_verified.png"))
        browser.close()

if __name__ == "__main__":
    test_all_pipeline_cards_fullpage()
