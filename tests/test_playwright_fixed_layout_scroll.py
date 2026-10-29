"""Playwright E2E verification test for Fixed Sidebar, Fixed Header, and Independent Main Content Scrolling:
1. Left Sidebar remains fixed and stationary across all views and scroll states.
2. Top Header remains fixed at y=0, never scrolls off-screen, never overlaps or scrolls behind window.
3. Window scroll position (window.scrollY) is ALWAYS 0 (zero whole-page/window scrolling).
4. Only the main content area (<main>) scrolls vertically when content exceeds viewport height.
5. Verification across multiple views: Agents, Skills, Dashboard, Pipeline Execution Flow.
6. Zero unwanted horizontal scrolling (window.scrollX === 0, main.scrollLeft === 0).
"""
from playwright.sync_api import sync_playwright

def test_fixed_layout_scroll():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto("http://localhost:5173", wait_until="load", timeout=15000)
        page.wait_for_timeout(1000)

        sidebar = page.locator("aside").first
        header = page.locator("header")
        main = page.locator("[data-testid='main-content-scroll-area']")

        assert sidebar.is_visible(), "Sidebar is not visible"
        assert header.is_visible(), "Header is not visible"
        assert main.is_visible(), "Main content area is not visible"

        # TEST 1: Window Scroll Lock (window.scrollY must ALWAYS be 0)
        win_scroll_y = page.evaluate("window.scrollY")
        win_scroll_x = page.evaluate("window.scrollX")
        doc_overflow = page.evaluate("getComputedStyle(document.documentElement).overflow")
        body_overflow = page.evaluate("getComputedStyle(document.body).overflow")

        assert win_scroll_y == 0, f"Expected window.scrollY == 0, got {win_scroll_y}"
        assert win_scroll_x == 0, f"Expected window.scrollX == 0, got {win_scroll_x}"
        assert "hidden" in doc_overflow or "hidden" in body_overflow, "Expected html/body to have overflow: hidden"

        # TEST 2: Long page (Agents) - scroll and verify Sidebar & Header stationary
        page.locator("[data-testid='sidebar-nav-agents']").click()
        page.wait_for_timeout(600)

        sidebar_box_init = sidebar.bounding_box()
        header_box_init = header.bounding_box()
        nav_btn_init = page.locator("[data-testid='sidebar-nav-agents']").bounding_box()

        main_scroll_height = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollHeight")
        main_client_height = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').clientHeight")
        assert main_scroll_height > main_client_height, (
            f"Expected the Agents page to be taller than the viewport ({main_scroll_height} > {main_client_height})"
        )

        page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollTop = 400")
        page.wait_for_timeout(400)

        main_scroll_top = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollTop")
        assert main_scroll_top >= 350, f"Expected main.scrollTop >= 350, got {main_scroll_top}"
        assert page.evaluate("window.scrollY") == 0, "Window scrolled when main content scrolled!"

        sidebar_box_scrolled = sidebar.bounding_box()
        assert sidebar_box_scrolled["x"] == sidebar_box_init["x"], "Sidebar x moved!"
        assert sidebar_box_scrolled["y"] == sidebar_box_init["y"], "Sidebar y moved!"
        assert sidebar_box_scrolled["width"] == sidebar_box_init["width"], "Sidebar width changed!"
        assert sidebar_box_scrolled["height"] == sidebar_box_init["height"], "Sidebar height changed!"

        header_box_scrolled = header.bounding_box()
        assert header_box_scrolled["y"] == header_box_init["y"], "Header y moved!"
        assert header_box_scrolled["x"] == header_box_init["x"], "Header x moved!"
        assert header_box_scrolled["height"] == header_box_init["height"], "Header height changed!"

        nav_btn_scrolled = page.locator("[data-testid='sidebar-nav-agents']").bounding_box()
        assert abs(nav_btn_scrolled["y"] - nav_btn_init["y"]) < 1, "Sidebar nav item shifted vertically during main content scroll!"

        # TEST 3: Skills page (long page) - scroll to bottom and check header/sidebar stay put
        page.locator("[data-testid='sidebar-nav-skills']").click()
        page.wait_for_timeout(600)

        page.evaluate("const el = document.querySelector('[data-testid=\"main-content-scroll-area\"]'); el.scrollTop = el.scrollHeight;")
        page.wait_for_timeout(400)

        assert page.evaluate("window.scrollY") == 0, "window.scrollY moved on scroll to bottom"

        h_box = header.bounding_box()
        assert h_box["y"] == 0, f"Header y should be 0, got {h_box['y']}"
        assert header.is_visible(), "Header became invisible after scrolling to bottom"

        s_box = sidebar.bounding_box()
        assert s_box["x"] == 0, f"Sidebar x should be 0, got {s_box['x']}"
        assert s_box["y"] == 0, f"Sidebar y should be 0, got {s_box['y']}"
        assert sidebar.is_visible(), "Sidebar became invisible after scrolling to bottom"

        # TEST 4: Pipeline Execution Flow - layout and scroll isolation
        page.locator("[data-testid='sidebar-nav-pipeline']").click()
        page.wait_for_timeout(600)

        assert page.evaluate("window.scrollY") == 0, "Window scroll should be 0"

        page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollTop = 100")
        page.wait_for_timeout(200)

        assert page.evaluate("window.scrollY") == 0, "Window scroll should remain 0"
        assert sidebar.bounding_box()["y"] == 0, "Sidebar y shifted"
        assert header.bounding_box()["y"] == 0, "Header y shifted"

        # TEST 5: Zero unwanted horizontal scrolling across all pages
        for nav_id in ["sidebar-nav-dashboard", "sidebar-nav-pipeline", "sidebar-nav-projects", "sidebar-nav-agents", "sidebar-nav-skills"]:
            btn = page.locator(f"[data-testid='{nav_id}']")
            assert btn.count() > 0 and btn.is_visible(), f"Nav item '{nav_id}' not visible"
            btn.click()
            page.wait_for_timeout(300)
            win_x = page.evaluate("window.scrollX")
            main_x = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollLeft")
            assert win_x == 0, f"Horizontal window scroll detected on {nav_id}: {win_x}"
            assert main_x == 0, f"Horizontal main scroll detected on {nav_id}: {main_x}"

        browser.close()

if __name__ == "__main__":
    test_fixed_layout_scroll()
    print("All fixed layout & independent scroll checks passed.")
