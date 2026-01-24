"""
Pytest fixtures for AI Assistant Competition tests.

These fixtures provide mocking for external dependencies (Streamlit, database, Google Drive)
so that unit tests can run without requiring secrets.toml or external services.
"""

import pytest
import sys
import types
from unittest.mock import MagicMock, patch
from io import StringIO


# =============================================================================
# Streamlit Mocking
# =============================================================================


class MockSecrets(dict):
    """Mock for st.secrets that behaves like a dict but also supports attribute access."""

    def __getattr__(self, key):
        try:
            value = self[key]
            if isinstance(value, dict):
                return MockSecrets(value)
            return value
        except KeyError:
            raise AttributeError(f"Secrets has no key '{key}'")


class MockSessionState(dict):
    """Mock for st.session_state that behaves like a dict with attribute access."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"Session state has no key '{key}'")

    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def mock_secrets():
    """
    Provides a mock st.secrets with test data.

    Usage:
        def test_something(mock_secrets):
            # st.secrets is now mocked with test data
            assert st.secrets["database"]["url"] == "postgresql://test:test@localhost/test"
    """
    secrets = MockSecrets({
        "database": {
            "url": "postgresql://test:test@localhost:5432/test_db",
        },
        "drive": {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "folder_id": "test_folder_id",
        },
        "mail": {
            "email": "test@example.com",
            "api_key": "test_api_key",
        },
        "app": {
            "link": "https://test-app.streamlit.app",
        },
    })

    with patch("streamlit.secrets", secrets):
        yield secrets


@pytest.fixture
def mock_session_state():
    """
    Provides a mock st.session_state with default authenticated user.

    Usage:
        def test_something(mock_session_state):
            assert st.session_state["authenticated"] == True
    """
    session_state = MockSessionState({
        "authenticated": True,
        "instructor": False,
        "user_id": "test_user",
        "email": "test@example.com",
        "current_visit_id": {},
        "academic_year": "2024-2025",
        "class": "TestClass",
        "group_id": 1,
    })

    with patch("streamlit.session_state", session_state):
        yield session_state


@pytest.fixture
def mock_streamlit(mock_secrets, mock_session_state):
    """
    Provides a complete mock Streamlit environment.

    Combines mock_secrets and mock_session_state, plus mocks common st functions.

    Usage:
        def test_something(mock_streamlit):
            # Full Streamlit mocking available
            pass
    """
    mock_st = MagicMock()
    mock_st.secrets = mock_secrets
    mock_st.session_state = mock_session_state
    mock_st.error = MagicMock()
    mock_st.success = MagicMock()
    mock_st.warning = MagicMock()
    mock_st.info = MagicMock()
    mock_st.write = MagicMock()
    mock_st.markdown = MagicMock()
    mock_st.button = MagicMock(return_value=False)
    mock_st.text_input = MagicMock(return_value="")
    mock_st.selectbox = MagicMock(return_value=None)
    mock_st.multiselect = MagicMock(return_value=[])
    mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
    mock_st.expander = MagicMock()
    mock_st.spinner = MagicMock()

    with patch.dict(sys.modules, {"streamlit": mock_st}):
        yield mock_st


# =============================================================================
# Database Mocking
# =============================================================================


@pytest.fixture
def mock_db_connection():
    """
    Provides a mock psycopg2 database connection.

    Usage:
        def test_db_operation(mock_db_connection):
            conn, cursor = mock_db_connection
            cursor.fetchall.return_value = [("row1",), ("row2",)]
            # Test your database operation
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchmany.return_value = []
    mock_cursor.description = []
    mock_cursor.rowcount = 0

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    return mock_conn, mock_cursor


@pytest.fixture
def mock_psycopg2(mock_db_connection):
    """
    Patches psycopg2.connect to return a mock connection.

    The get_connection() function in database_handler has a fallback path
    that calls psycopg2.connect() directly when Streamlit caching fails,
    so mocking psycopg2.connect is sufficient for tests.

    Usage:
        def test_something(mock_psycopg2):
            conn, cursor = mock_psycopg2
            # psycopg2.connect() and get_connection() fallback return mock_conn
    """
    mock_conn, mock_cursor = mock_db_connection

    with patch("psycopg2.connect", return_value=mock_conn):
        yield mock_conn, mock_cursor


# =============================================================================
# Google Drive Mocking
# =============================================================================


@pytest.fixture
def mock_drive_service():
    """
    Provides mock Google Drive service and file operations.

    Usage:
        def test_drive_operation(mock_drive_service):
            get_text, write_text, delete_file, service = mock_drive_service
            get_text.return_value = "file content"
            # Test your drive operation
    """
    mock_service = MagicMock()
    mock_files = MagicMock()
    mock_service.files.return_value = mock_files

    mock_get_text = MagicMock(return_value="Mock file content")
    mock_write_text = MagicMock(return_value=True)
    mock_delete_file = MagicMock(return_value=True)

    return mock_get_text, mock_write_text, mock_delete_file, mock_service


