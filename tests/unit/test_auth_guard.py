import os
import sys
from unittest.mock import patch

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules import auth_guard  # noqa: E402


class TestEnsureSessionDefaults:
    @pytest.mark.unit
    def test_sets_missing_defaults(self):
        mock_st = type("MockSt", (), {})()
        mock_st.session_state = {}
        with patch.object(auth_guard, "st", mock_st):
            auth_guard.ensure_session_defaults()

        assert mock_st.session_state["authenticated"] is False
        assert mock_st.session_state["instructor"] is False
        assert mock_st.session_state["user_id"] == ""
        assert mock_st.session_state["login_email"] == ""

    @pytest.mark.unit
    def test_preserves_existing_values(self):
        mock_st = type("MockSt", (), {})()
        mock_st.session_state = {"authenticated": True, "user_id": "abc123"}
        with patch.object(auth_guard, "st", mock_st):
            auth_guard.ensure_session_defaults()

        assert mock_st.session_state["authenticated"] is True
        assert mock_st.session_state["user_id"] == "abc123"


class TestRequireAuth:
    @pytest.mark.unit
    def test_redirects_and_stops_when_not_authenticated(self):
        mock_st = type("MockSt", (), {})()
        mock_st.session_state = {"authenticated": False}
        with (
            patch.object(auth_guard, "st", mock_st),
            patch.object(mock_st, "warning", create=True) as warning,
            patch.object(mock_st, "switch_page", create=True) as switch_page,
            patch.object(mock_st, "stop", create=True, side_effect=RuntimeError("stop")) as stop,
        ):
            with pytest.raises(RuntimeError, match="stop"):
                auth_guard.require_auth("Playground")

        warning.assert_called_once()
        switch_page.assert_called_once_with("0_Home.py")
        stop.assert_called_once()

    @pytest.mark.unit
    def test_passes_when_authenticated(self):
        mock_st = type("MockSt", (), {})()
        mock_st.session_state = {"authenticated": True}
        with (
            patch.object(auth_guard, "st", mock_st),
            patch.object(mock_st, "warning", create=True) as warning,
            patch.object(mock_st, "switch_page", create=True) as switch_page,
            patch.object(mock_st, "stop", create=True) as stop,
        ):
            auth_guard.require_auth("Play")

        warning.assert_not_called()
        switch_page.assert_not_called()
        stop.assert_not_called()


class TestRequireInstructor:
    @pytest.mark.unit
    def test_redirects_and_stops_when_not_instructor(self):
        mock_st = type("MockSt", (), {})()
        mock_st.session_state = {"authenticated": True, "instructor": False}
        with (
            patch.object(auth_guard, "st", mock_st),
            patch.object(mock_st, "warning", create=True) as warning,
            patch.object(mock_st, "switch_page", create=True) as switch_page,
            patch.object(mock_st, "stop", create=True, side_effect=RuntimeError("stop")) as stop,
        ):
            with pytest.raises(RuntimeError, match="stop"):
                auth_guard.require_instructor()

        warning.assert_called_once()
        switch_page.assert_called_once_with("0_Home.py")
        stop.assert_called_once()

    @pytest.mark.unit
    def test_passes_when_instructor(self):
        mock_st = type("MockSt", (), {})()
        mock_st.session_state = {"authenticated": True, "instructor": True}
        with (
            patch.object(auth_guard, "st", mock_st),
            patch.object(mock_st, "warning", create=True) as warning,
            patch.object(mock_st, "switch_page", create=True) as switch_page,
            patch.object(mock_st, "stop", create=True) as stop,
        ):
            auth_guard.require_instructor()

        warning.assert_not_called()
        switch_page.assert_not_called()
        stop.assert_not_called()
