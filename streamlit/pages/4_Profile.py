import hashlib
import time

from modules.auth_guard import ensure_session_defaults, require_auth

import streamlit as st

ensure_session_defaults()
require_auth("Profile")

import pandas as pd
from modules.control_panel_ui_helpers import format_game_selector_label
from modules.database_handler import (
    add_user_api_key,
    delete_user_api_key,
    fetch_and_compute_scores_for_game_ids,
    fetch_and_compute_scores_for_year_game,
    fetch_game_ids_for_user,
    fetch_student_visible_games,
    get_class_from_user_id,
    get_group_id_from_user_id,
    get_students_from_db,
    get_user_api_key,
    list_user_api_keys,
    update_password,
    update_user_api_key,
    update_user_api_key_name,
)
from modules.sidebar import render_sidebar

# Initialize session state for buttons if not set
if "password_edit_mode" not in st.session_state:
    st.session_state["password_edit_mode"] = False

if "show_password" not in st.session_state:
    st.session_state["show_password"] = False  # Track password visibility state

render_sidebar(current_page="profile")


def render_password_section(email):
    st.markdown("<h3 style='font-size: 24px;'>Password</h3>", unsafe_allow_html=True)
    password = st.session_state.get("login_password", "")
    if st.session_state["show_password"]:
        st.write(f"{password if password else 'Not defined'}")
    else:
        st.text("*******" if password else "Not defined")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.checkbox("Show password", key="show_password")
    with col2:
        if st.button("Edit password", key="edit_password"):
            st.session_state["password_edit_mode"] = not st.session_state["password_edit_mode"]
            st.rerun()

    if st.session_state["password_edit_mode"]:
        with st.form(key="password_form"):
            new_password = st.text_input(
                "**Enter new password**",
                type="password",
                key="new_password_input",
                help="Min 8 chars, uppercase, lowercase, digit, special char (!@#$%^&*...)",
            )
            confirm_password = st.text_input("**Confirm new password**", type="password", key="confirm_password_input")
            update_password_btn = st.form_submit_button("Update Password")

            if update_password_btn:
                if new_password and confirm_password:
                    if new_password == confirm_password:
                        if (
                            len(new_password) >= 8
                            and any(char.isupper() for char in new_password)
                            and any(char.islower() for char in new_password)
                            and any(char.isdigit() for char in new_password)
                            and any(char in "!@#$%^&*()-_=+[]{}|;:,.<>?/`~" for char in new_password)
                        ):

                            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()

                            if update_password(email, hashed_password):
                                st.success("Password updated.")
                                st.session_state["login_password"] = new_password
                                st.session_state["password_edit_mode"] = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to update password.")
                        else:
                            st.error("Password must be at least 8 characters long and include an uppercase letter, \
                                        a lowercase letter, a number, and a special character.")
                    else:
                        st.error("Passwords do not match.")
                else:
                    error = st.error("Please fill in both password fields.")
                    time.sleep(1)
                    error.empty()


def _format_key_date(updated_at):
    if not updated_at:
        return "unknown"
    if hasattr(updated_at, "strftime"):
        return updated_at.strftime("%Y-%m-%d %H:%M")
    return str(updated_at)


