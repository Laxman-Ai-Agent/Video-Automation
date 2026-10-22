"""Browser smoke tests of the current web UI (UI/frontend). They need the dev servers already running (frontend on 5173, API on 8000) and are skipped otherwise.
Read-only on purpose: they never start an analysis, never upload audio and never confirm a delete (the delete dialog is opened and cancelled)."""
import urllib.request

import pytest

UI, API = "http://localhost:5173", "http://localhost:8000"


def _up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not (_up(UI) and _up(f"{API}/projects")), reason="the dev servers (5173 and 8000) are not running")


@pytest.fixture()
def page():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(UI, wait_until="domcontentloaded")
        yield pg
        browser.close()


def test_app_loads_and_dashboard_lists_projects(page):
    page.get_by_test_id("sidebar-nav-dashboard").click()
    page.get_by_test_id("all-projects-card").click()
    page.get_by_test_id("all-projects-table-container").wait_for()
    rows = page.locator("[data-testid^='project-row-']")
    rows.first.wait_for()
    assert rows.count() >= 1


def test_delete_dialog_opens_and_cancel_closes_it(page):
    page.get_by_test_id("sidebar-nav-dashboard").click()
    page.get_by_test_id("all-projects-card").click()
    page.locator("[data-testid^='delete-project-btn-']").first.click()
    dialog = page.get_by_test_id("delete-confirmation-dialog")
    dialog.wait_for()
    dialog.get_by_role("button", name="Cancel").click()
    dialog.wait_for(state="detached")


def test_audio_input_page_has_the_file_input(page):
    page.get_by_test_id("sidebar-nav-pipeline").click()
    page.get_by_test_id("pill-tab-new-project").click()
    page.get_by_test_id("audio-file-input").wait_for(state="attached")
    assert page.get_by_test_id("project-title-input").is_visible()
