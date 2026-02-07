import logging

from modules.control_panel.create_game import render_create_game_tab
from modules.control_panel.game_overview import render_game_overview_tab
from modules.control_panel.student_management import render_student_management_tab
from modules.sidebar import render_sidebar

import streamlit as st

logger = logging.getLogger(__name__)


def render_control_center():
    render_sidebar(current_page="control_panel")
    st.title("Control Panel")
    st.write("Welcome, Instructor!")
    if st.session_state.cc_game_created:
        st.success("Game created.")
        st.session_state.cc_game_created = False

    tabs = st.tabs(["Game Overview", "Create Game", "Student Management"])

    with tabs[0]:
        render_game_overview_tab()

    with tabs[1]:
        render_create_game_tab(logger)

    with tabs[2]:
        render_student_management_tab()
