"""Example E2E test to verify Playwright setup is working."""

import pytest


@pytest.mark.e2e
class TestPlaywrightSetup:
    """Basic tests to verify Playwright is configured correctly."""

    def test_app_loads(self, app_page):
        """Verify the Streamlit app loads successfully."""
        # Check that the page title is present
        assert app_page.title() is not None

        # Verify Streamlit app container is rendered
        app_container = app_page.locator("[data-testid='stApp']")
        assert app_container.is_visible()

    def test_page_has_content(self, app_page):
        """Verify the page has some content loaded."""
        # Wait for any content to appear
        app_page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=10000)

        # Check that the main content area exists
        content = app_page.locator("[data-testid='stAppViewContainer']")
        assert content.is_visible()
