"""
Unit tests for negotiation chat storage in the database handler.
"""

import importlib
import os
import sys

import pytest
from unittest.mock import MagicMock, patch

# Add streamlit directory to path for imports
STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)


@pytest.fixture
def real_database_handler(mock_psycopg2):
    """Import the real database_handler module, ensuring any mocks are cleared."""
    conn, cursor = mock_psycopg2
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    # Remove any mocked version of the module to ensure a clean import
    if "modules.database_handler" in sys.modules:
        if isinstance(sys.modules["modules.database_handler"], MagicMock):
            del sys.modules["modules.database_handler"]
        else:
            del sys.modules["modules.database_handler"]

    database_handler = importlib.import_module("modules.database_handler")

    return database_handler, cursor


class TestNegotiationChatStorage:
    @pytest.mark.unit
    def test_insert_negotiation_chat_executes_upsert(self, real_database_handler):
        """Test that insert_negotiation_chat executes an upsert query."""
        database_handler, cursor = real_database_handler

        with patch.object(database_handler, "get_db_connection_string", return_value="db"):
            result = database_handler.insert_negotiation_chat(
                game_id=1,
                round_number=2,
                group1_class="A",
                group1_id=3,
                group2_class="B",
                group2_id=4,
                transcript="chat transcript"
            )

        assert result is True
        assert cursor.execute.called
        query, params = cursor.execute.call_args[0]
        assert "INSERT INTO negotiation_chat" in query
        assert "ON CONFLICT" in query
        assert params["param1"] == 1
        assert params["param2"] == 2
        assert params["param3"] == "A"
        assert params["param4"] == 3
        assert params["param5"] == "B"
        assert params["param6"] == 4
        assert params["param7"] == "chat transcript"

    @pytest.mark.unit
    def test_get_negotiation_chat_returns_transcript(self, real_database_handler):
        """Test that get_negotiation_chat returns the transcript when found."""
        database_handler, cursor = real_database_handler
        cursor.fetchone.return_value = ("stored transcript",)

        with patch.object(database_handler, "get_db_connection_string", return_value="db"):
            result = database_handler.get_negotiation_chat(
                game_id=1,
                round_number=2,
                group1_class="A",
                group1_id=3,
                group2_class="B",
                group2_id=4
            )

        assert result == "stored transcript"
        assert cursor.execute.called
        query, params = cursor.execute.call_args[0]
        assert "SELECT transcript" in query
        assert params["param1"] == 1
        assert params["param2"] == 2

    @pytest.mark.unit
    def test_get_negotiation_chat_returns_none_when_not_found(self, real_database_handler):
        """Test that get_negotiation_chat returns None when no transcript exists."""
        database_handler, cursor = real_database_handler
        cursor.fetchone.return_value = None

        with patch.object(database_handler, "get_db_connection_string", return_value="db"):
            result = database_handler.get_negotiation_chat(
                game_id=999,
                round_number=1,
                group1_class="X",
                group1_id=1,
                group2_class="Y",
                group2_id=2
            )

        assert result is None


class TestParseTeamName:
    @pytest.mark.unit
    def test_parse_valid_team_name(self):
        from modules.negotiations import parse_team_name

        class_, group = parse_team_name("ClassA_Group1")
        assert class_ == "A"
        assert group == 1

    @pytest.mark.unit
    def test_parse_team_name_with_multi_digit_group(self):
        from modules.negotiations import parse_team_name

        class_, group = parse_team_name("ClassB_Group12")
        assert class_ == "B"
        assert group == 12

    @pytest.mark.unit
    def test_parse_team_name_returns_none_for_none_input(self):
        from modules.negotiations import parse_team_name

        class_, group = parse_team_name(None)
        assert class_ is None
        assert group is None

    @pytest.mark.unit
    def test_parse_team_name_returns_none_for_invalid_format(self):
        from modules.negotiations import parse_team_name

        class_, group = parse_team_name("InvalidName")
        assert class_ is None
        assert group is None

    @pytest.mark.unit
    def test_parse_team_name_handles_non_numeric_group(self):
        from modules.negotiations import parse_team_name

        class_, group = parse_team_name("ClassC_GroupABC")
        assert class_ == "C"
        assert group == "ABC"  # Stays as string when not numeric


class TestStudentPromptStorage:
    @pytest.mark.unit
    def test_insert_student_prompt_executes_upsert(self, real_database_handler):
        """Test that insert_student_prompt executes an upsert query."""
        database_handler, cursor = real_database_handler

        with patch.object(database_handler, "get_db_connection_string", return_value="db"):
            result = database_handler.insert_student_prompt(
                game_id=1,
                class_="A",
                group_id=3,
                prompt="prompt1#_;:)prompt2",
                submitted_by="user123"
            )

        assert result is True
        assert cursor.execute.called
        query, params = cursor.execute.call_args[0]
        assert "INSERT INTO student_prompt" in query
        assert "ON CONFLICT" in query
        assert params["game_id"] == 1
        assert params["class"] == "A"
        assert params["group_id"] == 3
        assert params["prompt"] == "prompt1#_;:)prompt2"
        assert params["submitted_by"] == "user123"

    @pytest.mark.unit
    def test_insert_student_prompt_without_submitted_by(self, real_database_handler):
        """Test that insert_student_prompt works without submitted_by."""
        database_handler, cursor = real_database_handler

        with patch.object(database_handler, "get_db_connection_string", return_value="db"):
            result = database_handler.insert_student_prompt(
                game_id=1,
                class_="A",
                group_id=3,
                prompt="prompt1#_;:)prompt2"
            )

        assert result is True
        assert cursor.execute.called
        query, params = cursor.execute.call_args[0]
        assert params["submitted_by"] is None

    @pytest.mark.unit
    def test_get_student_prompt_returns_prompt(self, real_database_handler):
        """Test that get_student_prompt returns the prompt when found."""
        database_handler, cursor = real_database_handler
        cursor.fetchone.return_value = ("stored prompt",)

        with patch.object(database_handler, "get_db_connection_string", return_value="db"):
            result = database_handler.get_student_prompt(
                game_id=1,
                class_="A",
                group_id=3
            )

        assert result == "stored prompt"
        assert cursor.execute.called
        query, params = cursor.execute.call_args[0]
        assert "SELECT prompt" in query
        assert params["game_id"] == 1
        assert params["class"] == "A"
        assert params["group_id"] == 3

    @pytest.mark.unit
    def test_get_student_prompt_returns_none_when_not_found(self, real_database_handler):
        """Test that get_student_prompt returns None when no prompt exists."""
        database_handler, cursor = real_database_handler
        cursor.fetchone.return_value = None

        with patch.object(database_handler, "get_db_connection_string", return_value="db"):
            result = database_handler.get_student_prompt(
                game_id=999,
                class_="X",
                group_id=1
            )

        assert result is None
