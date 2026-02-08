import random
import time
from datetime import datetime

import streamlit as st

from ..control_panel_ui_helpers import build_year_class_options, format_year_class_option
from ..database_handler import (
    get_academic_year_class_combinations,
    get_game_by_id,
    get_game_parameters,
    get_group_ids_from_game_id,
    populate_plays_table,
    store_game_parameters,
    store_group_values,
    update_game_in_db,
)


def render_setup_tab(selected_game: dict, game_key_suffix: str) -> None:
    msg = st.session_state.pop("cc_setup_game_message", None)
    if msg:
        getattr(st, msg[0])(msg[1])

    game_id = selected_game["game_id"]
    game_details = get_game_by_id(game_id)
    if not game_details:
        st.error("Game not found.")
        return

    created_by_stored = game_details["created_by"]
    game_name_stored = game_details["game_name"]
    name_roles_1_stored = game_details["name_roles"].split("#_;:)")[0]
    name_roles_2_stored = game_details["name_roles"].split("#_;:)")[1]
    game_academic_year_stored = game_details["game_academic_year"]
    game_class_stored = game_details["game_class"]
    if game_class_stored in {"", "_"}:
        game_class_stored = None
    password_stored = game_details["password"]
    timestamp_game_creation_stored = game_details["timestamp_game_creation"]
    deadline_date_stored = game_details["timestamp_submission_deadline"].date()
    deadline_time_stored = game_details["timestamp_submission_deadline"].time()
    game_explanation_stored = game_details.get("explanation", "")
    game_type = game_details.get("game_type", "zero_sum")

    params_data = get_game_parameters(game_id)
    if params_data:
        params_stored = [
            params_data["min_minimizer"],
            params_data["max_minimizer"],
            params_data["min_maximizer"],
            params_data["max_maximizer"],
        ]
    else:
        params_stored = [0, 0, 0, 0]
        st.warning("Game parameters not found.")

    academic_year_class_combinations = get_academic_year_class_combinations()
    if not academic_year_class_combinations:
        st.error("No academic year and class combinations found.")
        return

    combination_options = build_year_class_options(academic_year_class_combinations)
    stored_combination = (str(game_academic_year_stored), game_class_stored)
    stored_index = combination_options.index(stored_combination) if stored_combination in combination_options else 0

    game_type_label = "Zero Sum" if game_type == "zero_sum" else "Prisoner's Dilemma"
    st.write(f"Game Type: {game_type_label}")

    with st.form("cc_game_edit_form"):
        game_name_edit = st.text_input(
            "Game Name",
            max_chars=100,
            key=f"cc_game_name_edit_{game_key_suffix}",
            value=game_name_stored,
        )
        game_explanation_edit = st.text_area(
            "Game Explanation",
            key=f"cc_explanation_edit_{game_key_suffix}",
            value=game_explanation_stored,
        )

        col1, col2 = st.columns(2)
        with col1:
            name_roles_1_edit = st.text_input(
                "Name of Minimizer Role",
                key=f"cc_name_roles_1_edit_{game_key_suffix}",
                value=name_roles_1_stored,
            )
        with col2:
            name_roles_2_edit = st.text_input(
                "Name of Maximizer Role",
                key=f"cc_name_roles_2_edit_{game_key_suffix}",
                value=name_roles_2_stored,
            )

        st.markdown("#### Reservation Values")
        st.caption("Each group's reservation values are sampled from these ranges for the two roles.")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            param1_edit = st.number_input(
                "Lower Bound (Minimizer)",
                min_value=0,
                step=1,
                value=int(params_stored[0]),
                key=f"cc_param1_edit_{game_key_suffix}",
                help="For the minimizer role, reservation value means the highest acceptable deal value. This sets the minimum of that sampled threshold.",
            )
        with col2:
            param2_edit = st.number_input(
                "Upper Bound (Minimizer)",
                min_value=0,
                step=1,
                value=int(params_stored[1]),
                key=f"cc_param2_edit_{game_key_suffix}",
                help="For the minimizer role, reservation value means the highest acceptable deal value. This sets the maximum of that sampled threshold.",
            )
        with col3:
            param3_edit = st.number_input(
                "Lower Bound (Maximizer)",
                min_value=0,
                step=1,
                value=int(params_stored[2]),
                key=f"cc_param3_edit_{game_key_suffix}",
                help="For the maximizer role, reservation value means the lowest acceptable deal value. This sets the minimum of that sampled threshold.",
            )
        with col4:
            param4_edit = st.number_input(
                "Upper Bound (Maximizer)",
                min_value=0,
                step=1,
                value=int(params_stored[3]),
                key=f"cc_param4_edit_{game_key_suffix}",
                help="For the maximizer role, reservation value means the lowest acceptable deal value. This sets the maximum of that sampled threshold.",
            )

        selected_combination_edit = st.selectbox(
            "Select Academic Year and Class",
            options=combination_options,
            index=stored_index,
            format_func=format_year_class_option,
            key=f"cc_academic_year_class_combination_edit_{game_key_suffix}",
        )
        game_academic_year_edit, game_class_edit = selected_combination_edit

        password_edit = st.text_input(
            "Game Password (4-digit)",
            max_chars=4,
            key=f"cc_password_edit_{game_key_suffix}",
            value=password_stored,
        )
        deadline_date_edit = st.date_input(
            "Submission Deadline Date",
            key=f"cc_deadline_date_edit_{game_key_suffix}",
            value=deadline_date_stored,
        )
        deadline_time_edit = st.time_input(
            "Submission Deadline Time",
            key=f"cc_deadline_time_edit_{game_key_suffix}",
            value=deadline_time_stored,
        )

        submit_button = st.form_submit_button("Save Changes")

    if not submit_button:
        return

    if not (
        game_name_edit
        and game_explanation_edit
        and name_roles_1_edit
        and name_roles_2_edit
        and selected_combination_edit
        and password_edit
        and deadline_date_edit
        and deadline_time_edit
    ):
        warning = st.warning("Please fill out all fields before submitting.")
        time.sleep(1)
        warning.empty()
        return

    update_success = False
    try:
        submission_deadline = datetime.combine(deadline_date_edit, deadline_time_edit)
        name_roles_edit = name_roles_1_edit + "#_;:)" + name_roles_2_edit

        update_game_in_db(
            game_id,
            created_by_stored,
            game_name_edit,
            -1,
            name_roles_edit,
            game_academic_year_edit,
            game_class_edit,
            password_edit,
            timestamp_game_creation_stored,
            submission_deadline,
            game_explanation_edit,
        )

        if not populate_plays_table(game_id, game_academic_year_edit, game_class_edit):
            st.error("An error occurred while assigning students to the game.")
            return

        different_groups_classes = get_group_ids_from_game_id(game_id)
        if not store_game_parameters(game_id, param1_edit, param2_edit, param3_edit, param4_edit):
            st.error("Failed to update game parameters.")

        if (
            game_class_stored != game_class_edit
            or str(game_academic_year_stored) != game_academic_year_edit
            or params_stored[0] != param1_edit
            or params_stored[1] != param2_edit
            or params_stored[2] != param3_edit
            or params_stored[3] != param4_edit
        ):
            if different_groups_classes:
                for i in different_groups_classes:
                    buy_value = int(random.uniform(param1_edit, param2_edit))
                    sell_value = int(random.uniform(param3_edit, param4_edit))
                    if not store_group_values(game_id, i[0], i[1], buy_value, sell_value):
                        st.error(f"Failed to update values for group {i[0]}-{i[1]}.")

        update_success = True
    except Exception:
        st.error("An error occurred. Please try again.")

    if update_success:
        st.session_state.cc_setup_game_message = ("success", "Game saved successfully.")
        st.rerun()
