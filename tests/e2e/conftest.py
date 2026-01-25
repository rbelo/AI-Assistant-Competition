"""Playwright fixtures and configuration for E2E tests."""

import os
import time
from pathlib import Path

import psycopg2
import pytest
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


# Default base URL for Streamlit app
DEFAULT_BASE_URL = "http://localhost:8501"


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the Streamlit application.

    Can be overridden with the E2E_BASE_URL environment variable.
    """
    return os.environ.get("E2E_BASE_URL", DEFAULT_BASE_URL)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context settings."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture
def app_page(page, base_url):
    """Navigate to the app's home page and wait for it to load."""
    page.goto(base_url)
    # Wait for Streamlit to finish loading
    page.wait_for_selector("[data-testid='stApp']", timeout=30000)
    return page


@pytest.fixture
def authenticated_page(app_page):
    """A page fixture that handles authentication.

    Override this fixture to implement actual login logic
    when authentication tests are needed.
    """
    # Placeholder for authentication logic
    # Implement actual login steps when needed
    return app_page


@pytest.fixture(scope="session")
def instructor_credentials():
    """Read instructor credentials from environment variables.

    Requires E2E_INSTRUCTOR_EMAIL and E2E_INSTRUCTOR_PASSWORD to be set.
    """
    email = os.environ.get("E2E_INSTRUCTOR_EMAIL")
    password = os.environ.get("E2E_INSTRUCTOR_PASSWORD")

    if not email or not password:
        pytest.skip(
            "Instructor credentials not available. "
            "Set E2E_INSTRUCTOR_EMAIL and E2E_INSTRUCTOR_PASSWORD environment variables."
        )

    return {"email": email, "password": password}


@pytest.fixture
def instructor_page(app_page, instructor_credentials):
    """Log in as instructor and return authenticated page.

    Uses credentials from E2E_INSTRUCTOR_EMAIL and E2E_INSTRUCTOR_PASSWORD
    environment variables.
    """
    page = app_page

    # Fill login form - use textbox role to avoid matching "Show password" button
    page.get_by_role("textbox", name="Email").fill(instructor_credentials["email"])
    page.get_by_role("textbox", name="Password").fill(instructor_credentials["password"])

    # Click Login button
    page.get_by_role("button", name="Login").click()

    # Wait for successful authentication - page should show "Welcome" message
    page.wait_for_selector("text=Welcome", timeout=60000)

    return page


@pytest.fixture(scope="session")
def openai_api_key():
    """Read OpenAI API key from environment.

    Required for simulation tests that make actual LLM API calls.
    Set E2E_OPENAI_API_KEY environment variable to use.
    """
    key = os.environ.get("E2E_OPENAI_API_KEY")
    if not key:
        pytest.skip("E2E_OPENAI_API_KEY not set - skipping simulation test")
    return key


@pytest.fixture(scope="session")
def database_url():
    """Read database URL from environment or secrets.

    Used for direct database operations in test fixtures.
    """
    # Try environment variable first
    url = os.environ.get("E2E_DATABASE_URL")
    if url:
        return url

    # Try to read from Streamlit secrets file
    secrets_path = Path(__file__).parent.parent.parent / "streamlit" / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        # Use tomllib (Python 3.11+) or toml (older versions)
        try:
            import tomllib

            with open(secrets_path, "rb") as f:
                secrets = tomllib.load(f)
        except ImportError:
            import toml

            with open(secrets_path) as f:
                secrets = toml.load(f)

        url = secrets.get("database", {}).get("url")
        if url:
            return url

    pytest.skip("Database URL not available - set E2E_DATABASE_URL or configure secrets.toml")


