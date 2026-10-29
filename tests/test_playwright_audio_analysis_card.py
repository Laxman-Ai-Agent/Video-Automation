"""Playwright E2E verification test for the Audio Analysis stage view (Stage 01):
1. Clicking the Audio Analysis card opens the full-page stage view.
2. The Audio Metadata subtab displays actual saved audio_analysis.json data (duration, sample rate, file name).
3. The Transcript subtab shows the real transcript text and utterance cards.
4. The Raw JSON subtab exposes the complete saved JSON.
5. Opening the card does NOT trigger new ASR or modify/overwrite audio_analysis.json (hash & mtime preserved).
6. A project with no completed Audio Analysis (sample-01) leaves the stage card disabled, not openable.
"""
import os
import json
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
# All 12 stages are completed for this project, so every stage card is clickable
# (a fresh project's later cards are disabled until their prior stage finishes).
TEST_PROJECT_ID = "my-first-project-01-df7f"
TEST_PROJECT_JSON_PATH = Path("projects") / TEST_PROJECT_ID / "audio_analysis.json"

def test_audio_analysis_card():
    artifacts_dir = ARTIFACTS_DIR
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    assert TEST_PROJECT_JSON_PATH.exists(), f"Expected test artifact not found at {TEST_PROJECT_JSON_PATH}"
    original_bytes = TEST_PROJECT_JSON_PATH.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    original_mtime = TEST_PROJECT_JSON_PATH.stat().st_mtime
    saved_data = json.loads(original_bytes.decode("utf-8"))
    expected_full_text = saved_data["transcription"]["full_text"]
    expected_file = saved_data["source"]["file"]
    expected_sample_rate = saved_data["source"]["sample_rate_hz"]
    expected_duration = saved_data["source"]["duration_seconds"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # TEST 1: open the project with a completed audio_analysis.json
        page.goto(f"http://localhost:5173/?projectId={TEST_PROJECT_ID}", wait_until="load")
        page.locator("[data-testid='stage-card-analyzer']").wait_for(state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        header = page.locator("header")
        assert TEST_PROJECT_ID in header.inner_text(), f"Header does not display active project {TEST_PROJECT_ID}"

        # TEST 2: click the Audio Analysis card, verify the full-page stage view opens
        analyzer_card = page.locator("[data-testid='stage-card-analyzer']")
        assert analyzer_card.is_visible(), "Audio Analysis stage card not visible in pipeline grid"
        analyzer_card.click()
        page.wait_for_timeout(1000)

        fullpage = page.locator("[data-testid='pipeline-stage-fullpage-container']")
        assert fullpage.is_visible(), "Audio Analysis full-page view did not open on card click"
        assert "Audio Analysis" in fullpage.inner_text(), "Stage title missing in full-page header"

        # The audio subtabs live under the "Audio & Transcript" tab (the view opens on Subtasks)
        page.locator("[data-testid='stage-drawer-tab-scenes']").click()
        page.wait_for_timeout(600)

        # The Overview/metadata subtab shows truthful values matching the saved JSON
        overview_tab = page.locator("[data-testid='audio-subtab-overview']")
        overview_tab.click()
        page.wait_for_timeout(500)
        overview_text = page.locator("[data-testid='audio-analyzer-view']").inner_text()
        assert expected_file in overview_text, f"File name '{expected_file}' not displayed"
        assert f"{expected_sample_rate} Hz" in overview_text, f"Sample rate '{expected_sample_rate} Hz' not displayed"
        assert f"{expected_duration:.2f}s" in overview_text, f"Duration '{expected_duration}s' not displayed"

        page.screenshot(path=str(artifacts_dir / "audio_analysis_overview.png"), full_page=False)

        # TEST 3: Transcript subtab shows the real transcript text and utterance cards
        transcript_tab = page.locator("[data-testid='audio-subtab-transcript']")
        transcript_tab.click()
        page.wait_for_timeout(600)

        first_words = expected_full_text[:30]
        assert first_words in page.content(), "Expected transcript snippet not found in the transcript subtab"

        utterance_card_0 = page.locator("[data-testid='utterance-card-0']")
        assert utterance_card_0.is_visible(), "Utterance card 0 not visible"

        page.screenshot(path=str(artifacts_dir / "audio_analysis_transcript.png"), full_page=False)

        # TEST 4: Raw JSON subtab exposes the complete saved JSON
        raw_tab = page.locator("[data-testid='audio-subtab-raw']")
        raw_tab.click()
        page.wait_for_timeout(600)

        raw_pre = page.locator("[data-testid='audio-analyzer-view'] pre")
        assert raw_pre.is_visible(), "Raw JSON <pre> element not visible"
        parsed_raw = json.loads(raw_pre.inner_text())
        assert parsed_raw.get("schema_version") == saved_data.get("schema_version"), "Raw JSON schema_version mismatch"
        assert parsed_raw.get("source", {}).get("file") == expected_file, "Raw JSON source.file mismatch"

        copy_btn = page.locator("button:has-text('Copy JSON')").first
        assert copy_btn.is_visible(), "Copy JSON button not visible"

        page.screenshot(path=str(artifacts_dir / "audio_analysis_raw_json.png"), full_page=False)

        # TEST 5: opening the view never triggers an ASR rerun or overwrites the artifact
        current_bytes = TEST_PROJECT_JSON_PATH.read_bytes()
        assert hashlib.sha256(current_bytes).hexdigest() == original_sha256, "audio_analysis.json was modified or overwritten"
        assert TEST_PROJECT_JSON_PATH.stat().st_mtime == original_mtime, "audio_analysis.json mtime changed, indicating a file write"

        # Back to the pipeline
        page.locator("[data-testid='stage-drawer-back-btn']").first.click()
        page.wait_for_timeout(500)
        assert not fullpage.is_visible(), "Full-page view did not close on Back to Pipeline"

        # TEST 6: a project with no completed Audio Analysis leaves the card disabled, not openable
        # (the current UI gates the card itself rather than showing an in-view "missing artifact" banner).
        page.goto("http://localhost:5173/?projectId=sample-01", wait_until="load")
        page.locator("[data-testid='stage-card-analyzer']").wait_for(state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        sample_card = page.locator("[data-testid='stage-card-analyzer']")
        assert sample_card.is_visible(), "Audio Analysis stage card not visible for sample-01"
        assert sample_card.get_attribute("aria-disabled") == "true", "Audio Analysis card should be disabled when no audio is uploaded"
        assert "Waiting for Audio Input" in sample_card.inner_text(), "Card does not explain it is waiting for audio upload"

        page.screenshot(path=str(artifacts_dir / "audio_analysis_disabled_card.png"), full_page=False)

        browser.close()

if __name__ == "__main__":
    test_audio_analysis_card()
    print("All Audio Analysis card tests passed.")
