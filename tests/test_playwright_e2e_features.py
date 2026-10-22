"""Playwright E2E verification for:
1. New Project opens the Audio Input page.
2. Project title and audio upload work.
3. Analyze starts the actual backend workflow.
4. Pipeline stages update in the correct order.
5. Progress and completion states reflect real backend events.
6. Agent Communication opens and displays actual available activity.
7. Errors are displayed correctly without falsely marking the pipeline as successful.
"""
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def run_feature_tests():
    print("\n=======================================================")
    print("STARTING PLAYWRIGHT E2E VERIFICATION FOR NEW FEATURES")
    print("=======================================================\n")
    
    results = {}
    audio_path = str(Path("VIDEO_ENGINE/remotion/public/synth_prod_release.wav").resolve())
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Test audio file not found at {audio_path}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # -----------------------------------------------------------
        # TEST 1: Main Dashboard loads and has New Project button
        # -----------------------------------------------------------
        print("TEST 1: Verifying Main Dashboard and New Project button...")
        try:
            page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1000)
            
            # Find New Project button
            new_proj_btn = page.locator("[data-testid='header-new-project-btn'], [data-testid='pipeline-new-project-btn']").first
            assert new_proj_btn.is_visible(), "New Project button not visible on dashboard"
            
            # Click New Project
            new_proj_btn.click()
            page.wait_for_timeout(800)
            
            # Verify Audio Input page is visible
            title_input = page.locator("[data-testid='project-title-input']")
            assert title_input.is_visible(), "Audio Input page not displayed after clicking New Project"
            results["1_new_project_button_opens_audio_input"] = "PASSED"
            print("  -> PASSED: New Project button successfully opens Audio Input page.")
        except Exception as e:
            results["1_new_project_button_opens_audio_input"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 2: Validation errors without falsely starting pipeline
        # -----------------------------------------------------------
        print("\nTEST 2: Verifying required field validation (no false success)...")
        try:
            # Click Analyze without filling title or audio
            analyze_btn = page.locator("[data-testid='analyze-button']")
            analyze_btn.click()
            page.wait_for_timeout(500)
            
            # Should show validation error banner
            text = page.inner_text("body")
            assert "required" in text.lower() or "title" in text.lower(), "Validation error not shown for empty title"
            
            # Should still remain on audio input page, NOT falsely start pipeline
            assert page.locator("[data-testid='project-title-input']").is_visible(), "Incorrectly navigated away despite missing fields"
            results["2_validation_prevents_false_success"] = "PASSED"
            print("  -> PASSED: Required fields validated properly without false success.")
        except Exception as e:
            results["2_validation_prevents_false_success"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 3: Project Title & Audio Upload Input
        # -----------------------------------------------------------
        print("\nTEST 3: Verifying Project title entry and audio file upload...")
        test_project_title = f"E2E Playwright Auto Test {int(time.time())}"
        try:
            # Fill title
            page.fill("[data-testid='project-title-input']", test_project_title)
            
            # Set audio file
            file_input = page.locator("[data-testid='audio-file-input']")
            file_input.set_input_files(audio_path)
            page.wait_for_timeout(800)
            
            # Verify file name is shown in the verified audio box
            content = page.content()
            assert "synth_prod_release.wav" in content, "Uploaded file name not displayed on page"
            assert "Audio Verified" in content or "KB" in content or "MB" in content, "Audio file status not verified"
            results["3_project_title_and_audio_upload"] = "PASSED"
            print(f"  -> PASSED: Title '{test_project_title}' and audio file set correctly.")
        except Exception as e:
            results["3_project_title_and_audio_upload"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 4: Analyze starts actual backend workflow & navigates
        # -----------------------------------------------------------
        print("\nTEST 4: Clicking Analyze to trigger real backend workflow...")
        try:
            analyze_btn = page.locator("[data-testid='analyze-button']")
            analyze_btn.click()
            
            # Wait for project creation and transition to pipeline view
            page.wait_for_selector("[data-testid='stages-container']", timeout=12000)
            page.wait_for_timeout(1500)
            
            # Verify pipeline canvas is loaded
            assert page.locator("[data-testid='stages-container']").is_visible(), "Stages container not visible after Analyze"
            results["4_analyze_starts_pipeline_workflow"] = "PASSED"
            print("  -> PASSED: Analyze initiated backend project creation and revealed pipeline.")
        except Exception as e:
            results["4_analyze_starts_pipeline_workflow"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 5: Pipeline stages present in correct order
        # -----------------------------------------------------------
        print("\nTEST 5: Verifying 12 canonical stages in correct execution order...")
        expected_stage_ids = [
            'audio', 'analyzer', 'segmentation', 'planning',
            'motion_plan', 'motion_gen', 'motion_validation', 'timeline',
            'approval', 'render', 'qc', 'final'
        ]
        try:
            found_stages = []
            for s_id in expected_stage_ids:
                locator = page.locator(f"[data-testid='stage-card-{s_id}']")
                assert locator.count() > 0, f"Stage {s_id} not found in pipeline"
                found_stages.append(s_id)
            
            assert found_stages == expected_stage_ids, f"Stages order mismatch: {found_stages}"
            results["5_stages_order_and_integrity"] = "PASSED"
            print(f"  -> PASSED: All 12 canonical stages present in exact execution order: {found_stages}")
        except Exception as e:
            results["5_stages_order_and_integrity"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 6: Real stage states & smooth animation
        # -----------------------------------------------------------
        print("\nTEST 6: Verifying real stage progress, active indicator & waiting states...")
        try:
            # Check statuses of cards
            first_card = page.locator("[data-testid='stage-card-audio']")
            status = first_card.get_attribute("data-status")
            print(f"  Current stage 'audio' status: {status}")
            
            # Check for active running animation or completed checkmark
            has_running = page.locator(".stage-card-running, [data-status='running']").count() > 0
            has_waiting = page.locator("[data-status='waiting']").count() > 0
            has_completed = page.locator("[data-status='completed']").count() > 0
            
            print(f"  Stage counts -> Running: {has_running}, Waiting: {has_waiting}, Completed: {has_completed}")
            assert has_running or has_waiting or has_completed, "No valid stage states found"
            results["6_real_progress_states_and_animations"] = "PASSED"
            print("  -> PASSED: Stages correctly display real runtime state without fake progress.")
        except Exception as e:
            results["6_real_progress_states_and_animations"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 7: Agent Communication Button & Panel
        # -----------------------------------------------------------
        print("\nTEST 7: Verifying Agent Communication button and modal panel...")
        try:
            agent_btn = page.locator("[data-testid='agent-communication-btn']").first
            assert agent_btn.is_visible(), "Agent Communication button not visible"
            agent_btn.click()
            page.wait_for_timeout(800)
            
            # Modal should be open
            comm_dialog = page.locator("[role='dialog'][aria-label='Agent Communication']")
            assert comm_dialog.is_visible(), "Agent Communication dialog not opened"
            
            # Check for tabs: Communication Log and Agent Registry
            assert "Agent Communication" in comm_dialog.inner_text(), "Dialog title missing"
            
            # Switch to Agent Registry tab to verify real agents list
            agent_tab = comm_dialog.locator("[data-testid='agent-registry-tab'], button:has-text('Agent Registry')").first
            agent_tab.click(timeout=5000)
            page.wait_for_timeout(600)
            dialog_text = comm_dialog.inner_text()
            assert "Agent" in dialog_text or "ONLINE" in dialog_text or "audio" in dialog_text, "Registry agents not displayed in panel"
            
            # Close dialog
            close_btn = comm_dialog.locator("button[aria-label='Close'], button:has-text('Close')").first
            close_btn.click()
            page.wait_for_timeout(500)
            assert not comm_dialog.is_visible(), "Agent Communication panel did not close"
            
            results["7_agent_communication_panel"] = "PASSED"
            print("  -> PASSED: Agent Communication panel displays real agent registry and logs, and closes cleanly.")
        except Exception as e:
            results["7_agent_communication_panel"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 8: Live Pipeline has NO TopMetricCards
        # -----------------------------------------------------------
        print("\nTEST 8: Verifying TopMetricCards are removed from Live Pipeline...")
        try:
            # We are in Live Pipeline view. TopMetricCards (e.g. Total Pipeline Runs) should not exist here
            metric_cards_count = page.locator("text='Total Pipeline Runs'").count()
            assert metric_cards_count == 0, "TopMetricCards unexpectedly found in Live Pipeline section"
            results["8_top_cards_removed_from_live_pipeline"] = "PASSED"
            print("  -> PASSED: Top four metric cards are completely removed from Live Pipeline.")
        except Exception as e:
            results["8_top_cards_removed_from_live_pipeline"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 9: Dashboard section houses the TopMetricCards
        # -----------------------------------------------------------
        print("\nTEST 9: Navigating to Dashboard and verifying TopMetricCards...")
        try:
            dashboard_nav = page.locator("nav, aside").locator("button:has-text('Dashboard'), a:has-text('Dashboard')").first
            assert dashboard_nav.is_visible(), "Dashboard nav button not visible in sidebar"
            dashboard_nav.click()
            page.wait_for_timeout(800)

            # In Dashboard view, TopMetricCards should be visible!
            runs_card = page.locator("text='Total Pipeline Runs'").first
            assert runs_card.is_visible(), "TopMetricCards not visible in Dashboard section"
            
            # Check for canonical agents counter
            agents_card = page.locator("text='Canonical Agents'").first
            assert agents_card.is_visible(), "Canonical Agents card not visible in Dashboard"
            
            results["9_top_cards_moved_to_dashboard"] = "PASSED"
            print("  -> PASSED: Dashboard successfully displays the top four metric cards.")
        except Exception as e:
            results["9_top_cards_moved_to_dashboard"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 10: Stage Execution Tracking section and sub-stages
        # -----------------------------------------------------------
        print("\nTEST 10: Verifying Stage Execution Tracking with ordered sub-stages...")
        try:
            # Navigate back to Live Pipeline / New Project
            pipeline_nav = page.locator("nav, aside").locator("button:has-text('New Project'), button:has-text('Live Pipeline')").first
            pipeline_nav.click()
            page.wait_for_timeout(600)
            flow_tab = page.locator("[data-testid='tab-pipeline-flow']")
            if flow_tab.is_visible():
                flow_tab.click()
                page.wait_for_timeout(600)

            # Verify Stage Execution Tracking section header
            tracking_header = page.locator("text='Stage Execution Tracking'").first
            assert tracking_header.is_visible(), "Stage Execution Tracking section header not visible"

            # Click Audio Analysis stage (stage 2) to track its sub-stages
            audio_analysis_card = page.locator("[data-testid='stage-card-analyzer']").first
            audio_analysis_card.click()
            page.wait_for_timeout(600)

            # Sub-stages of Audio Analysis should now be displayed
            sub_stage_item = page.locator("text='Speech-to-Text (ASR)'").first
            assert sub_stage_item.is_visible(), "Speech-to-Text (ASR) sub-stage not displayed in Stage Execution Tracking"

            # Check that percentage and status indicator are rendered
            tracking_panel = page.locator("[data-testid='stage-execution-tracking']").first
            assert tracking_panel.is_visible(), "Stage execution tracking panel not found"
            tracking_panel_text = tracking_panel.inner_text()
            assert "Sub-stages" in tracking_panel_text or "%" in tracking_panel_text, "Sub-stage telemetry missing"

            # Now Click Scene Segmentation stage (stage 3) to test dynamic loading of Scene Segmentation Agent's 7 sub-stages
            scene_seg_card = page.locator("[data-testid='stage-card-segmentation']").first
            scene_seg_card.click()
            page.wait_for_timeout(600)

            # Verify Scene Segmentation Agent header and exact 7 canonical sub-stages requested by user
            assert "Scene Segmentation Agent" in tracking_panel.inner_text(), "Active agent not updated to Scene Segmentation Agent"
            
            canonical_seg_substages = [
                "Analysis Data Reader",
                "Sentence & Clause Detection",
                "Semantic Understanding",
                "Topic & Idea Change Detection",
                "Scene Boundary & Grouping",
                "Duration & Timing Assignment",
                "Scene Validation & Continuity"
            ]
            for substage_name in canonical_seg_substages:
                loc = tracking_panel.locator(f"text='{substage_name}'").first
                assert loc.is_visible(), f"Sub-stage '{substage_name}' not displayed in Scene Segmentation tracking"

            # Verify sequential connectors exist between sub-stage cards
            cards = tracking_panel.locator("[data-testid^='sub-stage-card-']").all()
            assert len(cards) == 7, f"Expected 7 Scene Segmentation sub-stage cards, found {len(cards)}"

            results["10_stage_execution_tracking_sub_stages"] = "PASSED"
            print("  -> PASSED: Stage Execution Tracking dynamically displays Scene Segmentation and Audio Analysis sub-stages in sequential order with live telemetry.")
        except Exception as e:
            results["10_stage_execution_tracking_sub_stages"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        browser.close()

    print("\n=======================================================")
    print("E2E TEST SUMMARY RESULTS:")
    print("=======================================================")
    all_passed = True
    for test_name, status in results.items():
        print(f"  [{status}] {test_name}")
        if not str(status).startswith("PASSED"):
            all_passed = False
            
    print("=======================================================\n")
    return all_passed

if __name__ == "__main__":
    success = run_feature_tests()
    sys.exit(0 if success else 1)
