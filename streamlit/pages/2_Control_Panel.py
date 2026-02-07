from modules.control_panel.state import initialize_control_panel_state
from modules.control_panel.view import render_control_center

import streamlit as st

st.set_page_config("Control Panel")
initialize_control_panel_state()

if st.session_state.get("authenticated"):
    if st.session_state.get("instructor"):
        render_control_center()
    else:
        st.title("Control Panel")
        st.write("Page accessible only to Instructors.")
else:
    st.title("Control Panel")
    st.write("Please Login first. (Page accessible only to Instructors)")
