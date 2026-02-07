import os
import sys
from unittest.mock import MagicMock, patch

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules import sidebar  # noqa: E402


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.unit
def test_sidebar_renders_version_below_user_role():
    mock_st = MagicMock()
    mock_st.session_state = {
        "authenticated": True,
        "instructor": True,
        "login_email": "admin@example.com",
    }
    mock_st.sidebar = _DummyContext()
    mock_st.button.return_value = False

    with patch.object(sidebar, "st", mock_st), patch.object(sidebar, "get_app_version", return_value="v2026-02-07.4"):
        sidebar.render_sidebar(current_page="home")

    mock_st.caption.assert_any_call("admin@example.com • Instructor")
    mock_st.caption.assert_any_call("Version: v2026-02-07.4")
