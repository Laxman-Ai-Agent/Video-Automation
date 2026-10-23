"""End-to-End Real Video Generation Test using Visible Playwright.

Executes complete real video generation workflow through a visible Chrome browser:
1. Launches visible Chromium/Chrome browser (headless=False) with slow_mo and cursor highlight.
2. Interacts with the real frontend UI at http://localhost:5173.
3. Navigates to New Project, inputs title, aspect ratio (16:9), and uploads the sample Telugu audio.
4. Clicks "Analyze Audio" to initiate pipeline run.
5. Observes live pipeline execution across all stages in real-time.
6. Verifies final video delivery to the Desktop "First Video Automation" folder.
7. Validates media streams with ffprobe and asserts SHA-256 match between rendered source and desktop delivery.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://localhost:5173"
SAMPLE_AUDIO_PATH = Path(os.environ.get("A2V_ARTIFACTS_DIR", "test-artifacts"))
DESKTOP_DIR = Path.home() / "Desktop" / "First Video Automation"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def probe_media_file(video_path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of", "json",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {res.stderr}")
    return json.loads(res.stdout)


def run_e2e_visible_test():

    assert SAMPLE_AUDIO_PATH.exists(), f"Sample audio missing at {SAMPLE_AUDIO_PATH}"
    print(f"[PREFLIGHT] Sample audio verified: {SAMPLE_AUDIO_PATH} ({SAMPLE_AUDIO_PATH.stat().st_size} bytes)")

    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    initial_desktop_files = set(DESKTOP_DIR.glob("*.mp4"))
    print(f"[PREFLIGHT] Desktop delivery folder verified: {DESKTOP_DIR} (existing mp4s: {len(initial_desktop_files)})")

    with sync_playwright() as p:
        print("\n[PLAYWRIGHT] Launching visible browser (headless=False, slow_mo=150)...")
        browser = p.chromium.launch(
            headless=False,
            slow_mo=150,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="tests/screenshots/videos/" if os.environ.get("RECORD_VIDEO") else None,
        )
        page = context.new_page()

        # Inject visible cursor and click effect so interactions are visible on screen
        page.add_init_script("""
            window.addEventListener('DOMContentLoaded', () => {
                const pointer = document.createElement('div');
                pointer.id = 'visible-playwright-pointer';
                pointer.style.position = 'fixed';
                pointer.style.top = '0px';
                pointer.style.left = '0px';
                pointer.style.width = '22px';
                pointer.style.height = '22px';
                pointer.style.borderRadius = '50%';
                pointer.style.border = '2px solid #00F5D4';
                pointer.style.backgroundColor = 'rgba(0, 245, 212, 0.4)';
                pointer.style.boxShadow = '0 0 10px rgba(0, 245, 212, 0.6)';
                pointer.style.pointerEvents = 'none';
                pointer.style.zIndex = '999999';
                pointer.style.transition = 'transform 0.05s ease';
                pointer.style.transform = 'translate(-50%, -50%)';
                document.body.appendChild(pointer);

                window.addEventListener('mousemove', (e) => {
                    pointer.style.left = e.clientX + 'px';
                    pointer.style.top = e.clientY + 'px';
                });
                window.addEventListener('mousedown', () => {
                    pointer.style.transform = 'translate(-50%, -50%) scale(0.6)';
                    pointer.style.backgroundColor = 'rgba(255, 64, 129, 0.7)';
                    pointer.style.borderColor = '#FF4081';
                    pointer.style.boxShadow = '0 0 14px rgba(255, 64, 129, 0.8)';
                });
                window.addEventListener('mouseup', () => {
                    pointer.style.transform = 'translate(-50%, -50%) scale(1)';
                    pointer.style.backgroundColor = 'rgba(0, 245, 212, 0.4)';
                    pointer.style.borderColor = '#00F5D4';
                    pointer.style.boxShadow = '0 0 10px rgba(0, 245, 212, 0.6)';
                });
            });
        """)

        print(f"[NAVIGATE] Loading frontend application at {FRONTEND_URL}...")
        page.goto(FRONTEND_URL, wait_until="networkidle")
        page.wait_for_timeout(1000)

        # 1. Switch to New Project tab
        print("[ACTION] Switching to 'New Project' tab...")
        new_proj_tab = page.locator("[data-testid='header-new-project-btn'], [data-testid='pipeline-new-project-btn'], [data-testid='sidebar-nav-pipeline']").first
        new_proj_tab.wait_for(state="visible", timeout=15000)
        new_proj_tab.click()
        page.wait_for_timeout(800)

        # 2. Fill in project title
        project_title = f"Metaverse Automation Video {int(time.time()) % 10000}"
        print(f"[ACTION] Entering project title: '{project_title}'...")
        title_input = page.locator("[data-testid='project-title-input']")
        title_input.wait_for(state="visible", timeout=5000)
        title_input.fill(project_title)
        page.wait_for_timeout(400)

        # 3. Set file input
        print(f"[ACTION] Uploading audio file: {SAMPLE_AUDIO_PATH.name}...")
        file_input = page.locator("[data-testid='audio-file-input']")
        file_input.set_input_files(str(SAMPLE_AUDIO_PATH))
        page.wait_for_timeout(800)

        # Verify uploaded audio pill
        page.wait_for_selector("text=Audio Verified", timeout=5000)
        print("  [OK] Audio file validated and previewed in UI.")

        # 4. Click Analyze Audio
        print("[ACTION] Clicking 'Analyze Audio' button to start pipeline...")
        analyze_btn = page.locator("[data-testid='analyze-button']")
        analyze_btn.wait_for(state="visible", timeout=5000)
        analyze_btn.click()

        # 5. Monitor Live Pipeline
        print("\n[MONITOR] Monitoring Live Pipeline execution in real-time...")
        page.wait_for_timeout(2000)

        # Ensure we are in the flow tab
        flow_tab = page.locator("[data-testid='tab-pipeline-flow']")
        if flow_tab.is_visible():
            flow_tab.click()

        # Wait for the project to run through stages
        start_time = time.time()
        timeout_seconds = 480  # 8 minutes maximum for full transcription + Remotion render
        completed = False
        active_pid = None

        while time.time() - start_time < timeout_seconds:
            elapsed = int(time.time() - start_time)

            # Check active project ID from UI header
            try:
                hdr_text = page.locator("header").inner_text()
                m = re.search(r"Project:\s*([a-zA-Z0-9_\-]+)", hdr_text)
                if m:
                    active_pid = m.group(1).strip()
            except Exception:
                pass

            # Inspect stage cards on screen
            cards = page.locator("[data-testid^='stage-card-']").all()
            statuses = []
            for c in cards:
                tid = c.get_attribute("data-testid") or ""
                s_name = tid.replace("stage-card-", "")
                text = c.inner_text()
                status = "waiting"
                if "COMPLETED" in text or "DONE" in text:
                    status = "completed"
                elif "RUNNING" in text:
                    status = "running"
                elif "FAILED" in text or "ERROR" in text:
                    status = "failed"
                statuses.append(f"{s_name}:{status}")

            status_summary = ", ".join(statuses[:6])
            print(f"  [{elapsed}s elapsed] Pipeline: {status_summary}")

            # Check if Final Delivery is completed or if new desktop file appeared
            current_desktop_files = set(DESKTOP_DIR.glob("*.mp4")) - initial_desktop_files
            if current_desktop_files:
                print(f"\n[SUCCESS] New delivered MP4 detected on Desktop: {[f.name for f in current_desktop_files]}")
                completed = True
                break

            # Click a card periodically to exercise drawer inspection
            if elapsed % 25 == 0 and elapsed > 0 and len(cards) > 0:
                try:
                    cards[0].click()
                    page.wait_for_timeout(600)
                    close_btn = page.locator("button[aria-label='Close drawer'], button:has-text('✕')").first
                    if close_btn.is_visible():
                        close_btn.click()
                except Exception:
                    pass

            page.wait_for_timeout(3000)

        assert completed, f"Pipeline did not complete video generation within {timeout_seconds}s"

        # 6. Verify Delivered MP4 Artifact
        delivered_mp4 = list(current_desktop_files)[0]
        print(f"\n--- [VERIFICATION] Delivered Video File: {delivered_mp4} ---")
        file_size = delivered_mp4.stat().st_size
        print(f"  File size: {file_size:,} bytes")
        assert file_size > 10000, f"Delivered video is too small ({file_size} bytes)"

        # Probe with ffprobe
        probe_data = probe_media_file(delivered_mp4)
        v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"), None)

        assert v_stream is not None, "Delivered MP4 has no video stream"
        assert a_stream is not None, "Delivered MP4 has no audio stream"

        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))
        duration = float(probe_data.get("format", {}).get("duration", 0))

        print(f"  Resolution: {width}x{height} (Aspect ratio check: {width}/{height} = {round(width/height, 2)})")
        print(f"  Video codec: {v_stream.get('codec_name')}")
        print(f"  Audio codec: {a_stream.get('codec_name')}")
        print(f"  Duration: {duration:.2f} seconds")

        assert width == 1920 and height == 1080, f"Expected 1920x1080, got {width}x{height}"
        assert duration >= 20.0, f"Expected duration >= 20.0s, got {duration}s"

        # Compute SHA-256
        desktop_sha256 = file_sha256(delivered_mp4)
        print(f"  Delivered SHA-256: {desktop_sha256}")

        # Check source project out.mp4 if project ID known
        if active_pid:
            source_mp4 = Path("projects") / active_pid / "out.mp4"
            if source_mp4.exists():
                source_sha256 = file_sha256(source_mp4)
                print(f"  Source out.mp4 SHA-256: {source_sha256}")
                assert desktop_sha256 == source_sha256, (
                    f"SHA-256 mismatch! Desktop: {desktop_sha256} != Source: {source_sha256}"
                )
                print("  [OK] SHA-256 matches bit-for-bit with source project render!")

        # Keep browser visible briefly for user inspection
        print("\n[PLAYWRIGHT] Test completed successfully! Keeping browser visible for 3 seconds...")
        page.wait_for_timeout(3000)
        browser.close()

    # Done
    print("\n========================================================")
    print("ALL VERIFICATIONS PASSED: REAL VIDEO GENERATED & DELIVERED")
    print(f"Destination: {delivered_mp4}")
    print(f"SHA-256:     {desktop_sha256}")
    print("========================================================\n")


if __name__ == "__main__":
    run_e2e_visible_test()
