"""Playwright verification to ensure zero blinking or thrashing on the Pipeline Execution Flow page."""
import sys
import time
from playwright.sync_api import sync_playwright

def test_pipeline_no_blinking():
    print("\n--- Verifying Live Pipeline Page Stability & Zero Blinking ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)

        # 1. Verify Pipeline Execution Flow is visible
        container = page.locator("[data-testid='stages-container']")
        assert container.is_visible(), "Stages container not visible"

        # 2. Track DOM node replacements over 5 seconds (5000ms)
        # In a blinking app, cards are destroyed and recreated every 1.5s
        initial_card_text = page.locator("[data-testid='stage-card-analyzer']").inner_text()
        print(f"Initial analyzer card rendered: {initial_card_text[:30]}...")

        # Inject a custom attribute to observe if DOM elements get replaced
        page.evaluate("""() => {
            window.__renderCounter = 0;
            const card = document.querySelector("[data-testid='stage-card-analyzer']");
            if (card) {
                card.setAttribute('data-stable-mount', 'true');
            }
        }""")

        # Wait 4 seconds (across multiple poll intervals)
        time.sleep(4.0)

        # Verify the same DOM element is still mounted and wasn't destroyed/recreated by re-renders
        is_still_mounted = page.evaluate("""() => {
            const card = document.querySelector("[data-testid='stage-card-analyzer']");
            return card && card.getAttribute('data-stable-mount') === 'true';
        }""")

        assert is_still_mounted, "DOM element was remounted or destroyed during polling interval!"
        print("  -> PASSED: Stage card DOM element stayed mounted and stable across polling intervals without re-creating or thrashing!")

        browser.close()
    return True

if __name__ == "__main__":
    ok = test_pipeline_no_blinking()
    sys.exit(0 if ok else 1)