def render_api_keys_section(user_id, usage_label):
    st.markdown("<h3 style='font-size: 24px;'>API Keys</h3>", unsafe_allow_html=True)
    st.caption("Keys are stored encrypted.")
    st.info(
        "API keys power your AI agents in negotiations. "
        "Get one free at [OpenAI](https://platform.openai.com/api-keys)."
    )

    keys = list_user_api_keys(user_id)
    if not keys:
        st.warning(f"No API keys saved. Add one below to use {usage_label}.")

    @st.dialog("Add API key")
    def add_key_dialog():
        key_name = st.text_input("Key name", max_chars=100, key=f"api_key_name_{user_id}")
        api_key_input = st.text_input(
            "OpenAI API key",
            type="password",
            key=f"api_key_value_{user_id}",
        )
        if st.button("Save API key", key=f"api_key_add_submit_{user_id}"):
            if not key_name or not api_key_input:
                st.error("Please enter both a name and an API key.")
            elif add_user_api_key(user_id, key_name, api_key_input):
                st.success("API key saved.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to save API key. Check API_KEY_ENCRYPTION_KEY.")

    @st.dialog("Edit API key")
    def edit_key_dialog(selected_key):
        st.caption(f"Last updated: {_format_key_date(selected_key['updated_at'])}")
        existing_key = get_user_api_key(user_id, selected_key["key_id"])
        if existing_key is None:
            st.error("Unable to load the existing key. Please re-save it.")
            return
        new_name = st.text_input(
            "Key name",
            value=selected_key["key_name"],
            max_chars=100,
            key=f"edit_api_key_name_{selected_key['key_id']}",
        )
        api_key_input = st.text_input(
            "OpenAI API key",
            value=existing_key,
            type="password",
            key=f"edit_api_key_value_{selected_key['key_id']}",
        )
        if st.button("Save changes", key=f"api_key_edit_submit_{selected_key['key_id']}"):
            if not new_name:
                st.error("Please enter a name.")
            elif api_key_input != existing_key:
                if update_user_api_key(user_id, selected_key["key_id"], new_name, api_key_input):
                    st.success("API key updated.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to update key. Check API_KEY_ENCRYPTION_KEY.")
            elif new_name != selected_key["key_name"]:
                if update_user_api_key_name(user_id, selected_key["key_id"], new_name):
                    st.success("Key name updated.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to update key name.")
            else:
                st.info("No changes to save.")

    @st.dialog("Delete API key")
    def delete_key_dialog(selected_key):
        st.caption(f"Last updated: {_format_key_date(selected_key['updated_at'])}")
        st.warning("This will permanently delete the selected key.")
        confirm_delete = st.checkbox(
            "I understand this will delete the key.",
            key=f"delete_api_key_confirm_{selected_key['key_id']}",
        )
        if st.button("Delete key", key=f"api_key_delete_submit_{selected_key['key_id']}"):
            if not confirm_delete:
                st.error("Please confirm deletion.")
            elif delete_user_api_key(user_id, selected_key["key_id"]):
                st.success("Key deleted.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to delete key.")

    selected_key = None
    if keys:
        options = {key["key_name"]: key for key in keys}
        selected_label = st.selectbox(
            "Saved keys",
            options=list(options.keys()),
            key=f"api_key_select_{user_id}",
        )
        selected_key = options[selected_label]

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Add key", key=f"api_key_add_btn_{user_id}"):
            add_key_dialog()
    with col2:
        if st.button(
            "Edit key",
            key=f"api_key_edit_btn_{user_id}",
            disabled=selected_key is None,
        ):
            edit_key_dialog(selected_key)
    with col3:
        if st.button(
            "Delete key",
            key=f"api_key_delete_btn_{user_id}",
            disabled=selected_key is None,
        ):
            delete_key_dialog(selected_key)


def _render_leaderboard_table(
    leaderboard, class_, group_id, role_1_label="Minimizer Role", role_2_label="Maximizer Role"
):
    if not leaderboard:
        st.write("Leaderboard not available yet.")
        return

    leaderboard_with_position = [
        {
            "Class": row["team_class"],
            "Group ID": row["team_id"],
            "Games": row["total_games"],
            "Avg Rounds": row["avg_rounds_per_game"],
            "Avg Score": row["average_score"],
            f"Rank ({role_1_label})": row["position_name_roles_1"],
            f"Score ({role_1_label})": row["score_name_roles_1"],
            f"Rank ({role_2_label})": row["position_name_roles_2"],
            f"Score ({role_2_label})": row["score_name_roles_2"],
        }
        for row in leaderboard
    ]

    leaderboard_df = pd.DataFrame(
        leaderboard_with_position,
        columns=[
            "Class",
            "Group ID",
            "Games",
            "Avg Rounds",
            "Avg Score",
            f"Rank ({role_1_label})",
            f"Score ({role_1_label})",
            f"Rank ({role_2_label})",
            f"Score ({role_2_label})",
        ],
    )

    leaderboard_df["Avg Rounds"] = pd.to_numeric(leaderboard_df["Avg Rounds"], errors="coerce").round(2)
    leaderboard_df["Avg Score"] = leaderboard_df["Avg Score"].round(2)
    leaderboard_df[f"Score ({role_1_label})"] = leaderboard_df[f"Score ({role_1_label})"].round(2)
    leaderboard_df[f"Score ({role_2_label})"] = leaderboard_df[f"Score ({role_2_label})"].round(2)
    leaderboard_df.index = leaderboard_df.index + 1

    def color_coding(row):
        return (
            ["background-color:rgba(0, 255, 0, 0.25"] * len(row)
            if row["Class"] == class_ and row["Group ID"] == group_id
            else [""] * len(row)
        )

    st.dataframe(
        leaderboard_df.style.apply(color_coding, axis=1).format(precision=2),
        width="stretch",
        column_config={
            "Class": st.column_config.TextColumn(width="small"),
            "Group ID": st.column_config.NumberColumn(width="small"),
            "Games": st.column_config.NumberColumn(width="small", help="Total games played"),
            "Avg Rounds": st.column_config.NumberColumn(width="small", help="Average rounds per game"),
            "Avg Score": st.column_config.NumberColumn(width="small", help="Average score across games"),
            f"Rank ({role_1_label})": st.column_config.NumberColumn(width="small"),
            f"Score ({role_1_label})": st.column_config.NumberColumn(width="small"),
            f"Rank ({role_2_label})": st.column_config.NumberColumn(width="small"),
            f"Score ({role_2_label})": st.column_config.NumberColumn(width="small"),
        },
    )