@pytest.fixture
def mock_google_auth():
    """
    Patches Google authentication modules.

    Usage:
        def test_something(mock_google_auth):
            # Google auth is now mocked
    """
    # Create mock credentials
    mock_creds = MagicMock()
    mock_creds.valid = True

    mock_service_account = MagicMock()
    mock_service_account.Credentials.from_service_account_info.return_value = mock_creds

    with patch.dict(sys.modules, {
        "google": MagicMock(),
        "google.oauth2": MagicMock(),
        "google.oauth2.service_account": mock_service_account,
        "googleapiclient": MagicMock(),
        "googleapiclient.discovery": MagicMock(),
        "googleapiclient.http": MagicMock(),
    }):
        yield mock_creds


# =============================================================================
# Test Data Factories
# =============================================================================


@pytest.fixture
def sample_student_data():
    """
    Provides sample student data for testing.

    Usage:
        def test_student_import(sample_student_data):
            df, csv_content = sample_student_data
            # Use df as a DataFrame or csv_content as raw CSV
    """
    import pandas as pd

    data = {
        "user_id": ["student1", "student2", "student3"],
        "email": ["student1@test.com", "student2@test.com", "student3@test.com"],
        "group_id": [1, 1, 2],
        "academic_year": ["2024-2025", "2024-2025", "2024-2025"],
        "class": ["ClassA", "ClassA", "ClassA"],
    }
    df = pd.DataFrame(data)

    # Also provide CSV format
    csv_content = "user_id;email;group_id;academic_year;class\n"
    csv_content += "student1;student1@test.com;1;2024-2025;ClassA\n"
    csv_content += "student2;student2@test.com;1;2024-2025;ClassA\n"
    csv_content += "student3;student3@test.com;2;2024-2025;ClassA\n"

    return df, csv_content


@pytest.fixture
def sample_game_data():
    """
    Provides sample game configuration data for testing.

    Usage:
        def test_game_creation(sample_game_data):
            game_config = sample_game_data
    """
    return {
        "game_id": 1,
        "game_name": "Test Negotiation",
        "game_type": "zero_sum",
        "role_1": "Buyer",
        "role_2": "Seller",
        "min_value": 0,
        "max_value": 100,
        "academic_year": "2024-2025",
        "class": "ClassA",
        "status": "active",
    }


@pytest.fixture
def sample_negotiation_data():
    """
    Provides sample negotiation/match data for testing.
    """
    return {
        "round_id": 1,
        "game_id": 1,
        "group_1": 1,
        "group_2": 2,
        "score_1": 50,
        "score_2": 50,
        "deal_value": 50,
        "transcript": "Agent 1: I offer 40.\nAgent 2: I counter with 60.\nAgent 1: Deal at 50.",
    }


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def csv_file():
    """
    Factory fixture to create mock CSV file objects.

    Usage:
        def test_csv_import(csv_file):
            file = csv_file("user_id;email\ntest;test@test.com")
            # file is a file-like object
    """
    def _create_csv(content):
        file = StringIO(content)
        file.name = "test.csv"
        return file

    return _create_csv


@pytest.fixture
def stub_google_modules():
    """
    Stubs Google API modules to allow importing drive_file_manager without dependencies.

    This is useful when you need to test modules that import drive_file_manager
    but don't want to require the actual Google libraries.
    """
    # Stub Google API modules
    sys.modules.setdefault("googleapiclient", types.ModuleType("googleapiclient"))

    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = lambda *args, **kwargs: MagicMock()
    sys.modules["googleapiclient.discovery"] = discovery

    http = types.ModuleType("googleapiclient.http")
    http.MediaIoBaseUpload = MagicMock
    http.MediaIoBaseDownload = MagicMock
    sys.modules["googleapiclient.http"] = http

    sys.modules.setdefault("google", types.ModuleType("google"))
    sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")

    service_account = types.ModuleType("google.oauth2.service_account")
    service_account.Credentials = MagicMock()
    service_account.Credentials.from_service_account_info = MagicMock(return_value=MagicMock())
    sys.modules["google.oauth2.service_account"] = service_account

    yield

    # Note: We don't clean up sys.modules as other tests may need these stubs


# =============================================================================
# Markers Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Fast tests with no external dependencies")
    config.addinivalue_line("markers", "integration: Tests that may need mocked external services")
    config.addinivalue_line("markers", "slow: Long-running tests")
    config.addinivalue_line("markers", "requires_db: Tests that need a database connection")
    config.addinivalue_line("markers", "requires_secrets: Tests that need secrets.toml")
