"""E2E test for running a simulation in the Control Panel.

Note: This test requires:
1. The Streamlit app to be running (make run)
2. Environment variables: E2E_INSTRUCTOR_EMAIL, E2E_INSTRUCTOR_PASSWORD, E2E_OPENAI_API_KEY
3. A compatible Python version for pyautogen (< 3.14 as of 2024)

The test creates test data (game, students, prompts), runs a simulation via the UI,
and cleans up afterward.
"""

import psycopg2
import pytest


@pytest.mark.e2e
class TestRunSimulation:
    """Test the run simulation flow for instructors."""

    def test_run_simulation_completes(
        self, instructor_page, simulation_test_game, openai_api_key, database_url
    ):
        """Test that an instructor can run a simulation.

        Steps:
        1. Log in as instructor (handled by fixture)
        2. Navigate to Control Panel
        3. Click "Run Simulation" button
        4. Select the test game
        5. Fill simulation form with minimal settings
        6. Click Run Simulation
        7. Wait for completion message (success or partial failure)

        The test passes if the simulation completes (either successfully
        or with some failed negotiations), as this validates the full
        simulation pipeline is working.
        """
        page = instructor_page
        game_data = simulation_test_game

        # Navigate to Control Panel (fixture creates data via DB, page is at home)
        page.get_by_role("link", name="Control Panel").click()
        page.wait_for_selector("text=Welcome, Instructor!", timeout=30000)

        # Click "Run Simulation" button (matches "Run Simulation" or "▶️ Run Simulation")
        page.get_by_role("button").filter(has_text="Run Simulation").click()
        page.wait_for_selector("text=Run Simulation", timeout=30000)

        # Select academic year
        # Find the academic year dropdown and select the correct year
        year_select = page.locator("[data-testid='stSelectbox']").first
        year_select.locator("div[data-baseweb='select']").click()
        # academic_year is stored as int in fixture, convert to string for UI
        page.get_by_role("option", name=str(game_data["academic_year"])).click()

        # Select the test game from dropdown
        # The game dropdown should appear after selecting the year
        game_select = page.locator("[data-testid='stSelectbox']").nth(1)
        game_select.locator("div[data-baseweb='select']").click()

        # Game name includes class suffix: "E2E_Sim_Test_xxx - Class E2E"
        game_option_name = f"{game_data['game_name']} - Class {game_data['class_']}"
        page.get_by_role("option", name=game_option_name).click()

        # Select "Simulation" radio button (should be default, but click to ensure)
        # Streamlit radio inputs are hidden, need to click the label
        page.locator("label").filter(has_text="Simulation").click()

        # Wait for the simulation form to appear
        page.wait_for_selector("text=API Key", timeout=30000)

        # Fill out the simulation form
        # API Key
        page.get_by_label("API Key").fill(openai_api_key)

        # Model - use gpt-4o-mini for lower cost and faster response
        # The selectbox should default to gpt-4o-mini, but let's ensure
        model_select = page.locator("[data-testid='stSelectbox']").filter(
            has_text="OpenAI Model"
        )
        model_select.locator("div[data-baseweb='select']").click()
        page.get_by_role("option", name="gpt-4o-mini").click()

        # Number of Rounds - use 1 for speed
        rounds_input = page.get_by_label("Number of Rounds")
        rounds_input.fill("1")

        # Maximum Number of Turns - use minimal value for speed
        turns_input = page.get_by_label("Maximum Number of Turns")
        turns_input.fill("5")

        # Other fields use defaults:
        # - Conversation Starter: default
        # - Starting Message: "Hello, shall we start the negotiation?"
        # - Negotiation Termination Message: "Pleasure doing business with you"
        # - Negotiation Summary Prompt: "What was the value agreed?"
        # - Summary Termination Message: "The value agreed was"

        # Submit the form - click Run button
        page.locator("[data-testid='stFormSubmitButton'] button").click()

        # Wait for result with extended timeout (LLM calls take time)
        # Success: "All negotiations were completed successfully!"
        # Partial: warning message with "were unsuccessful"
        try:
            # Try to detect success message
            page.wait_for_selector(
                "text=All negotiations were completed successfully!",
                timeout=120000,
            )
        except Exception:
            # Check if there's a partial failure warning (still a valid completion)
            try:
                page.wait_for_selector(
                    "text=were unsuccessful",
                    timeout=10000,
                )
            except Exception:
                # If neither success nor partial failure, check for any error
                error_visible = page.locator("text=Please fill out all fields").is_visible()
                attribute_error = page.get_by_text("AttributeError").is_visible()
                exception_visible = page.get_by_text("Exception").is_visible()

                if error_visible:
                    pytest.fail("Form validation failed - missing required fields")
                elif attribute_error:
                    # Get more details about the error
                    error_text = page.locator(".stException").inner_text() if page.locator(".stException").count() > 0 else "AttributeError occurred"
                    pytest.fail(f"AttributeError during simulation: {error_text[:500]}")
                elif exception_visible:
                    error_text = page.locator(".stException").inner_text() if page.locator(".stException").count() > 0 else "Exception occurred"
                    pytest.fail(f"Exception during simulation: {error_text[:500]}")
                else:
                    pytest.fail("Simulation did not complete within timeout")

        # Verify negotiation chats are stored in the database
        conn = psycopg2.connect(database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM negotiation_chat WHERE game_id = %s",
                    (game_data["game_id"],),
                )
                chat_count = cur.fetchone()[0]
                assert (
                    chat_count > 0
                ), f"No negotiation chats stored in database for game {game_data['game_id']}"
        finally:
            conn.close()
