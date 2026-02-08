import random
from datetime import datetime, timedelta

import streamlit as st

from ..control_panel_ui_helpers import build_year_class_options, format_game_selector_label, format_year_class_option
from ..database_handler import (
    get_academic_year_class_combinations,
    get_group_ids_from_game_id,
    get_next_game_id,
    populate_plays_table,
    store_game_in_db,
    store_game_parameters,
    store_group_values,
)


def render_create_game_tab(logger):
    msg = st.session_state.pop("cc_create_game_message", None)
    if msg:
        getattr(st, msg[0])(msg[1])

    academic_year_class_combinations = get_academic_year_class_combinations()
    if not academic_year_class_combinations:
        st.error("No academic year and class combinations found. Please make sure there are students in the database.")
        return

    combination_options = build_year_class_options(academic_year_class_combinations)

    with st.form("cc_game_creation_form"):
        game_name = st.text_input("Game Name", max_chars=100, key="cc_game_name")
        game_explanation = st.text_area("Game Explanation", key="cc_explanation")
        game_type = st.selectbox(
            "Game Type",
            options=["zero_sum", "prisoners_dilemma"],
            format_func=lambda x: "Zero Sum" if x == "zero_sum" else "Prisoner's Dilemma",
            help="Select the type of game to create. Zero-sum games are negotiation games where one player's gain is another's loss. Prisoner's dilemma games involve strategic decision making with cooperation and defection options.",
            key="cc_game_type",
        )

        col1, col2 = st.columns(2)
        with col1:
            name_roles_1 = st.text_input("Name of Minimizer Role", value="Buyer", key="cc_name_roles_1")
        with col2:
            name_roles_2 = st.text_input("Name of Maximizer Role", value="Seller", key="cc_name_roles_2")

        st.markdown("#### Reservation Values")
        st.caption("Each group's reservation values are sampled from these ranges for the two roles.")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            param1 = st.number_input(
                "Lower Bound (Minimizer)",
                min_value=0,
                step=1,
                value=16,
                key="cc_param1",
                help="For the minimizer role, reservation value means the highest acceptable deal value. This sets the minimum of that sampled threshold.",
            )
        with col2:
            param2 = st.number_input(
                "Upper Bound (Minimizer)",
                min_value=0,
                step=1,
                value=25,
                key="cc_param2",
                help="For the minimizer role, reservation value means the highest acceptable deal value. This sets the maximum of that sampled threshold.",
            )
        with col3:
            param3 = st.number_input(
                "Lower Bound (Maximizer)",
                min_value=0,
                step=1,
                value=7,
                key="cc_param3",
                help="For the maximizer role, reservation value means the lowest acceptable deal value. This sets the minimum of that sampled threshold.",
            )
        with col4:
            param4 = st.number_input(
                "Upper Bound (Maximizer)",
                min_value=0,
                step=1,
                value=15,
                key="cc_param4",
                help="For the maximizer role, reservation value means the lowest acceptable deal value. This sets the maximum of that sampled threshold.",
            )

        selected_combination = st.selectbox(
            "Select Academic Year and Class",
            options=combination_options,
            format_func=format_year_class_option,
            key="cc_academic_year_class_combination",
        )
        game_academic_year, game_class = selected_combination

        password = st.text_input("Game Password (4-digit)", max_chars=4, key="cc_password")

        default_date = datetime.today().date() + timedelta(weeks=1)
        default_time = datetime.strptime("23:59", "%H:%M").time()
        deadline_date = st.date_input("Submission Deadline Date", value=default_date, key="cc_deadline_date")
        deadline_time = st.time_input("Submission Deadline Time", value=default_time, key="cc_deadline_time")

        submit_button = st.form_submit_button("Create Game")

    if submit_button and not st.session_state.cc_game_creation_in_progress:
        st.session_state.cc_game_creation_in_progress = True
        if (
            game_name
            and game_explanation
            and name_roles_1
            and name_roles_2
            and selected_combination
            and param1 is not None
            and param2 is not None
            and param3 is not None
            and param4 is not None
            and password
            and deadline_date
            and deadline_time
        ):
            try:
                user_id = st.session_state.get("user_id")
                next_game_id = get_next_game_id()
                timestamp_game_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                submission_deadline = datetime.combine(deadline_date, deadline_time)
                name_roles = name_roles_1 + "#_;:)" + name_roles_2

                if not store_game_in_db(
                    next_game_id,
                    0,
                    user_id,
                    game_name,
                    -1,
                    name_roles,
                    game_academic_year,
                    game_class,
                    password,
                    timestamp_game_creation,
                    submission_deadline,
                    game_explanation,
                    game_type,
                ):
                    st.session_state.cc_create_game_message = ("error", "Failed to create game in the database.")
                    st.session_state.cc_game_creation_in_progress = False
                    st.rerun()

                if not populate_plays_table(next_game_id, game_academic_year, game_class):
                    st.session_state.cc_create_game_message = (
                        "error",
                        "An error occurred while assigning students to the game.",
                    )
                    st.session_state.cc_game_creation_in_progress = False
                    st.rerun()

                different_groups_classes = get_group_ids_from_game_id(next_game_id)
                if different_groups_classes is False:
                    st.session_state.cc_create_game_message = (
                        "error",
                        "An error occurred while retrieving group information.",
                    )
                    st.session_state.cc_game_creation_in_progress = False
                    st.rerun()
                elif not different_groups_classes:
                    st.session_state.cc_create_game_message = (
                        "error",
                        "No eligible students found for this game.",
                    )
                    st.session_state.cc_game_creation_in_progress = False
                    st.rerun()

                if not store_game_parameters(next_game_id, param1, param2, param3, param4):
                    st.session_state.cc_create_game_message = (
                        "error",
                        "Failed to store game parameters.",
                    )
                    st.session_state.cc_game_creation_in_progress = False
                    st.rerun()

                for i in different_groups_classes:
                    buy_value = int(random.uniform(param1, param2))
                    sell_value = int(random.uniform(param3, param4))
                    if not store_group_values(next_game_id, i[0], i[1], buy_value, sell_value):
                        st.session_state.cc_create_game_message = (
                            "error",
                            f"Failed to store values for group {i[0]}-{i[1]}.",
                        )
                        st.session_state.cc_game_creation_in_progress = False
                        st.rerun()

                st.session_state.cc_game_created = True
                st.session_state.cc_pending_selected_year = game_academic_year
                st.session_state.cc_pending_selected_game = format_game_selector_label(
                    game_academic_year, game_class, game_name
                )
            except Exception as e:
                logger.exception("Game creation failed")
                st.session_state.cc_create_game_message = (
                    "error",
                    f"Game creation failed: {e}",
                )
            finally:
                st.session_state.cc_game_creation_in_progress = False
            st.rerun()
        else:
            st.session_state.cc_create_game_message = (
                "warning",
                "Please fill out all fields before submitting.",
            )
            st.session_state.cc_game_creation_in_progress = False
            st.rerun()
