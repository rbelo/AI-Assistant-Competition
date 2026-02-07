"""
Unit tests for database_handler.py CRUD operations.

Follows the existing mock pattern: mock get_connection to return a mock conn/cursor,
then assert the correct SQL queries and parameters are used.
"""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)


@pytest.fixture
def db(mock_psycopg2):
    """Import real database_handler with mocked psycopg2 connection."""
    conn, cursor = mock_psycopg2
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    if "modules.database_handler" in sys.modules:
        del sys.modules["modules.database_handler"]

    database_handler = importlib.import_module("modules.database_handler")
    return database_handler, conn, cursor


# ---------------------------------------------------------------------------
# get_db_connection_string
# ---------------------------------------------------------------------------
class TestGetDbConnectionString:
    @pytest.mark.unit
    def test_returns_env_var_when_set(self, db):
        dh, _, _ = db
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://env"}):
            assert dh.get_db_connection_string() == "postgresql://env"

    @pytest.mark.unit
    def test_falls_back_to_secrets(self, db):
        dh, _, _ = db
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            mock_secrets = MagicMock()
            mock_secrets.__getitem__ = lambda self, k: {"url": "postgresql://secret"} if k == "database" else {}
            with patch.object(dh, "st") as mock_st:
                mock_st.secrets = mock_secrets
                assert dh.get_db_connection_string() == "postgresql://secret"

    @pytest.mark.unit
    def test_returns_none_when_nothing_set(self, db):
        dh, _, _ = db
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with patch.object(dh, "st") as mock_st:
                mock_st.secrets = {}
                assert dh.get_db_connection_string() is None


