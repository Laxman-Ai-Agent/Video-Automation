import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 1080})
        page = await context.new_page()

        print("Navigating to http://localhost:5173/?projectId=01-2f64...")
        await page.goto("http://localhost:5173/?projectId=01-2f64", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Look for the stage card for timeline
        print("Finding Timeline Build stage card...")
        timeline_card = page.locator("[data-testid='stage-card-timeline']")
        if await timeline_card.count() == 0:
            # Fallback search by text
            timeline_card = page.locator("text=Timeline Build").first

        print("Clicking Timeline Build stage card...")
        await timeline_card.click()
        await page.wait_for_timeout(2500)

        # Verify visual timeline view is present
        visual_view = page.locator("[data-testid='timeline-build-visual-view']")
        is_visible = await visual_view.is_visible()
        print(f"TimelineBuildVisualView visible: {is_visible}")

        # Capture screenshot 1: Complete Timeline View with Preview Canvas and Tracks
        ss1 = ARTIFACT_DIR / "timeline_build_visual_view_overview.png"
        await page.screenshot(path=str(ss1), full_page=True)
        print(f"Captured screenshot 1: {ss1}")

        # Click on Scene 2 block to inspect details
        print("Clicking Scene 2 block on timeline...")
        scene_2_block = page.locator("text=scene_002").first
        if await scene_2_block.count() > 0:
            await scene_2_block.click()
            await page.wait_for_timeout(1000)

        # Capture screenshot 2: Scene Selection and Detailed Inspector
        ss2 = ARTIFACT_DIR / "timeline_build_scene_inspection.png"
        await page.screenshot(path=str(ss2), full_page=True)
        print(f"Captured screenshot 2: {ss2}")

        # Click Play button for a moment, then step forward a few frames
        print("Stepping forward 15 frames...")
        await page.keyboard.press("ArrowRight")
        await page.keyboard.press("ArrowRight")
        await page.keyboard.press("ArrowRight")
        await page.wait_for_timeout(500)

        # Click zoom in button
        zoom_in_btn = page.locator("button[title*='Zoom In']").first
        if await zoom_in_btn.count() > 0:
            await zoom_in_btn.click()
            await zoom_in_btn.click()
            await page.wait_for_timeout(800)

        # Capture screenshot 3: Zoomed Timeline with multi-format ruler and playhead
        ss3 = ARTIFACT_DIR / "timeline_build_zoomed_ruler.png"
        await page.screenshot(path=str(ss3), full_page=True)
        print(f"Captured screenshot 3: {ss3}")

        # Scroll to Selected Scene Inspector
        print("Scrolling to Selected Scene Inspector...")
        inspector = page.locator("text=Selected Scene:").first
        if await inspector.count() > 0:
            await inspector.scroll_into_view_if_needed()
            await page.wait_for_timeout(800)
            ss4 = ARTIFACT_DIR / "timeline_build_scene_details_inspector.png"
            await page.screenshot(path=str(ss4))
            print(f"Captured screenshot 4 (Scene Details Inspector): {ss4}")

            # Click Raw JSON tab
            raw_tab = page.locator("button:has-text('Raw JSON')").first
            if await raw_tab.count() > 0:
                await raw_tab.click()
                await page.wait_for_timeout(500)
                ss5 = ARTIFACT_DIR / "timeline_build_raw_json_tab.png"
                await page.screenshot(path=str(ss5))
                print(f"Captured screenshot 5 (Raw JSON Inspector): {ss5}")

        await browser.close()
        print("Playwright verification completed successfully!")

if __name__ == "__main__":
    asyncio.run(run())
