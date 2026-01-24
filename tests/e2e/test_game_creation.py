"""E2E test for game creation flow in the Control Panel."""

import time

import pytest


@pytest.mark.e2e
class TestGameCreation:
    """Test the game creation flow for instructors."""

    def test_create_game(self, instructor_page):
        """Test that an instructor can create a new game.

        Steps:
        1. Log in as instructor (handled by fixture)
        2. Navigate to Control Panel
        3. Click "Create Game" button
        4. Fill out the game creation form
        5. Submit the form
        6. Verify success message appears
        """
        page = instructor_page

        # Navigate to Control Panel using sidebar navigation
        page.get_by_role("link", name="Control Panel").click()

        # Wait for Control Panel to load
        page.wait_for_selector("text=Control Panel", timeout=30000)

        # Click "Create Game" button (matches "Create Game" or "🎮 Create Game")
        page.get_by_role("button").filter(has_text="Create Game").click()

        # Wait for the Create Game form to appear
        page.wait_for_selector("text=Game Name", timeout=30000)

        # Fill out the game creation form
        # Game Name - generate unique name with timestamp
        game_name = f"E2E Test Game {int(time.time())}"
        page.get_by_label("Game Name").fill(game_name)

        # Game Explanation
        page.get_by_label("Game Explanation").fill(
            "This is an automated E2E test game for testing the game creation flow."
        )

        # Game Type - use default (zero_sum), no need to change

        # Role names - use defaults (Buyer/Seller), no need to change

        # Value bounds - use defaults, no need to change

        # Academic Year/Class - first option is selected by default

        # Password (4-digit)
        page.get_by_label("Game Password (4-digit)").fill("1234")

        # Deadline date/time - use defaults (1 week from now), no need to change

        # Submit the form - click the form submit button
        page.locator("[data-testid='stFormSubmitButton'] button").click()

        # Wait for success message or redirect to Available Games
        # The success message appears briefly, then redirects
        try:
            page.wait_for_selector("text=Game created successfully!", timeout=60000)
        except Exception:
            # If we missed the success message, check if we're on Available Games page
            # which indicates successful creation
            page.wait_for_selector("text=Available Games", timeout=30000)