@pytest.fixture
def simulation_test_game(instructor_page, instructor_credentials, database_url):
    """Create a test game with 2 groups and prompts for simulation testing.

    This fixture creates all necessary test data via direct DB inserts:
    1. Two test students with different groups
    2. A test game
    3. Plays entries linking students to game
    4. Group values for each student group
    5. Prompts for each group

    Returns dict with game_id, game_name, academic_year, class_.
    Cleans up all test data after test completes.
    """
    timestamp = int(time.time())

    # Test data
    game_name = f"E2E_Sim_Test_{timestamp}"
    academic_year = 2099  # Use a far-future year to avoid conflicts with real data
    class_ = "T"  # Single character for class
    test_users = [
        {
            "user_id": f"e2e_sim_user1_{timestamp}",
            "email": f"e2e_sim1_{timestamp}@test.com",
            "group_id": 1,
        },
        {
            "user_id": f"e2e_sim_user2_{timestamp}",
            "email": f"e2e_sim2_{timestamp}@test.com",
            "group_id": 2,
        },
    ]

    game_id = None
    instructor_user_id = None

    # --- Get instructor user_id from email ---
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM user_ WHERE email = %s;",
                (instructor_credentials["email"],),
            )
            result = cur.fetchone()
            if result:
                instructor_user_id = result[0]
    finally:
        conn.close()

    if not instructor_user_id:
        pytest.fail(f"Could not find instructor with email: {instructor_credentials['email']}")

    # --- Setup: Create all test data via database ---
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            # 1. Create test students
            for user in test_users:
                cur.execute(
                    """
                    INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING;
                    """,
                    (
                        user["user_id"],
                        user["email"],
                        "testpass",
                        user["group_id"],
                        academic_year,
                        class_,
                    ),
                )

            # 2. Create game (get next available game_id first to avoid sequence issues)
            cur.execute("SELECT COALESCE(MAX(game_id), 0) + 1 FROM game;")
            next_game_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO game (
                    game_id, available, created_by, game_name, number_of_rounds, name_roles,
                    game_academic_year, game_class, password, timestamp_submission_deadline, explanation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING game_id;
                """,
                (
                    next_game_id,
                    0,  # available
                    instructor_user_id,  # created_by
                    game_name,
                    1,  # number_of_rounds
                    "Buyer#_;:)Seller",  # name_roles
                    academic_year,
                    class_,
                    "1234",  # password
                    "2099-12-31 23:59:59",  # timestamp_submission_deadline (far future)
                    "E2E test game for simulation testing.",
                ),
            )
            game_id = cur.fetchone()[0]

            # 3. Create plays entries (link students to game)
            for user in test_users:
                cur.execute(
                    """
                    INSERT INTO plays (user_id, game_id)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, game_id) DO NOTHING;
                    """,
                    (user["user_id"], game_id),
                )

            # 4. Create group values
            for user in test_users:
                cur.execute(
                    """
                    INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (game_id, class, group_id)
                    DO UPDATE SET minimizer_value = EXCLUDED.minimizer_value,
                                  maximizer_value = EXCLUDED.maximizer_value;
                    """,
                    (game_id, class_, user["group_id"], 20, 10),
                )

            # 5. Create student prompts
            prompt_content = (
                "You are a buyer. Try to negotiate the lowest price possible. "
                "Be cooperative and aim to reach a deal quickly.\n\n#_;:)\n\n"
                "You are a seller. Try to negotiate the highest price possible. "
                "Be cooperative and aim to reach a deal quickly."
            )
            for user in test_users:
                cur.execute(
                    """
                    INSERT INTO student_prompt (game_id, class, group_id, prompt, submitted_by)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (game_id, class, group_id)
                    DO UPDATE SET prompt = EXCLUDED.prompt,
                                  submitted_by = EXCLUDED.submitted_by,
                                  updated_at = CURRENT_TIMESTAMP;
                    """,
                    (game_id, class_, user["group_id"], prompt_content, user["user_id"]),
                )

            conn.commit()
    finally:
        conn.close()

    if not game_id:
        pytest.fail(f"Failed to create game: {game_name}")

    # Return test data
    test_data = {
        "game_id": game_id,
        "game_name": game_name,
        "academic_year": academic_year,
        "class_": class_,
        "test_users": test_users,
    }

    yield test_data

    # --- Cleanup ---
    # Delete from database (order matters due to foreign keys)
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            # Delete student prompts
            cur.execute("DELETE FROM student_prompt WHERE game_id = %s;", (game_id,))
            # Delete negotiation chats
            cur.execute("DELETE FROM negotiation_chat WHERE game_id = %s;", (game_id,))
            # Delete round data
            cur.execute("DELETE FROM round WHERE game_id = %s;", (game_id,))
            # Delete group values
            cur.execute("DELETE FROM group_values WHERE game_id = %s;", (game_id,))
            # Delete plays entries
            cur.execute("DELETE FROM plays WHERE game_id = %s;", (game_id,))
            # Delete game
            cur.execute("DELETE FROM game WHERE game_id = %s;", (game_id,))
            # Delete test users
            for user in test_users:
                cur.execute("DELETE FROM user_ WHERE user_id = %s;", (user["user_id"],))
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
