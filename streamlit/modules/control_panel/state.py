import pandas as pd

import streamlit as st


def initialize_control_panel_state():
    if "cc_game_creation_in_progress" not in st.session_state:
        st.session_state.cc_game_creation_in_progress = False
    if "cc_add_students" not in st.session_state:
        st.session_state.cc_add_students = False
    if "cc_add_student" not in st.session_state:
        st.session_state.cc_add_student = False
    if "cc_remove_student" not in st.session_state:
        st.session_state.cc_remove_student = False
    if "cc_selected_student" not in st.session_state:
        st.session_state.cc_selected_student = None
    if "cc_students" not in st.session_state:
        st.session_state.cc_students = pd.DataFrame(
            columns=["User ID", "Email", "Academic Year", "Class", "Created at"]
        )
    if "cc_game_created" not in st.session_state:
        st.session_state.cc_game_created = False
    if "cc_pending_selected_year" not in st.session_state:
        st.session_state.cc_pending_selected_year = None
    if "cc_pending_selected_game" not in st.session_state:
        st.session_state.cc_pending_selected_game = None
