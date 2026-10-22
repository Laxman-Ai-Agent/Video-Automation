"""Playwright verification to ensure Pipeline Execution Flow displays 12 connected stages starting at Audio Analysis,
and Agents Center displays 20 registered agents (13 Video + 7 System).
Captures verification screenshot to artifacts directory.
"""
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))

def test_pipeline_11_stages():
    print("\n--- Verifying Pipeline Execution Flow (12 Stages) & 20 Canonical Agents ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)

        # 1. Verify Pipeline Execution Flow is visible
        container = page.locator("[data-testid='stages-container']")
        assert container.is_visible(), "Stages container not visible"

        # 2. Check header text indicates 12 Connected Stages
        header_text = page.locator("text=12 Connected Stages").first
        assert header_text.is_visible(), "Header '12 Connected Stages' not visible"
        print("  -> PASSED: Header confirms '12 Connected Stages'")

        # 3. Verify Stage 01 is Audio Analysis (stage-card-analyzer)
        card_analyzer = page.locator("[data-testid='stage-card-analyzer']")
        assert card_analyzer.is_visible(), "Stage card analyzer not visible"
        analyzer_text = card_analyzer.inner_text()
        assert "Audio Analysis" in analyzer_text, f"Audio Analysis not found in card text: {analyzer_text}"
        assert "01" in analyzer_text, f"Stage 01 number not found in card text: {analyzer_text}"
        print(f"  -> PASSED: Stage 01 is 'Audio Analysis' (analyzer)")

        # 4. Verify Audio Input card is NOT present
        card_audio = page.locator("[data-testid='stage-card-audio']")
        assert not card_audio.is_visible(), "Audio input stage card should not be visible"
        print("  -> PASSED: Audio Input stage card is completely absent from pipeline flow")

        # 5. Verify total stage cards is exactly 12
        stage_cards = page.locator("[data-testid^='stage-card-']").all()
        assert len(stage_cards) == 12, f"Expected 12 stage cards, found {len(stage_cards)}"
        print(f"  -> PASSED: Exactly 12 stage cards rendered in pipeline grid")

        # 6. Verify sidebar navigation has '20 Agents'
        sidebar_agents_item = page.locator("text=20 Agents").first
        assert sidebar_agents_item.is_visible(), "Sidebar label '20 Agents' not visible"
        print("  -> PASSED: Sidebar confirms '20 Agents'")

        # Capture Pipeline Screenshot
        screenshot_path = ARTIFACTS_DIR / "live_pipeline_11_stages.png"
        page.screenshot(path=str(screenshot_path), full_page=False)
        print(f"  -> Saved pipeline screenshot to: {screenshot_path}")

        # 7. Navigate to Agents Center Page
        page.locator("[data-testid='sidebar-nav-agents'], [data-testid='nav-item-agents']").first.click()
        page.wait_for_timeout(800)

        # Verify Agents Center heading or subtext
        agents_header = page.locator("text=20 Registered").first
        assert agents_header.is_visible(), "Agents Center '20 Registered' not visible"
        print("  -> PASSED: Agents Center displays '20 Registered' agents")

        # Capture Agents Center Screenshot
        agents_screenshot_path = ARTIFACTS_DIR / "agents_center_20_agents.png"
        page.screenshot(path=str(agents_screenshot_path), full_page=False)
        print(f"  -> Saved Agents Center screenshot to: {agents_screenshot_path}")

        browser.close()
    return True

if __name__ == "__main__":
    ok = test_pipeline_11_stages()
    sys.exit(0 if ok else 1)
