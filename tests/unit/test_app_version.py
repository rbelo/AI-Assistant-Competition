import os
import sys

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules.app_version import DEFAULT_APP_VERSION, get_app_version  # noqa: E402


@pytest.mark.unit
def test_get_app_version_returns_default_constant():
    assert get_app_version() == DEFAULT_APP_VERSION
