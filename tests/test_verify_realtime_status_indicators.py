import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_realtime_status_indicators():
    artifacts_dir = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("[NAVIGATE] Opening http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        page.wait_for_timeout(2000)

        # 1. Locate and verify Backend Server status pill
        backend_pill = page.locator("[data-testid='backend-status-pill']")
        backend_pill.wait_for(state="visible", timeout=10000)
        backend_text = backend_pill.inner_text().strip()
        print(f"[VERIFY] Backend status pill text: '{backend_text}'")
        assert "SERVER ONLINE" in backend_text or "NO SERVER" in backend_text, f"Unexpected backend text: {backend_text}"

        # 2. Locate and verify LLM status pill
        llm_pill = page.locator("[data-testid='llm-status-pill']")
        llm_pill.wait_for(state="visible", timeout=10000)
        llm_text = llm_pill.inner_text().strip()
        print(f"[VERIFY] LLM status pill text: '{llm_text}'")
        assert llm_text in ("LLM", "LLM OFF"), f"Unexpected LLM text: {llm_text}"

        # 3. Wait 6 seconds and verify stability (no flapping/offline flickering)
        print("[STABILITY] Monitoring status indicators over 6 seconds for flapping...")
        for i in range(3):
            page.wait_for_timeout(2000)
            cur_backend = backend_pill.inner_text().strip()
            cur_llm = llm_pill.inner_text().strip()
            print(f"  T+{(i+1)*2}s: Backend='{cur_backend}', LLM='{cur_llm}'")
            assert "SERVER ONLINE" in cur_backend, f"Backend flapped to offline: {cur_backend}"

        # 4. Capture screenshot of the verified header & UI
        ss_path = artifacts_dir / "realtime_status_indicators_verified.png"
        page.screenshot(path=str(ss_path))
        print(f"[SUCCESS] Saved verified screenshot to {ss_path}")

        browser.close()

if __name__ == "__main__":
    test_realtime_status_indicators()
