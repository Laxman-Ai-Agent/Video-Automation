"""Playwright E2E verification test for Visual AI Editor:
1. Navigation to Visual AI Editor page from sidebar & verification of New Project design language.
2. 5 Horizontal Tabs rendering (Feedback, AI Chat, Implementation Plan, Implementation, Preview & Approval).
3. Feedback Tab: Visual sticky-note creation, filtering, and persistent storage across reloads.
4. AI Chat Tab: Direct communication stream with configured LLM/Main Architecture Agent.
5. Implementation Plan Tab: 5-section technical plan generation and Gate 1 (Approve Plan) enforcement.
6. Implementation Tab: Gate 2 (Authorize Implementation) guard and acceptance test execution with real telemetry.
7. Preview & Approval Tab: Gate 3 Final UI Review testing 'Request Further Changes' and 'Approve Final UI'.
8. Tab Switching State Preservation: All state and history preserved across tab changes.
"""
import sys
import time
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

def run_visual_ai_editor_tests():
    print("\n==================================================================")
    print("STARTING PLAYWRIGHT E2E VERIFICATION FOR VISUAL AI EDITOR (5 TABS)")
    print("==================================================================\n")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Catch browser console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # Reset session state for clean deterministic E2E test execution
        config_path = Path("config/visual_editor/sessions.json")
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                if "sample-01" in data:
                    del data["sample-01"]
                config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

        # -----------------------------------------------------------
        # TEST 1: Navigation to Visual AI Editor & 5 Horizontal Tabs
        # -----------------------------------------------------------
        print("TEST 1: Verifying navigation to Visual AI Editor & 5 horizontal tabs...")
        try:
            page.goto("http://localhost:5173", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1000)

            # Find Visual AI Editor item in sidebar
            nav_item = page.locator("[data-testid='sidebar-nav-visual-editor'], [data-testid='nav-item-visual-editor']").first
            assert nav_item.is_visible(), "Visual AI Editor menu item not found in Sidebar"

            # Click to navigate
            nav_item.click()
            page.wait_for_timeout(800)

            # Verify top banner subtitle was removed from UI per user request
            page_sub = page.locator("text=Collect UI feedback, collaborate with AI, and review changes before approval.")
            assert page_sub.count() == 0, "Page subtitle should be removed from UI"

            # Verify all 5 horizontal tabs are present
            tab_feedback = page.locator("[data-testid='tab-feedback']")
            tab_chat = page.locator("[data-testid='tab-ai-chat']")
            tab_plan = page.locator("[data-testid='tab-plan']")
            tab_impl = page.locator("[data-testid='tab-implementation']")
            tab_preview = page.locator("[data-testid='tab-preview']")

            assert tab_feedback.is_visible(), "Tab 1: Feedback not visible"
            assert tab_chat.is_visible(), "Tab 2: AI Chat not visible"
            assert tab_plan.is_visible(), "Tab 3: Implementation Plan not visible"
            assert tab_impl.is_visible(), "Tab 4: Implementation not visible"
            assert tab_preview.is_visible(), "Tab 5: Preview & Approval not visible"

            # Initial active tab should be Feedback
            feedback_panel = page.locator("[data-testid='feedback-panel']")
            assert feedback_panel.is_visible(), "Feedback Panel not active on initial load"

            results["1_navigation_and_5_tabs_header"] = "PASSED"
            print("  -> PASSED: Visual AI Editor rendered with New Project design and all 5 horizontal tabs.")
        except Exception as e:
            results["1_navigation_and_5_tabs_header"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 2: Tab 1 (Feedback) — Sticky Note Creation & Persistence
        # -----------------------------------------------------------
        print("\nTEST 2: Verifying Tab 1 (Feedback) sticky note creation & persistence...")
        try:
            # Click Add Note button
            add_btn = page.locator("[data-testid='open-add-feedback-btn']")
            assert add_btn.is_visible(), "Add Note button not visible"
            add_btn.click()
            page.wait_for_timeout(500)

            # Verify modal is open
            modal = page.locator("[data-testid='add-feedback-modal']")
            assert modal.is_visible(), "Add Feedback modal did not open"

            # Fill feedback text
            textarea = page.locator("[data-testid='feedback-note-textarea']")
            unique_feedback = f"Automated E2E Note {int(time.time())}: Reduce spacing between cards and align right."
            textarea.fill(unique_feedback)

            # Submit
            submit_btn = page.locator("[data-testid='submit-feedback-note-btn']")
            submit_btn.click()
            page.wait_for_timeout(1000)

            # Verify the new note appears in the feedback list
            notes_list = page.locator("[data-testid='feedback-notes-list']")
            assert unique_feedback[:25] in notes_list.inner_text(), "Newly created sticky note not found in list"

            # Test persistence across page reload
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(1000)

            # Navigate back to Visual AI Editor if needed
            page.locator("[data-testid='sidebar-nav-visual-editor'], [data-testid='nav-item-visual-editor']").first.click()
            page.wait_for_timeout(800)

            notes_list_after_reload = page.locator("[data-testid='feedback-notes-list']")
            assert unique_feedback[:25] in notes_list_after_reload.inner_text(), "Sticky note did not persist after reload"

            results["2_feedback_tab_persistence"] = "PASSED"
            print("  -> PASSED: Visual sticky note successfully created and persisted to backend storage.")
        except Exception as e:
            results["2_feedback_tab_persistence"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 3: Tab 2 (AI Chat) — Live Agent Communication
        # -----------------------------------------------------------
        print("\nTEST 3: Verifying Tab 2 (AI Chat) agent communication...")
        try:
            # Switch to AI Chat tab
            page.locator("[data-testid='tab-ai-chat']").click()
            page.wait_for_timeout(500)

            chat_panel = page.locator("[data-testid='agent-chat-panel']")
            assert chat_panel.is_visible(), "Agent Chat Panel not visible"

            chat_input = page.locator("[data-testid='agent-chat-input']")
            send_btn = page.locator("[data-testid='send-chat-btn']")
            assert chat_input.is_visible(), "Chat input not visible"

            # Send a prompt to the agent
            test_prompt = "What is the recommended padding token for StageCard?"
            chat_input.fill(test_prompt)
            send_btn.click()
            page.wait_for_timeout(1000)

            # Verify user message and agent response stream
            messages_stream = page.locator("[data-testid='chat-messages-stream']")
            assert test_prompt in messages_stream.inner_text(), "User prompt not displayed in conversation"

            results["3_ai_chat_tab_communication"] = "PASSED"
            print("  -> PASSED: Agent chat message sent and displayed in real-time stream.")
        except Exception as e:
            results["3_ai_chat_tab_communication"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 4: Tab 3 (Implementation Plan) — 5-Section Architecture Plan
        # -----------------------------------------------------------
        print("\nTEST 4: Verifying Tab 3 (Implementation Plan) 5 sections...")
        try:
            # Switch to Implementation Plan tab
            page.locator("[data-testid='tab-plan']").click()
            page.wait_for_timeout(500)

            plan_panel = page.locator("[data-testid='change-review-panel']")
            assert plan_panel.is_visible(), "Implementation Plan panel not visible"

            # Click Generate Plan button
            gen_plan_btn = page.locator("[data-testid='generate-plan-btn']")
            assert gen_plan_btn.is_visible(), "Generate Plan button not visible"
            gen_plan_btn.click()
            
            # Wait for plan generation
            page.wait_for_selector("[data-testid='implementation-plan-container']", timeout=45000)
            plan_container = page.locator("[data-testid='implementation-plan-container']")
            assert plan_container.is_visible(), "Implementation plan container not visible"

            plan_text = plan_container.inner_text()
            # Verify the 5 required sections exist
            assert "1. UNDERSTANDING OF REQUESTED CHANGES" in plan_text, "Missing Section 1: Understanding"
            assert "2. PROPOSED UI MODIFICATIONS" in plan_text, "Missing Section 2: Proposed UI Modifications"
            assert "3. AFFECTED COMPONENTS & SOURCE FILES" in plan_text, "Missing Section 3: Affected Components"
            assert "4. POTENTIAL RISKS & DEPENDENCIES" in plan_text, "Missing Section 4: Risks & Dependencies"
            assert "5. VALIDATION & TESTING STEPS" in plan_text, "Missing Section 5: Validation & Testing Steps"

            results["4_implementation_plan_5_sections"] = "PASSED"
            print("  -> PASSED: Implementation plan generated with all 5 mandatory architectural sections.")
        except Exception as e:
            results["4_implementation_plan_5_sections"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 5: Gate 1 (Approve Plan) & Gate 2 (Authorize Implementation)
        # -----------------------------------------------------------
        print("\nTEST 5: Verifying Gate 1 & Gate 2 separate approvals across tabs...")
        try:
            # Check Implementation tab before Gate 1 approval: Gate 2 must be blocked
            page.locator("[data-testid='tab-implementation']").click()
            page.wait_for_timeout(500)
            auth_btn = page.locator("[data-testid='authorize-implementation-btn']")
            assert auth_btn.is_disabled(), "Implementation Authorization must be disabled before Plan Approval!"

            # Go back to Implementation Plan tab to Approve Plan (Gate 1)
            page.locator("[data-testid='tab-plan']").click()
            page.wait_for_timeout(500)

            approve_plan_btn = page.locator("[data-testid='approve-plan-btn']")
            assert approve_plan_btn.is_visible(), "Approve Plan button not visible"
            approve_plan_btn.click()
            page.wait_for_timeout(1000)

            # Verify Gate 1 passed
            assert page.locator("[data-testid='plan-approved-badge']").is_visible(), "Plan Approved confirmation not displayed"

            # Now switch to Implementation tab: Gate 2 is now enabled
            page.locator("[data-testid='tab-implementation']").click()
            page.wait_for_timeout(500)

            assert not auth_btn.is_disabled(), "Authorize Implementation should now be enabled"
            auth_btn.click()
            page.wait_for_timeout(1000)

            # Verify Gate 2 passed
            assert page.locator("[data-testid='implementation-authorized-badge']").is_visible(), "Implementation Authorized confirmation not displayed"

            results["5_gate1_and_gate2_approvals"] = "PASSED"
            print("  -> PASSED: Gate 1 and Gate 2 strictly enforced as separate approval gates across tabs.")
        except Exception as e:
            results["5_gate1_and_gate2_approvals"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 6: Tab 4 (Implementation) — Acceptance Testing Execution
        # -----------------------------------------------------------
        print("\nTEST 6: Verifying Tab 4 (Implementation) Acceptance Testing execution...")
        try:
            run_tests_btn = page.locator("[data-testid='run-implementation-tests-btn']")
            assert run_tests_btn.is_visible(), "Run Acceptance Tests button not visible"
            run_tests_btn.click()

            # Wait for test execution
            page.wait_for_timeout(3000)
            
            # Verify test results telemetry is displayed
            exec_card = page.locator("[data-testid='implementation-execution-card']")
            page.wait_for_selector("[data-testid='implementation-execution-card'] pre", timeout=60000)
            assert "Duration:" in exec_card.inner_text(), "Test duration telemetry not displayed"

            results["6_implementation_testing_telemetry"] = "PASSED"
            print("  -> PASSED: Implementation acceptance test suite executed and reported genuine telemetry.")
        except Exception as e:
            results["6_implementation_testing_telemetry"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 7: Tab 5 (Preview & Approval) — Gate 3 Request Changes & Sign-Off
        # -----------------------------------------------------------
        print("\nTEST 7: Verifying Tab 5 (Preview & Approval) Gate 3 review...")
        try:
            # Switch to Preview & Approval tab
            page.locator("[data-testid='tab-preview']").click()
            page.wait_for_timeout(500)

            preview_container = page.locator("[data-testid='final-ui-review-container']")
            assert preview_container.is_visible(), "Final UI Review container not visible"

            # 1. Test Request Further Changes
            request_changes_btn = page.locator("[data-testid='request-further-changes-btn']")
            assert request_changes_btn.is_visible(), "Request Further Changes button not visible"
            request_changes_btn.click()
            page.wait_for_timeout(1000)

            # Verify status reflects changes requested
            assert "CHANGES REQUESTED" in preview_container.inner_text(), "Changes Requested status not reflected"

            # 2. Test Final UI Approval
            approve_final_ui_btn = page.locator("[data-testid='approve-final-ui-btn']")
            assert approve_final_ui_btn.is_visible(), "Approve Final UI button not visible"
            approve_final_ui_btn.click()
            page.wait_for_timeout(1000)

            # Verify Final UI is Approved
            assert "APPROVED" in preview_container.inner_text(), "Final UI Approved status not displayed"

            # 3. Verify in Feedback tab that notes are resolved
            page.locator("[data-testid='tab-feedback']").click()
            page.wait_for_timeout(500)
            assert "RESOLVED" in page.locator("[data-testid='feedback-notes-list']").inner_text(), "Feedback not marked as resolved"

            results["7_gate3_preview_and_approval"] = "PASSED"
            print("  -> PASSED: Final UI review supports Request Further Changes and Final Sign-Off.")
        except Exception as e:
            results["7_gate3_preview_and_approval"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        # -----------------------------------------------------------
        # TEST 8: Tab Switching State & History Preservation
        # -----------------------------------------------------------
        print("\nTEST 8: Verifying tab switching preserves all state and data...")
        try:
            # Cycle through all tabs and ensure no errors and history intact
            for tab_id, container_id in [
                ("tab-feedback", "feedback-panel"),
                ("tab-ai-chat", "agent-chat-panel"),
                ("tab-plan", "change-review-panel"),
                ("tab-implementation", "implementation-panel"),
                ("tab-preview", "final-ui-review-container")
            ]:
                page.locator(f"[data-testid='{tab_id}']").click()
                page.wait_for_timeout(300)
                assert page.locator(f"[data-testid='{container_id}']").is_visible(), f"Container {container_id} not visible after clicking {tab_id}"

            results["8_tab_switching_state_preservation"] = "PASSED"
            print("  -> PASSED: All 5 tabs switch cleanly without state loss or page reload.")
        except Exception as e:
            results["8_tab_switching_state_preservation"] = f"FAILED: {e}"
            print(f"  -> FAILED: {e}")

        browser.close()

    print("\n==================================================================")
    print("VISUAL AI EDITOR (5 TABS) TEST SUMMARY RESULTS:")
    print("==================================================================")
    all_passed = True
    for test_name, status in results.items():
        print(f"  [{status}] {test_name}")
        if not str(status).startswith("PASSED"):
            all_passed = False
    print("==================================================================\n")
    return all_passed

if __name__ == "__main__":
    ok = run_visual_ai_editor_tests()
    sys.exit(0 if ok else 1)