def _render_student_leaderboard_sections(user_id, class_, group_id, key_prefix):
    visible_games = fetch_student_visible_games(user_id)
    if not visible_games:
        st.write("No leaderboard available yet.")
        return

    subtab_overall, subtab_by_game = st.tabs(["Overall", "By Game"])

    with subtab_overall:
        st.subheader("Overall (Participating Games)")
        user_game_ids = fetch_game_ids_for_user(user_id, available_only=True)
        overall_leaderboard = fetch_and_compute_scores_for_game_ids(user_game_ids)
        _render_leaderboard_table(overall_leaderboard, class_, group_id)

    with subtab_by_game:
        game_labels = [
            format_game_selector_label(game["game_academic_year"], game["game_class"], game["game_name"])
            for game in visible_games
        ]
        selected_label = st.selectbox("Select Game", game_labels, key=f"{key_prefix}_selected_game")
        selected_index = game_labels.index(selected_label)
        selected_game = visible_games[selected_index]

        role_labels = selected_game["name_roles"].split("#_;:)")
        role_1_label = role_labels[0]
        role_2_label = role_labels[1]

        leaderboard = fetch_and_compute_scores_for_year_game(selected_game["game_id"])
        _render_leaderboard_table(leaderboard, class_, group_id, role_1_label, role_2_label)


# Check if the user is logged in
if st.session_state.get("authenticated", False):

    if st.session_state.instructor:

        st.title("Profile")
        tab_instructor_profile, tab_student_view = st.tabs(["Personal Data", "Student View"])

        with tab_instructor_profile:
            email = st.session_state["login_email"]
            st.markdown("<h3 style='font-size: 24px;'>Email</h3>", unsafe_allow_html=True)
            st.write(f"{email}")

            user_id = st.session_state["user_id"]
            st.markdown("<h3 style='font-size: 24px;'>User ID</h3>", unsafe_allow_html=True)
            st.write(f"{user_id}")

            render_password_section(email)
            render_api_keys_section(user_id, "the Playground and Simulations")

        with tab_student_view:
            st.header("Student View")
            students_df = get_students_from_db()
            if not isinstance(students_df, pd.DataFrame) or students_df.empty:
                st.info("No students found.")
            else:
                students_df = students_df.copy()
                students_df["label"] = students_df.apply(
                    lambda row: (
                        f"{row['user_id']} • {row['email']} • "
                        f"{row['academic_year']} • {row['class']} • Group {row['group_id']}"
                    ),
                    axis=1,
                )
                label_options = students_df["label"].tolist()
                selected_label = st.selectbox("Select Student", label_options, key="profile_instructor_student_select")
                selected_row = students_df[students_df["label"] == selected_label].iloc[0]

                st.markdown("### Basic Information")
                st.write(f"**User ID:** {selected_row['user_id']}")
                st.write(f"**Email:** {selected_row['email']}")
                st.write(f"**Academic Year:** {selected_row['academic_year']}")
                st.write(f"**Class:** {selected_row['class']}")
                st.write(f"**Group ID:** {selected_row['group_id']}")

                st.markdown("### Leaderboard")
                _render_student_leaderboard_sections(
                    user_id=str(selected_row["user_id"]),
                    class_=selected_row["class"],
                    group_id=selected_row["group_id"],
                    key_prefix=f"profile_instructor_student_{selected_row['user_id']}",
                )

    elif not st.session_state.instructor:

        CLASS = get_class_from_user_id(st.session_state["user_id"])
        GROUP_ID = get_group_id_from_user_id(st.session_state["user_id"])
        USER_ID = st.session_state["user_id"]

        st.title("Profile")
        tab_personal, tab_leaderboard = st.tabs(["Personal Data", "Leaderboard"])

        with tab_personal:
            st.header("Personal Data")

            email = st.session_state["login_email"]
            st.markdown("<h3 style='font-size: 24px;'>Email</h3>", unsafe_allow_html=True)
            st.write(f"{email}")

            st.markdown("<h3 style='font-size: 24px;'>User ID</h3>", unsafe_allow_html=True)
            st.write(f"{USER_ID}")

            render_password_section(email)
            render_api_keys_section(USER_ID, "the Playground")

        with tab_leaderboard:
            st.header("Leaderboard")
            _render_student_leaderboard_sections(
                user_id=USER_ID,
                class_=CLASS,
                group_id=GROUP_ID,
                key_prefix="profile_student",
            )
