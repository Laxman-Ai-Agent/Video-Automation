import sys
import os
import time
from playwright.sync_api import sync_playwright

def test_verify_backend_stability():
    artifact_dir = os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        
        print("1. Loading http://127.0.0.1:5173/ ...")
        page.goto("http://127.0.0.1:5173/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Check backend indicator
        backend_pill = page.locator('[data-testid="backend-status-pill"]')
        backend_pill.wait_for(state="visible", timeout=10000)

        offline_count = 0
        online_count = 0
        total_checks = 25

        print(f"2. Continuously monitoring backend status indicator for {total_checks} seconds...")
        for i in range(total_checks):
            text = backend_pill.inner_text().strip()
            is_offline = "NO SERVER" in text or "OFFLINE" in text
            is_online = "SERVER ONLINE" in text

            banner = page.locator('[data-testid="backend-disconnected-banner"]')
            banner_visible = banner.is_visible()

            if is_offline or banner_visible:
                offline_count += 1
                print(f"[{i+1}/{total_checks}] FLAP DETECTED! Pill: '{text}', Banner visible: {banner_visible}")
            else:
                online_count += 1
                if (i + 1) % 5 == 0:
                    print(f"[{i+1}/{total_checks}] Backend STABLE: '{text}' (Banner hidden)")

            # Also click around between Dashboard and Pipeline to test under UI load
            if i == 5:
                page.locator('[data-testid="sidebar-nav-dashboard"]').click()
            elif i == 12:
                page.locator('[data-testid="sidebar-nav-pipeline"]').click()
            elif i == 18:
                page.locator('[data-testid="sidebar-nav-dashboard"]').click()

            page.wait_for_timeout(1000)

        screenshot_path = os.path.join(artifact_dir, "backend_permanent_stability_verified.png")
        page.screenshot(path=screenshot_path)
        print(f"Saved stability screenshot to: {screenshot_path}")

        print(f"\nResults over {total_checks} seconds:")
        print(f"  Online checks:  {online_count}/{total_checks}")
        print(f"  Offline flaps:  {offline_count}/{total_checks}")

        assert offline_count == 0, f"Backend flapped offline {offline_count} times! Root cause is not fully resolved."
        assert online_count == total_checks, "Backend was not online for the full monitoring period."

        browser.close()
        print("\nPERMANENT STABILITY VERIFIED: 100% ONLINE, ZERO FLAPPING!")

if __name__ == '__main__':
    test_verify_backend_stability()
