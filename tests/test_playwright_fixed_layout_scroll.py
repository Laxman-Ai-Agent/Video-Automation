"""Playwright E2E verification test for Fixed Sidebar, Fixed Header, and Independent Main Content Scrolling:
1. Left Sidebar remains fixed and stationary across all views and scroll states.
2. Top Header remains fixed at y=0, never scrolls off-screen, never overlaps or scrolls behind window.
3. Window scroll position (window.scrollY) is ALWAYS 0 (zero whole-page/window scrolling).
4. Only the main content area (<main>) scrolls vertically when content exceeds viewport height.
5. Verification across multiple views:
   - 21 Agents (long page with 21 cards)
   - Skills Registry (long page with multiple domain cards)
   - Dashboard (metrics and project table)
   - Pipeline Execution Flow (connected sequence canvas)
   - Visual AI Editor (5-tab workspace)
6. Zero unwanted horizontal scrolling (window.scrollX === 0, main.scrollLeft === 0).
"""
import sys
import time
from playwright.sync_api import sync_playwright

def run_layout_scroll_tests():
    print("\n==================================================================")
    print("STARTING PLAYWRIGHT VERIFICATION FOR FIXED SIDEBAR & INDEPENDENT SCROLL")
    print("==================================================================\n")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use standard laptop resolution
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Navigating to application...")
        page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)

        sidebar = page.locator("aside").first
        header = page.locator("header")
        main = page.locator("[data-testid='main-content-scroll-area']")

        assert sidebar.is_visible(), "Sidebar is not visible"
        assert header.is_visible(), "Header is not visible"
        assert main.is_visible(), "Main content area is not visible"

        # -----------------------------------------------------------
        # TEST 1: Window Scroll Lock (window.scrollY must ALWAYS be 0)
        # -----------------------------------------------------------
        print("\nTEST 1: Verifying window scroll lock (no whole-page scrolling)...")
        try:
            # Check window scroll
            win_scroll_y = page.evaluate("window.scrollY")
            win_scroll_x = page.evaluate("window.scrollX")
            doc_overflow = page.evaluate("document.documentElement.style.overflow || window.getComputedStyle(document.documentElement).overflow")
            body_overflow = page.evaluate("document.body.style.overflow || window.getComputedStyle(document.body).overflow")

            assert win_scroll_y == 0, f"Expected window.scrollY == 0, got {win_scroll_y}"
            assert win_scroll_x == 0, f"Expected window.scrollX == 0, got {win_scroll_x}"
            assert "hidden" in doc_overflow or "hidden" in body_overflow, "Expected html/body to have overflow: hidden"

            results["1_window_scroll_locked"] = "PASSED"
            print("  -> PASSED: Window scrolling is locked (window.scrollY == 0, overflow: hidden).")
        except Exception as e:
            results["1_window_scroll_locked"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 2: Long Page (21 Agents) — Scroll and verify Sidebar & Header stationary
        # -----------------------------------------------------------
        print("\nTEST 2: Verifying 21 Agents (long page) scroll behavior...")
        try:
            # Navigate to 21 Agents
            page.locator("[data-testid='sidebar-nav-agents']").click()
            page.wait_for_timeout(600)

            # Record initial positions
            sidebar_box_init = sidebar.bounding_box()
            header_box_init = header.bounding_box()

            # Record a sidebar nav button position
            nav_btn = page.locator("[data-testid='sidebar-nav-agents']").bounding_box()

            # Verify content is scrollable
            main_scroll_height = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollHeight")
            main_client_height = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').clientHeight")
            assert main_scroll_height > main_client_height, f"Expected 21 Agents to be taller than viewport ({main_scroll_height} > {main_client_height})"

            # Scroll main content area down by 400px
            page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollTop = 400")
            page.wait_for_timeout(400)

            main_scroll_top = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollTop")
            assert main_scroll_top >= 350, f"Expected main.scrollTop >= 350, got {main_scroll_top}"

            # Verify window.scrollY is STILL 0
            assert page.evaluate("window.scrollY") == 0, "Window scrolled when main content scrolled!"

            # Verify Sidebar did NOT move at all
            sidebar_box_scrolled = sidebar.bounding_box()
            assert sidebar_box_scrolled["x"] == sidebar_box_init["x"], "Sidebar x moved!"
            assert sidebar_box_scrolled["y"] == sidebar_box_init["y"], "Sidebar y moved!"
            assert sidebar_box_scrolled["width"] == sidebar_box_init["width"], "Sidebar width changed!"
            assert sidebar_box_scrolled["height"] == sidebar_box_init["height"], "Sidebar height changed!"

            # Verify Header did NOT move at all
            header_box_scrolled = header.bounding_box()
            assert header_box_scrolled["y"] == header_box_init["y"], "Header y moved!"
            assert header_box_scrolled["x"] == header_box_init["x"], "Header x moved!"
            assert header_box_scrolled["height"] == header_box_init["height"], "Header height changed!"

            # Verify sidebar nav item did NOT move
            nav_btn_scrolled = page.locator("[data-testid='sidebar-nav-agents']").bounding_box()
            assert abs(nav_btn_scrolled["y"] - nav_btn["y"]) < 1, "Sidebar nav item shifted vertically during main content scroll!"

            results["2_agents_page_scroll_and_fixed_elements"] = "PASSED"
            print("  -> PASSED: 21 Agents content scrolled 400px down while Sidebar and Header stayed 100% stationary.")
        except Exception as e:
            results["2_agents_page_scroll_and_fixed_elements"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 3: Skills Page (long page) — Scroll to bottom and check header visibility
        # -----------------------------------------------------------
        print("\nTEST 3: Verifying Skills Page scroll to bottom...")
        try:
            # Navigate to Skills
            page.locator("[data-testid='sidebar-nav-skills']").click()
            page.wait_for_timeout(600)

            # Scroll to very bottom of main content
            page.evaluate("const el = document.querySelector('[data-testid=\"main-content-scroll-area\"]'); el.scrollTop = el.scrollHeight;")
            page.wait_for_timeout(400)

            # Verify window still at 0
            assert page.evaluate("window.scrollY") == 0, "window.scrollY moved on scroll to bottom"

            # Verify Header is still visible and at y=0
            h_box = header.bounding_box()
            assert h_box["y"] == 0, f"Header y should be 0, got {h_box['y']}"
            assert header.is_visible(), "Header became invisible after scrolling to bottom"

            # Verify Sidebar is still visible and at x=0, y=0
            s_box = sidebar.bounding_box()
            assert s_box["x"] == 0, f"Sidebar x should be 0, got {s_box['x']}"
            assert s_box["y"] == 0, f"Sidebar y should be 0, got {s_box['y']}"
            assert sidebar.is_visible(), "Sidebar became invisible after scrolling to bottom"

            results["3_skills_page_scroll_to_bottom"] = "PASSED"
            print("  -> PASSED: Scrolled to bottom of Skills; Header stayed at y=0 and Sidebar at x=0.")
        except Exception as e:
            results["3_skills_page_scroll_to_bottom"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 4: Live Pipeline / New Project — Layout and Scroll Isolation
        # -----------------------------------------------------------
        print("\nTEST 4: Verifying Live Pipeline & New Project scroll isolation...")
        try:
            # Navigate to Pipeline
            page.locator("[data-testid='sidebar-nav-pipeline']").click()
            page.wait_for_timeout(600)

            assert page.evaluate("window.scrollY") == 0, "Window scroll should be 0"

            # Check if main content scrolls
            page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollTop = 100")
            page.wait_for_timeout(200)

            assert page.evaluate("window.scrollY") == 0, "Window scroll should remain 0"
            assert sidebar.bounding_box()["y"] == 0, "Sidebar y shifted"
            assert header.bounding_box()["y"] == 0, "Header y shifted"

            results["4_pipeline_scroll_isolation"] = "PASSED"
            print("  -> PASSED: Live Pipeline page maintains complete scroll isolation.")
        except Exception as e:
            results["4_pipeline_scroll_isolation"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 5: Visual AI Editor — 5 Tabs in Fixed Layout
        # -----------------------------------------------------------
        print("\nTEST 5: Verifying Visual AI Editor 5 tabs in fixed layout...")
        try:
            # Navigate to Visual AI Editor
            page.locator("[data-testid='sidebar-nav-visual-editor']").click()
            page.wait_for_timeout(600)

            # Verify all 5 tabs are visible
            assert page.locator("[data-testid='tab-feedback']").is_visible()
            assert page.locator("[data-testid='tab-ai-chat']").is_visible()
            assert page.locator("[data-testid='tab-plan']").is_visible()
            assert page.locator("[data-testid='tab-implementation']").is_visible()
            assert page.locator("[data-testid='tab-preview']").is_visible()

            # Switch tabs and check scroll independence
            page.locator("[data-testid='tab-plan']").click()
            page.wait_for_timeout(400)
            assert page.locator("[data-testid='change-review-panel']").is_visible()

            # Scroll main content area
            page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollTop = 200")
            page.wait_for_timeout(200)

            assert page.evaluate("window.scrollY") == 0, "Window scroll should remain 0"
            assert sidebar.bounding_box()["y"] == 0, "Sidebar moved on Visual AI Editor"
            assert header.bounding_box()["y"] == 0, "Header moved on Visual AI Editor"

            results["5_visual_ai_editor_fixed_layout"] = "PASSED"
            print("  -> PASSED: Visual AI Editor works smoothly in fixed layout without whole-page scroll.")
        except Exception as e:
            results["5_visual_ai_editor_fixed_layout"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 6: Zero Unwanted Horizontal Scrolling across all pages
        # -----------------------------------------------------------
        print("\nTEST 6: Verifying zero horizontal scrollbars across pages...")
        try:
            for nav_id in ["sidebar-nav-dashboard", "sidebar-nav-pipeline", "sidebar-nav-visual-editor", "sidebar-nav-projects", "sidebar-nav-agents", "sidebar-nav-skills", "sidebar-nav-diagnostics"]:
                btn = page.locator(f"[data-testid='{nav_id}']")
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(300)
                    win_x = page.evaluate("window.scrollX")
                    main_x = page.evaluate("document.querySelector('[data-testid=\"main-content-scroll-area\"]').scrollLeft")
                    assert win_x == 0, f"Horizontal window scroll detected on {nav_id}: {win_x}"
                    assert main_x == 0, f"Horizontal main scroll detected on {nav_id}: {main_x}"

            results["6_zero_horizontal_scroll"] = "PASSED"
            print("  -> PASSED: No unwanted horizontal scrolling detected on any page.")
        except Exception as e:
            results["6_zero_horizontal_scroll"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        browser.close()

    print("\n==================================================================")
    print("FIXED LAYOUT & INDEPENDENT SCROLL SUMMARY RESULTS:")
    print("==================================================================")
    all_passed = True
    for test_name, status in results.items():
        print(f"  [{status}] {test_name}")
        if not str(status).startswith("PASSED"):
            all_passed = False
    print("==================================================================\n")
    return all_passed

if __name__ == "__main__":
    ok = run_layout_scroll_tests()
    sys.exit(0 if ok else 1)
