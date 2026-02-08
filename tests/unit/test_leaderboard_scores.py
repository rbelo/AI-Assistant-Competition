import os
import sys
from unittest.mock import MagicMock

import pytest

# Add streamlit directory to path for imports
STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules import database_handler  # noqa: E402


def _mock_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.mark.unit
def test_fetch_and_compute_scores_for_year_formats_results():
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = [
        ("A", 1, 75.0, 3, 2.0, 1, 80.0, 2, 70.0),
    ]
    conn = _mock_connection(cursor)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(database_handler, "get_connection", lambda: conn)
        results = database_handler.fetch_and_compute_scores_for_year(2024)

    assert results == [
        {
            "team_class": "A",
            "team_id": 1,
            "average_score": 75.0,
            "total_games": 3,
            "avg_rounds_per_game": 2.0,
            "position_name_roles_1": 1,
            "score_name_roles_1": 80.0,
            "position_name_roles_2": 2,
            "score_name_roles_2": 70.0,
        }
    ]

    query = cursor.execute.call_args[0][0]
    assert "r.score_team1_role1 AS score_role1" in query
    assert "r.score_team1_role2 AS score_role2" in query
    assert "r.score_team2_role1 AS score_role1" in query
    assert "r.score_team2_role2 AS score_role2" in query
    assert "CASE WHEN r.score_team1_role1 = -1" not in query


@pytest.mark.unit
def test_fetch_and_compute_scores_for_year_game_formats_results():
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = [
        ("B", 2, 60.0, 1, 4.0, 2, 55.0, 1, 65.0),
    ]
    conn = _mock_connection(cursor)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(database_handler, "get_connection", lambda: conn)
        results = database_handler.fetch_and_compute_scores_for_year_game(7)

    assert results == [
        {
            "team_class": "B",
            "team_id": 2,
            "average_score": 60.0,
            "total_games": 1,
            "avg_rounds_per_game": 4.0,
            "position_name_roles_1": 2,
            "score_name_roles_1": 55.0,
            "position_name_roles_2": 1,
            "score_name_roles_2": 65.0,
        }
    ]

    query = cursor.execute.call_args[0][0]
    assert "r.score_team1_role1 AS score_role1" in query
    assert "r.score_team1_role2 AS score_role2" in query
    assert "r.score_team2_role1 AS score_role1" in query
    assert "r.score_team2_role2 AS score_role2" in query
    assert "CASE WHEN r.score_team1_role1 = -1" not in query


@pytest.mark.unit
def test_get_error_matchups_flags_null_scores():
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = [
        (1, "A", 1, "B", 2, None, 0.4, None, 0.6),
    ]
    conn = _mock_connection(cursor)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(database_handler, "get_connection", lambda: conn)
        results = database_handler.get_error_matchups(10)

    assert results == [[1, ["A", 1], ["B", 2], 1, 1]]

    query = cursor.execute.call_args[0][0]
    assert "score_team1_role1 IS NULL" in query
    assert "score_team1_role2 IS NULL" in query