# ---------------------------------------------------------------------------
# _get_api_key_cipher
# ---------------------------------------------------------------------------
class TestGetApiKeyCipher:
    @pytest.mark.unit
    def test_returns_fernet_from_env(self, db):
        dh, _, _ = db
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"API_KEY_ENCRYPTION_KEY": key}):
            cipher = dh._get_api_key_cipher()
            assert cipher is not None

    @pytest.mark.unit
    def test_returns_none_when_no_key(self, db):
        dh, _, _ = db
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("API_KEY_ENCRYPTION_KEY", None)
            with patch.object(dh, "st") as mock_st:
                mock_st.secrets = MagicMock()
                mock_st.secrets.get.return_value = {}
                assert dh._get_api_key_cipher() is None

    @pytest.mark.unit
    def test_returns_none_for_invalid_key(self, db):
        dh, _, _ = db
        with patch.dict(os.environ, {"API_KEY_ENCRYPTION_KEY": "not-valid-base64"}):
            assert dh._get_api_key_cipher() is None


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------
class TestAuthenticateUser:
    @pytest.mark.unit
    def test_returns_truthy_on_match(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (1,)
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.authenticate_user("test@example.com", "hash123")
        assert result
        query = cursor.execute.call_args[0][0]
        assert "SELECT 1 FROM user_" in query
        params = cursor.execute.call_args[0][1]
        assert params["param1"] == "test@example.com"
        assert params["param2"] == "hash123"

    @pytest.mark.unit
    def test_returns_false_on_no_match(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = None
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.authenticate_user("no@match.com", "wrong") is False

    @pytest.mark.unit
    def test_returns_false_on_no_connection(self, db):
        dh, _, _ = db
        with patch.object(dh, "get_connection", return_value=None):
            assert dh.authenticate_user("x@x.com", "h") is False


# ---------------------------------------------------------------------------
# exists_user
# ---------------------------------------------------------------------------
class TestExistsUser:
    @pytest.mark.unit
    def test_returns_true_when_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (True,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.exists_user("test@example.com") is True

    @pytest.mark.unit
    def test_returns_false_when_not_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (False,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.exists_user("nobody@example.com") is False


# ---------------------------------------------------------------------------
# is_instructor
# ---------------------------------------------------------------------------
class TestIsInstructor:
    @pytest.mark.unit
    def test_returns_true_for_instructor(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (True,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.is_instructor("prof@school.edu") is True

    @pytest.mark.unit
    def test_returns_false_for_student(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (False,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.is_instructor("student@school.edu") is False


# ---------------------------------------------------------------------------
# update_password
# ---------------------------------------------------------------------------
class TestUpdatePassword:
    @pytest.mark.unit
    def test_updates_and_commits(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.update_password("test@example.com", "newhash")
        assert result is True
        conn.commit.assert_called_once()
        query = cursor.execute.call_args[0][0]
        assert "UPDATE user_" in query
        assert "SET password" in query

    @pytest.mark.unit
    def test_returns_false_on_no_connection(self, db):
        dh, _, _ = db
        with patch.object(dh, "get_connection", return_value=None):
            assert dh.update_password("x@x.com", "h") is False


# ---------------------------------------------------------------------------
# get_user_id_by_email
# ---------------------------------------------------------------------------
class TestGetUserIdByEmail:
    @pytest.mark.unit
    def test_returns_user_id(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = ("user123",)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_user_id_by_email("test@example.com") == "user123"

    @pytest.mark.unit
    def test_returns_false_on_exception(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = None  # will cause TypeError on [0] access
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_user_id_by_email("none@example.com") is False


# ---------------------------------------------------------------------------
# get_group_id_from_user_id / get_class_from_user_id / get_academic_year_from_user_id
# ---------------------------------------------------------------------------
class TestUserLookups:
    @pytest.mark.unit
    def test_get_group_id(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (5,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_group_id_from_user_id("user1") == 5

    @pytest.mark.unit
    def test_get_class(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = ("ClassA",)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_class_from_user_id("user1") == "ClassA"

    @pytest.mark.unit
    def test_get_academic_year(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = ("2024-2025",)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_academic_year_from_user_id("user1") == "2024-2025"

    @pytest.mark.unit
    def test_returns_false_on_no_connection(self, db):
        dh, _, _ = db
        with patch.object(dh, "get_connection", return_value=None):
            assert dh.get_group_id_from_user_id("x") is False
            assert dh.get_class_from_user_id("x") is False
            assert dh.get_academic_year_from_user_id("x") is False


# ---------------------------------------------------------------------------
# insert_student_data
# ---------------------------------------------------------------------------
class TestInsertStudentData:
    @pytest.mark.unit
    def test_inserts_new_student(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (False,)  # user does not exist
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.insert_student_data("s1", "s1@test.com", "pass", 1, "2024", "A")
        assert result is True
        conn.commit.assert_called_once()
        # Two execute calls: EXISTS check + INSERT
        assert cursor.execute.call_count == 2
        insert_query = cursor.execute.call_args_list[1][0][0]
        assert "INSERT INTO user_" in insert_query

    @pytest.mark.unit
    def test_skips_existing_student(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (True,)  # user already exists
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.insert_student_data("s1", "s1@test.com", "pass", 1, "2024", "A")
        assert result is True
        # Only the EXISTS check should have run
        assert cursor.execute.call_count == 1


# ---------------------------------------------------------------------------
# remove_student
# ---------------------------------------------------------------------------
class TestRemoveStudent:
    @pytest.mark.unit
    def test_deletes_plays_and_user(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.remove_student("user1")
        assert result is True
        conn.commit.assert_called_once()
        # Two deletes: plays then user_
        assert cursor.execute.call_count == 2
        q1 = cursor.execute.call_args_list[0][0][0]
        q2 = cursor.execute.call_args_list[1][0][0]
        assert "DELETE FROM plays" in q1
        assert "DELETE FROM user_" in q2


# ---------------------------------------------------------------------------
# get_game_by_id
# ---------------------------------------------------------------------------
class TestGetGameById:
    @pytest.mark.unit
    def test_returns_game_dict(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (
            True,
            "admin",
            "TestGame",
            3,
            ["Buyer", "Seller"],
            "2024",
            "A",
            "pass",
            "2024-01-01",
            "2024-06-01",
            "Explanation",
        )
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_game_by_id(1)
        assert result["game_name"] == "TestGame"
        assert result["name_roles"] == ["Buyer", "Seller"]
        assert result["explanation"] == "Explanation"

    @pytest.mark.unit
    def test_returns_false_when_not_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = None
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_game_by_id(999) is False


# ---------------------------------------------------------------------------
# get_next_game_id
# ---------------------------------------------------------------------------
class TestGetNextGameId:
    @pytest.mark.unit
    def test_increments_last_id(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (5,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_next_game_id() == 6

    @pytest.mark.unit
    def test_starts_at_1_when_empty(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (None,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_next_game_id() == 1


# ---------------------------------------------------------------------------
# fetch_games_data
# ---------------------------------------------------------------------------
class TestFetchGamesData:
    @pytest.mark.unit
    def test_get_academic_years(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("2024",), ("2023",)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.fetch_games_data(get_academic_years=True)
        assert result == ["2024", "2023"]

    @pytest.mark.unit
    def test_get_games_for_year(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [
            (1, "Game1", "A", True, "admin", 3, ["B", "S"], "2024", "pw", "ts1", "ts2", "exp"),
        ]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.fetch_games_data(academic_year="2024")
        assert len(result) == 1
        assert result[0]["game_id"] == 1
        assert result[0]["game_name"] == "Game1"

    @pytest.mark.unit
    def test_returns_empty_on_no_connection(self, db):
        dh, _, _ = db
        with patch.object(dh, "get_connection", return_value=None):
            assert dh.fetch_games_data(academic_year="2024") == []


# ---------------------------------------------------------------------------
# store_game_in_db
# ---------------------------------------------------------------------------
class TestStoreGameInDb:
    @pytest.mark.unit
    def test_stores_with_existing_mode(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (1,)  # mode_id exists
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.store_game_in_db(
                1, True, "admin", "Game", 3, ["B", "S"], "2024", "A", "pw", "ts", "dl", "exp", "zero_sum"
            )
        assert result is True
        conn.commit.assert_called_once()
        # Two executes: mode lookup + game insert
        assert cursor.execute.call_count == 2

    @pytest.mark.unit
    def test_creates_new_mode_if_missing(self, db):
        dh, conn, cursor = db
        # First fetchone returns None (no mode), second returns new mode_id
        cursor.fetchone.side_effect = [None, (42,)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.store_game_in_db(
                1, True, "admin", "Game", 3, ["B", "S"], "2024", "A", "pw", "ts", "dl", "exp", "new_mode"
            )
        assert result is True
        # Three executes: mode lookup + mode insert + game insert
        assert cursor.execute.call_count == 3


# ---------------------------------------------------------------------------
# update_game_in_db
# ---------------------------------------------------------------------------
class TestUpdateGameInDb:
    @pytest.mark.unit
    def test_updates_and_commits(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.update_game_in_db(1, "admin", "Game", 3, ["B", "S"], "2024", "A", "pw", "ts", "dl", "exp")
        assert result is True
        conn.commit.assert_called_once()
        q = cursor.execute.call_args_list[0][0][0]
        assert "UPDATE game" in q


# ---------------------------------------------------------------------------
# update_access_to_chats
# ---------------------------------------------------------------------------
class TestUpdateAccessToChats:
    @pytest.mark.unit
    def test_updates_available_flag(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.update_access_to_chats(True, 1)
        assert result is True
        conn.commit.assert_called_once()
        q = cursor.execute.call_args_list[0][0][0]
        assert "UPDATE game" in q
        assert "available" in q


# ---------------------------------------------------------------------------
# populate_plays_table
# ---------------------------------------------------------------------------
class TestPopulatePlaysTable:
    @pytest.mark.unit
    def test_all_classes(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("s1",), ("s2",)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.populate_plays_table(1, "2024", "_")
        assert result is True
        conn.commit.assert_called_once()
        # First query uses only param1 (no class filter)
        first_query = cursor.execute.call_args_list[0][0][0]
        assert "academic_year" in first_query

    @pytest.mark.unit
    def test_specific_class(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("s1",)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.populate_plays_table(1, "2024", "A")
        assert result is True
        first_params = cursor.execute.call_args_list[0][0][1]
        assert first_params["param2"] == "A"

    @pytest.mark.unit
    def test_returns_false_when_no_students(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = []
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.populate_plays_table(1, "2024", "A") is False
        conn.commit.assert_called_once()
        delete_query = cursor.execute.call_args_list[1][0][0]
        assert "DELETE FROM plays" in delete_query


# ---------------------------------------------------------------------------
# insert_round_data / get_round_data
# ---------------------------------------------------------------------------
class TestRoundData:
    @pytest.mark.unit
    def test_insert_round(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.insert_round_data(1, 1, "A", 1, "B", 2, 0.5, 0.5, None, None)
        assert result is True
        conn.commit.assert_called_once()
        q = cursor.execute.call_args[0][0]
        assert "INSERT INTO round" in q

    @pytest.mark.unit
    def test_get_round(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [(1, "A", 1, "B", 2, 0.5, 0.5, None, None)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_round_data(1)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# update_round_data
# ---------------------------------------------------------------------------
class TestUpdateRoundData:
    @pytest.mark.unit
    def test_role_1_2(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.update_round_data(1, 1, "A", 1, "B", 2, 0.6, 0.4, 1, 2)
        assert result is True
        q = cursor.execute.call_args[0][0]
        assert "score_team1_role1" in q
        assert "score_team2_role2" in q

    @pytest.mark.unit
    def test_role_2_1(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.update_round_data(1, 1, "A", 1, "B", 2, 0.6, 0.4, 2, 1)
        assert result is True
        q = cursor.execute.call_args[0][0]
        assert "score_team1_role2" in q
        assert "score_team2_role1" in q

    @pytest.mark.unit
    def test_invalid_role_index(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.update_round_data(1, 1, "A", 1, "B", 2, 0.6, 0.4, 3, 4)
        assert result is False


# ---------------------------------------------------------------------------
# delete_from_round / delete_negotiation_chats
# ---------------------------------------------------------------------------
class TestDeleteOperations:
    @pytest.mark.unit
    def test_delete_from_round(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.delete_from_round(1) is True
        q = cursor.execute.call_args[0][0]
        assert "DELETE FROM round" in q

    @pytest.mark.unit
    def test_delete_negotiation_chats(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.delete_negotiation_chats(1) is True
        q = cursor.execute.call_args[0][0]
        assert "DELETE FROM negotiation_chat" in q


# ---------------------------------------------------------------------------
# upsert_game_simulation_params / get_game_simulation_params
# ---------------------------------------------------------------------------
class TestGameSimulationParams:
    @pytest.mark.unit
    def test_upsert(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.upsert_game_simulation_params(1, "gpt-4o", "same", "Hello", 10, "Deal!", "Summarize", "DEAL:")
        assert result is True
        conn.commit.assert_called()
        # CREATE TABLE IF NOT EXISTS + INSERT/UPSERT
        queries = [call[0][0] for call in cursor.execute.call_args_list]
        assert any("INSERT INTO game_simulation_params" in q for q in queries)

    @pytest.mark.unit
    def test_get_params_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = ("gpt-4o", "same", "Hello", 10, "Deal!", "Sum", "DEAL:")
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_game_simulation_params(1)
        assert result["model"] == "gpt-4o"
        assert result["num_turns"] == 10

    @pytest.mark.unit
    def test_get_params_not_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = None
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_game_simulation_params(999) is None


# ---------------------------------------------------------------------------
# get_negotiation_chat_details
# ---------------------------------------------------------------------------
class TestGetNegotiationChatDetails:
    @pytest.mark.unit
    def test_returns_details_dict(self, db):
        dh, conn, cursor = db
        # First fetchall: column introspection
        cursor.fetchall.return_value = [("transcript",), ("summary",), ("deal_value",)]
        cursor.fetchone.return_value = ("text", "summary", 15.0)
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_negotiation_chat_details(1, 1, "A", 1, "B", 2)
        assert result["transcript"] == "text"
        assert result["summary"] == "summary"
        assert result["deal_value"] == 15.0

    @pytest.mark.unit
    def test_returns_none_when_not_found(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("transcript",)]
        cursor.fetchone.return_value = None
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_negotiation_chat_details(1, 1, "A", 1, "B", 2) is None


# ---------------------------------------------------------------------------
# get_students_from_db
# ---------------------------------------------------------------------------
class TestGetStudentsFromDb:
    @pytest.mark.unit
    def test_returns_dataframe_with_data(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [
            ("s1", "s1@test.com", 1, "2024", "A", "2024-01-01"),
        ]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_students_from_db()
        assert len(result) == 1
        assert result.iloc[0]["user_id"] == "s1"

    @pytest.mark.unit
    def test_returns_empty_dataframe_when_no_data(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = []
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_students_from_db()
        assert len(result) == 0
        assert "user_id" in result.columns


# ---------------------------------------------------------------------------
# is_valid_instructor_email
# ---------------------------------------------------------------------------
class TestIsValidInstructorEmail:
    @pytest.mark.unit
    def test_returns_true_when_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (True,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.is_valid_instructor_email("prof@school.edu") is True

    @pytest.mark.unit
    def test_returns_false_when_not_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (False,)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.is_valid_instructor_email("nobody@school.edu") is False


# ---------------------------------------------------------------------------
# update_num_rounds_game
# ---------------------------------------------------------------------------
class TestUpdateNumRoundsGame:
    @pytest.mark.unit
    def test_updates_rounds(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.update_num_rounds_game(5, 1) is True
        conn.commit.assert_called_once()
        q = cursor.execute.call_args_list[0][0][0]
        assert "UPDATE game" in q
        assert "number_of_rounds" in q


# ---------------------------------------------------------------------------
# get_academic_year_class_combinations
# ---------------------------------------------------------------------------
class TestGetAcademicYearClassCombinations:
    @pytest.mark.unit
    def test_returns_dict(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("2024", "A"), ("2024", "B"), ("2023", "A")]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_academic_year_class_combinations()
        assert result == {"2024": ["A", "B"], "2023": ["A"]}

    @pytest.mark.unit
    def test_returns_false_when_empty(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = []
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_academic_year_class_combinations() is False


# ---------------------------------------------------------------------------
# Student grouping lookups
# ---------------------------------------------------------------------------
class TestStudentGroupingLookups:
    @pytest.mark.unit
    def test_get_academic_years_of_students(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("2024",), ("2023",)]
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_academic_years_of_students() == ["2024", "2023"]

    @pytest.mark.unit
    def test_get_classes_of_students(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("A",), ("B",)]
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_classes_of_students("2024") == ["A", "B"]

    @pytest.mark.unit
    def test_get_groups_of_students(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [(1,), (2,), (3,)]
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_groups_of_students("2024", "A") == [1, 2, 3]

    @pytest.mark.unit
    def test_get_user_id_of_student(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = ("student1",)
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_user_id_of_student("2024", "A", 1) == "student1"


# ---------------------------------------------------------------------------
# get_round_data_by_class_group_id / get_group_ids_from_game_id
# ---------------------------------------------------------------------------
class TestRoundAndGroupLookups:
    @pytest.mark.unit
    def test_get_round_data_by_class_group(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [(1, "A", 1, "B", 2)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_round_data_by_class_group_id(1, "A", 1)
        assert len(result) == 1

    @pytest.mark.unit
    def test_get_group_ids_from_game_id(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("A", 1), ("A", 2), ("B", 1)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_group_ids_from_game_id(1)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Playground CRUD
# ---------------------------------------------------------------------------
class TestPlaygroundCrud:
    @pytest.mark.unit
    def test_delete_playground_result(self, db):
        dh, conn, cursor = db
        cursor.rowcount = 1
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.delete_playground_result(1, "user1", "A", 1) is True
        q = cursor.execute.call_args[0][0]
        assert "DELETE FROM playground_result" in q

    @pytest.mark.unit
    def test_delete_playground_result_not_found(self, db):
        dh, conn, cursor = db
        cursor.rowcount = 0
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.delete_playground_result(999, "user1", "A", 1) is False

    @pytest.mark.unit
    def test_delete_all_playground_results(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.delete_all_playground_results("user1", "A", 1) is True
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# fetch_current_games_data_by_user_id
# ---------------------------------------------------------------------------
class TestFetchCurrentGamesDataByUserId:
    @pytest.mark.unit
    def test_returns_games(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [
            (1, True, "admin", "Game1", 3, ["B", "S"], "2024", "A", "pw", "ts1", "ts2", "exp"),
        ]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.fetch_current_games_data_by_user_id("<", "user1")
        assert len(result) == 1
        assert result[0]["game_name"] == "Game1"

    @pytest.mark.unit
    def test_returns_empty_when_no_games(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = []
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.fetch_current_games_data_by_user_id("<", "user1") == []


# ---------------------------------------------------------------------------
# store_group_values / get_group_values / get_all_group_values / get_game_parameters / store_game_parameters
# ---------------------------------------------------------------------------
class TestGroupValuesAndGameParams:
    @pytest.mark.unit
    def test_store_group_values(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.store_group_values(1, "A", 1, 10, 20)
        assert result is True
        conn.commit.assert_called_once()

    @pytest.mark.unit
    def test_get_group_values_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = (10, 20)
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_group_values(1, "A", 1)
        assert result == {"minimizer_value": 10, "maximizer_value": 20}

    @pytest.mark.unit
    def test_get_group_values_not_found(self, db):
        dh, conn, cursor = db
        cursor.fetchone.return_value = None
        with patch.object(dh, "get_connection", return_value=conn):
            assert dh.get_group_values(1, "A", 1) is None

    @pytest.mark.unit
    def test_get_all_group_values(self, db):
        dh, conn, cursor = db
        cursor.fetchall.return_value = [("A", 1, 10, 20), ("B", 2, 15, 25)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_all_group_values(1)
        assert len(result) == 2
        assert result[0]["class"] == "A"

    @pytest.mark.unit
    def test_get_game_parameters_found(self, db):
        dh, conn, cursor = db
        # get_game_parameters uses fetchall and expects exactly 2 rows
        cursor.fetchall.return_value = [(5, 10), (50, 100)]
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.get_game_parameters(1)
        assert result == {
            "min_minimizer": 5,
            "max_minimizer": 50,
            "min_maximizer": 10,
            "max_maximizer": 100,
        }

    @pytest.mark.unit
    def test_store_game_parameters(self, db):
        dh, conn, cursor = db
        with patch.object(dh, "get_connection", return_value=conn):
            result = dh.store_game_parameters(1, 5, 50, 10, 100)
        assert result is True
        conn.commit.assert_called_once()
