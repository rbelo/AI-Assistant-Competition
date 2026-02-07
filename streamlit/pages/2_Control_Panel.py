from modules.auth_guard import ensure_session_defaults, require_auth, require_instructor

import streamlit as st

st.set_page_config("Control Panel")
ensure_session_defaults()
require_auth("Control Panel")
require_instructor()

from modules.control_panel.state import initialize_control_panel_state
from modules.control_panel.view import render_control_center

initialize_control_panel_state()
render_control_center()
