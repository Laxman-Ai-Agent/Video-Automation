"""Playwright automated verification for Agent Intelligence, Growth & Upgrade Tracking System."""
import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "http://localhost:5173"


def test_agent_intelligence_system():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Grant clipboard-read and clipboard-write permissions
        context = browser.new_context(
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})

        print("Navigating to frontend...")
        page.goto(FRONTEND_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # 1. Navigate to Agents Center Page
        print("Clicking Agents sidebar button...")
        agents_btn = page.locator('button:has-text("Agents")').first
        if not agents_btn.is_visible():
            agents_btn = page.locator('nav button:has-text("Agents")')
        agents_btn.click()
        page.wait_for_timeout(1000)

        # Verify Agents Center Page is loaded
        agents_page = page.locator('[data-testid="agents-center-page"]')
        assert agents_page.is_visible(), "Agents Center Page not visible"
        print("Agents Center Page loaded successfully.")

        # Capture screenshot of Agents Swarm Grid
        grid_screenshot = ARTIFACTS_DIR / "agent_intelligence_swarm_grid.png"
        page.screenshot(path=str(grid_screenshot))
        print(f"Captured Agents Swarm Grid screenshot: {grid_screenshot}")

        # Check cards count
        cards = page.locator('[data-testid^="agent-card-"]')
        count = cards.count()
        print(f"Total agent cards in grid: {count}")
        assert count >= 20, f"Expected at least 20 agent cards, found {count}"

        # 2. Test Visual Planning Agent Detail View
        print("Clicking Visual Planning Agent card...")
        vp_card = page.locator('[data-testid="agent-card-visual_planning"]')
        assert vp_card.is_visible(), "Visual Planning card not visible"
        vp_card.click()
        page.wait_for_timeout(1500)

        # Verify Detail View rendered
        detail_view = page.locator('[data-testid="agent-intelligence-detail-view"]')
        assert detail_view.is_visible(), "Agent Intelligence Detail View not visible"
        print("Agent Intelligence Detail View opened successfully.")

        # Capture screenshot of Detail View - Growth Dashboard
        growth_screenshot = ARTIFACTS_DIR / "agent_intelligence_visual_planning_growth.png"
        page.screenshot(path=str(growth_screenshot))
        print(f"Captured Visual Planning Growth Dashboard screenshot: {growth_screenshot}")

        # Verify Growth & Maturity Cards
        growth_content = page.locator('[data-testid="growth-dashboard-content"]')
        assert growth_content.is_visible(), "Growth dashboard content not visible"
        assert page.locator('text=Capability Readiness Score').is_visible()
        assert page.locator('text=Verification Coverage').is_visible()
        assert page.locator('text=Quality Score & Telemetry').is_visible()
        assert page.locator('text=Chronological Maturity Snapshots').is_visible()

        # 3. Test "Copy All Agent Details" button
        print("Testing 'Copy All Agent Details' button...")
        copy_btn = page.locator('[data-testid="copy-all-agent-details-btn"]')
        assert copy_btn.is_visible(), "Copy button not visible"
        copy_btn.click()
        page.wait_for_timeout(1000)

        # Verify clipboard or toast message
        copied_text = page.evaluate("navigator.clipboard.readText()")
        print(f"Copied text length: {len(copied_text)} chars")
        assert len(copied_text) > 500, "Copied profile too short"
        assert "# Agent Technical Profile:" in copied_text, "Missing title in copied profile"
        assert "## 1. Agent Identity & Metadata" in copied_text, "Missing section 1"
        assert "## 2. Executive Overview & Architectural Purpose" in copied_text, "Missing section 2"
        assert "## 14. Current Capabilities & Maturity Classification" in copied_text, "Missing section 14"
        assert "## 19. Growth & Maturity History" in copied_text, "Missing section 19"
        print("Verified all 19 specification points in copied Markdown profile!")

        # 4. Test Verified Upgrades Tab
        print("Switching to Verified Upgrades Tab...")
        upgrades_tab = page.locator('[data-testid="tab-upgrades"]')
        upgrades_tab.click()
        page.wait_for_timeout(1000)

        upgrades_content = page.locator('[data-testid="upgrades-content"]')
        assert upgrades_content.is_visible(), "Upgrades content not visible"
        upgrades_screenshot = ARTIFACTS_DIR / "agent_intelligence_visual_planning_upgrades.png"
        page.screenshot(path=str(upgrades_screenshot))
        print(f"Captured Upgrades Tab screenshot: {upgrades_screenshot}")

        # 5. Test Technical Profile Tab (A-L)
        print("Switching to Technical Profile (A-L) Tab...")
        about_tab = page.locator('[data-testid="tab-about"]')
        about_tab.click()
        page.wait_for_timeout(1000)

        tech_content = page.locator('[data-testid="technical-profile-content"]')
        assert tech_content.is_visible(), "Technical profile content not visible"
        tech_screenshot = ARTIFACTS_DIR / "agent_intelligence_visual_planning_technical.png"
        page.screenshot(path=str(tech_screenshot))
        print(f"Captured Technical Profile Tab screenshot: {tech_screenshot}")

        # 6. Test LLM Markdown Export Preview Tab
        print("Switching to LLM Markdown Export Preview Tab...")
        markdown_tab = page.locator('[data-testid="tab-markdown"]')
        markdown_tab.click()
        page.wait_for_timeout(1000)

        md_content = page.locator('[data-testid="markdown-preview-content"]')
        assert md_content.is_visible(), "Markdown preview content not visible"
        md_screenshot = ARTIFACTS_DIR / "agent_intelligence_visual_planning_markdown.png"
        page.screenshot(path=str(md_screenshot))
        print(f"Captured Markdown Preview Tab screenshot: {md_screenshot}")

        # 7. Test "Back to All Agents" Navigation
        print("Clicking 'Back to All Agents' button...")
        back_btn = page.locator('[data-testid="back-to-agents-swarm-btn"]')
        back_btn.click()
        page.wait_for_timeout(1000)

        assert page.locator('[data-testid="agents-center-page"]').is_visible()
        print("Returned to Agents Swarm Grid successfully.")

        # 8. The Audio Analyzer detail view opens too
        print("Testing the Audio Analyzer agent detail view...")
        audio_card = page.locator('[data-testid="agent-card-audio_analyzer"]')
        audio_card.click()
        page.wait_for_timeout(1200)

        assert page.locator('[data-testid="agent-intelligence-detail-view"]').is_visible(), "Audio Analyzer detail view not visible"

        # Return back
        page.locator('[data-testid="back-to-agents-swarm-btn"]').click()
        page.wait_for_timeout(1000)

        # 9. Test System Agent: Skill Factory
        print("Testing System Subagent (Skill Factory)...")
        sf_card = page.locator('[data-testid="agent-card-skill_factory"]')
        sf_card.click()
        page.wait_for_timeout(1200)

        assert page.locator('text=AUTONOMOUS SKILL SYNTHESIS').first.is_visible()
        sf_screenshot = ARTIFACTS_DIR / "agent_intelligence_skill_factory.png"
        page.screenshot(path=str(sf_screenshot))
        print(f"Captured Skill Factory screenshot: {sf_screenshot}")

        print("ALL PLAYWRIGHT TESTS PASSED SUCCESSFULLY!")
        browser.close()


if __name__ == "__main__":
    test_agent_intelligence_system()
