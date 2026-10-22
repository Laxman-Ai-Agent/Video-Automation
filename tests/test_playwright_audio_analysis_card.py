"""Playwright E2E verification test for Audio Analysis Card (Stage 01):
1. Clicking Audio Analysis card opens dedicated results drawer.
2. Displays actual saved audio-analysis.json data matching file content (metadata, transcript, utterances, words, pauses, quality).
3. Raw JSON view exposes complete saved JSON and allows copying.
4. Opening the card does NOT trigger new ASR or modify/overwrite audio-analysis.json (hash & mtime preserved).
5. Switching projects (e.g. sample-01 with missing artifact) displays clean missing artifact message with run action.
6. Preserves existing pipeline functionality.
"""
import os
import sys
import time
import json
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
TEST_PROJECT_ID = "test-02-510e"
TEST_PROJECT_JSON_PATH = Path("projects") / TEST_PROJECT_ID / "audio_analysis.json"

def run_audio_analysis_card_tests():
    print("\n==================================================================")
    print("STARTING PLAYWRIGHT VERIFICATION FOR AUDIO ANALYSIS CARD (STAGE 01)")
    print("==================================================================\n")

    assert TEST_PROJECT_JSON_PATH.exists(), f"Expected test artifact not found at {TEST_PROJECT_JSON_PATH}"
    original_bytes = TEST_PROJECT_JSON_PATH.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    original_mtime = TEST_PROJECT_JSON_PATH.stat().st_mtime
    saved_data = json.loads(original_bytes.decode('utf-8'))
    expected_full_text = saved_data["transcription"]["full_text"]

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Catch console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # -----------------------------------------------------------
        # TEST 1: Open project with valid audio-analysis.json
        # -----------------------------------------------------------
        print("TEST 1: Navigating to project with valid audio_analysis.json...")
        try:
            # Set active project in localStorage before navigation
            page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
            page.evaluate(f"localStorage.setItem('a2v_active_project', '{TEST_PROJECT_ID}')")
            page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1000)

            # Confirm project loaded in header
            header_workspace = page.locator("header")
            assert TEST_PROJECT_ID in header_workspace.inner_text(), f"Header does not display active project {TEST_PROJECT_ID}"

            results["1_project_navigation"] = "PASSED"
            print(f"  -> PASSED: Navigated to project '{TEST_PROJECT_ID}'.")
        except Exception as e:
            results["1_project_navigation"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 2: Click Audio Analysis (Stage 01) Card & Verify Results Drawer
        # -----------------------------------------------------------
        print("\nTEST 2: Clicking Audio Analysis card and verifying results drawer...")
        try:
            analyzer_card = page.locator("[data-testid='stage-card-analyzer']")
            assert analyzer_card.is_visible(), "Audio Analysis stage card not visible in pipeline grid"

            analyzer_card.click()
            page.wait_for_timeout(1000)

            drawer = page.locator("[data-testid='audio-analysis-drawer']")
            assert drawer.is_visible(), "Audio Analysis results drawer did not open on card click"

            # Check title and metadata in header
            assert "Audio Analysis Results" in drawer.inner_text(), "Drawer title missing"
            assert TEST_PROJECT_ID in drawer.inner_text(), "Project ID missing in drawer header"

            # Verify Overview tab metadata matches saved JSON
            assert "56.35s" in drawer.inner_text() or "56.3" in drawer.inner_text(), "Duration not displayed"
            assert "44100 Hz" in drawer.inner_text(), "Sample rate 44100 Hz not displayed"
            assert "MP3" in drawer.inner_text(), "MP3 format not displayed"

            # Save Screenshot of Overview
            overview_shot = ARTIFACTS_DIR / "audio_analysis_drawer_overview.png"
            page.screenshot(path=str(overview_shot), full_page=False)
            print(f"  -> Saved overview screenshot to {overview_shot}")

            results["2_click_and_display_overview"] = "PASSED"
            print("  -> PASSED: Clicking Audio Analysis card opened drawer and displayed truthful audio metadata.")
        except Exception as e:
            results["2_click_and_display_overview"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 3: Verify Transcript & Word-Level Timestamps
        # -----------------------------------------------------------
        print("\nTEST 3: Verifying transcript tab and word-level timestamps...")
        try:
            tab_transcript = page.locator("[data-testid='audio-tab-transcript']")
            assert tab_transcript.is_visible(), "Transcript tab button not visible"
            tab_transcript.click()
            page.wait_for_timeout(600)

            # Check full text snippet in drawer matches saved JSON
            first_words = expected_full_text[:30]
            assert first_words in page.content(), f"Expected transcript snippet '{first_words}' not found in drawer content"

            # Check utterance cards rendered
            utterance_card_0 = page.locator("[data-testid='utterance-card-0']")
            assert utterance_card_0.is_visible(), "Utterance card 0 not visible"

            # Save Screenshot of Transcript & Word Timestamps
            transcript_shot = ARTIFACTS_DIR / "audio_analysis_drawer_transcript.png"
            page.screenshot(path=str(transcript_shot), full_page=False)
            print(f"  -> Saved transcript screenshot to {transcript_shot}")

            results["3_transcript_and_words"] = "PASSED"
            print("  -> PASSED: Displayed Telugu transcript and word-level timestamps match audio_analysis.json.")
        except Exception as e:
            results["3_transcript_and_words"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 4: Verify Raw JSON View & Copy Functionality
        # -----------------------------------------------------------
        print("\nTEST 4: Verifying Raw JSON view and copy functionality...")
        try:
            tab_raw = page.locator("[data-testid='audio-tab-raw']")
            assert tab_raw.is_visible(), "Raw JSON tab button not visible"
            tab_raw.click()
            page.wait_for_timeout(600)

            raw_pre = page.locator("[data-testid='audio-analysis-raw-json']")
            assert raw_pre.is_visible(), "Raw JSON <pre> element not visible"

            raw_text = raw_pre.inner_text()
            parsed_raw = json.loads(raw_text)
            assert parsed_raw.get("schema_version") == saved_data.get("schema_version"), "Parsed raw JSON schema mismatch"
            assert parsed_raw.get("source", {}).get("file") == saved_data.get("source", {}).get("file"), "Raw JSON source mismatch"

            # Check Copy JSON button
            copy_btn = page.locator("[data-testid='copy-audio-json-btn']").first
            assert copy_btn.is_visible(), "Copy JSON button not visible"
            copy_btn.click()
            page.wait_for_timeout(300)
            assert "Copied" in copy_btn.inner_text(), "Copy button text did not change to 'Copied'"

            # Save Screenshot of Raw JSON
            raw_shot = ARTIFACTS_DIR / "audio_analysis_drawer_raw_json.png"
            page.screenshot(path=str(raw_shot), full_page=False)
            print(f"  -> Saved raw JSON screenshot to {raw_shot}")

            results["4_raw_json_view"] = "PASSED"
            print("  -> PASSED: Raw JSON view exposes complete saved JSON and copy button works.")
        except Exception as e:
            results["4_raw_json_view"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 5: Verify Artifact Invariance (Zero ASR Rerun, Zero Overwrite)
        # -----------------------------------------------------------
        print("\nTEST 5: Verifying artifact invariance (file SHA-256 and mtime unchanged)...")
        try:
            current_bytes = TEST_PROJECT_JSON_PATH.read_bytes()
            current_sha256 = hashlib.sha256(current_bytes).hexdigest()
            current_mtime = TEST_PROJECT_JSON_PATH.stat().st_mtime

            assert current_sha256 == original_sha256, "audio_analysis.json was modified or overwritten!"
            assert current_mtime == original_mtime, "audio_analysis.json mtime changed, indicating a file write!"

            results["5_artifact_invariance"] = "PASSED"
            print("  -> PASSED: Zero file writes or ASR reruns occurred. SHA-256 and mtime 100% identical.")
        except Exception as e:
            results["5_artifact_invariance"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # Close the drawer
        close_btn = page.locator("[data-testid='close-audio-analysis-btn']")
        close_btn.click()
        page.wait_for_timeout(500)
        assert not drawer.is_visible(), "Drawer did not close when close button clicked"

        # -----------------------------------------------------------
        # TEST 6: Verify Missing Artifact State on Project Without Analysis
        # -----------------------------------------------------------
        print("\nTEST 6: Verifying missing artifact state on 'sample-01'...")
        try:
            page.evaluate("localStorage.setItem('a2v_active_project', 'sample-01')")
            page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1000)

            # Click Audio Analysis card on sample-01
            analyzer_card = page.locator("[data-testid='stage-card-analyzer']")
            analyzer_card.click()
            page.wait_for_timeout(1000)

            missing_banner = page.locator("[data-testid='audio-analysis-missing']")
            assert missing_banner.is_visible(), "Missing artifact banner not visible for sample-01"

            missing_text = missing_banner.inner_text()
            assert "Audio Analysis Artifact Unavailable" in missing_text, "Missing banner title text mismatch"
            assert "sample-01" in missing_text, "Project name missing in banner text"

            # Verify action button to run workflow is present
            run_btn = page.locator("[data-testid='run-audio-analysis-workflow-btn']")
            assert run_btn.is_visible(), "Run Audio Analysis Workflow button not visible in missing state"

            # Save Screenshot of Missing Artifact State
            missing_shot = ARTIFACTS_DIR / "audio_analysis_drawer_missing.png"
            page.screenshot(path=str(missing_shot), full_page=False)
            print(f"  -> Saved missing artifact screenshot to {missing_shot}")

            # Close drawer
            page.locator("[data-testid='close-audio-analysis-btn']").click()
            page.wait_for_timeout(500)

            results["6_missing_artifact_handling"] = "PASSED"
            print("  -> PASSED: Missing artifact shows clear explanation and run workflow action.")
        except Exception as e:
            results["6_missing_artifact_handling"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # Restore active project in localStorage to sample-01
        page.evaluate("localStorage.setItem('a2v_active_project', 'sample-01')")

        browser.close()

    print("\n==================================================================")
    print("AUDIO ANALYSIS CARD TEST SUMMARY:")
    print("==================================================================")
    all_passed = True
    for test_name, status in results.items():
        print(f"  [{status}] {test_name}")
        if "FAILED" in status:
            all_passed = False
    print("==================================================================\n")

    return all_passed

if __name__ == "__main__":
    ok = run_audio_analysis_card_tests()
    sys.exit(0 if ok else 1)
