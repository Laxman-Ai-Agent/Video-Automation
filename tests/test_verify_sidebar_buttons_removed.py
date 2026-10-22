import time
import os
from playwright.sync_api import sync_playwright

def test_verify_sidebar_buttons_removed():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1536, 'height': 864})
        page = context.new_page()
        
        print("Navigating to http://127.0.0.1:5173/...")
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        time.sleep(2)
        
        # Check that Diagnostics and Account buttons do NOT exist in the sidebar
        diagnostics_btn = page.locator("[data-testid='sidebar-nav-diagnostics']")
        account_btn = page.locator("[data-testid='sidebar-nav-account']")
        
        diag_count = diagnostics_btn.count()
        acc_count = account_btn.count()
        
        print(f"Diagnostics button count: {diag_count}")
        print(f"Account button count: {acc_count}")
        assert diag_count == 0, f"Diagnostics button should not exist! Found {diag_count}"
        assert acc_count == 0, f"Account button should not exist! Found {acc_count}"
        
        # Check that expected items exist
        expected_items = [
            "sidebar-nav-dashboard",
            "sidebar-nav-pipeline",
            "sidebar-nav-visual-editor",
            "sidebar-nav-projects",
            "sidebar-nav-agents",
            "sidebar-nav-skills"
        ]
        for item in expected_items:
            locator = page.locator(f"[data-testid='{item}']")
            assert locator.count() > 0, f"Expected {item} to exist in sidebar"
            print(f"Verified expected item: {item}")
            
        output_dir = os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts")
        screenshot_path = os.path.join(output_dir, "sidebar_buttons_removed_verified.png")
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        
        browser.close()
        print("Test passed successfully!")

if __name__ == "__main__":
    test_verify_sidebar_buttons_removed()
