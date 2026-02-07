import re

from modules.auth_guard import ensure_session_defaults, require_auth

import streamlit as st

ensure_session_defaults()
require_auth("Play")

from modules.database_handler import (
    fetch_games_data_by_user_id,
    get_academic_years_of_students,
    get_class_and_group_from_user_id,
    get_classes_of_students,
    get_group_values,
    get_groups_of_students,
    get_negotiation_chat,
    get_round_data_by_class_group_id,
    get_student_prompt,
    get_user_id_of_student,
    insert_student_prompt,
)
from modules.sidebar import render_sidebar

# ------------------------ SET THE DEFAULT SESSION STATE FOR THE PLAY SECTION ---------------------------- #

# Initialize session state for show password form
if "not_show_game_password_form" not in st.session_state:
    st.session_state.not_show_game_password_form = []

# Initialize session state for game tracking
if "game_started" not in st.session_state:
    st.session_state.game_started = {}
elif not isinstance(st.session_state.game_started, dict):
    st.session_state.game_started = {}

render_sidebar(current_page="play")

# -------------------------------------------------------------------------------------------------------- #

# Check if the user is authenticated
if st.session_state.get("authenticated", False):

    st.title("Play")

    if st.session_state["instructor"]:
        academic_years_students = get_academic_years_of_students()

        # Instructor selectors in horizontal row
        col1, col2, col3 = st.columns(3)
        with col1:
            select_year = st.selectbox("Select Academic Year", academic_years_students)

        classes_students = get_classes_of_students(select_year)
        with col2:
            CLASS = st.selectbox("Select Class", classes_students)

        groups_students = get_groups_of_students(select_year, CLASS)
        with col3:
            GROUP_ID = st.selectbox("Select Group", groups_students)

        USER_ID = get_user_id_of_student(select_year, CLASS, GROUP_ID)

    else:
        CLASS, GROUP_ID = get_class_and_group_from_user_id(st.session_state["user_id"])
        USER_ID = st.session_state.user_id

    games = fetch_games_data_by_user_id(USER_ID)

    if games:

        def format_deadline(game):
            deadline = game.get("timestamp_submission_deadline")
            if hasattr(deadline, "strftime"):
                return deadline.strftime("%Y-%m-%d %H:%M")
            return str(deadline)

        game_labels = [f"{game['game_name']} ({game['status']}) - deadline {format_deadline(game)}" for game in games]
        game_id_by_label = {label: game["game_id"] for label, game in zip(game_labels, games)}
        selected_label = st.selectbox("Select Game", game_labels)
        selected_game_id = game_id_by_label.get(selected_label)
        selected_game = next((game for game in games if game["game_id"] == selected_game_id), None)
        if not selected_game:
            st.write("Game not found.")
            st.stop()

        st.subheader(selected_game["game_name"])
        st.write(f"Status: {selected_game['status']}")

        deadline = selected_game["timestamp_submission_deadline"]
        deadline_display = deadline.strftime("%Y-%m-%d %H:%M") if hasattr(deadline, "strftime") else str(deadline)
        st.write(f"**Submission Deadline:** {deadline_display}")

        game_id = selected_game["game_id"]
        name_roles = selected_game["name_roles"].split("#_;:)")
        name_roles_1, name_roles_2 = name_roles[0], name_roles[1]

        if not isinstance(st.session_state.game_started, dict):
            st.session_state.game_started = {}

        if selected_game["status"] == "Active":
            if str(game_id) not in st.session_state.game_started:
                st.session_state.game_started[str(game_id)] = True

        with st.expander("**Explanation**", expanded=True):
            game_explanation = selected_game.get("explanation")
            if game_explanation:
                st.write(
                    f"{game_explanation}\n\n**Note:** The game explanation is not passed automatically to the agent. If you want to do it, you must place it in the prompt explicitly."
                )
            else:
                st.write("No explanation found for this game. Please contact your Instructor.")

        with st.expander("**Private Information**", expanded=False):
            st.write(
                "Note: Private information is not injected into your agent. Include it in your prompt if you want the agent to use it."
            )

            group_values = get_group_values(game_id, CLASS, GROUP_ID)
            if group_values:
                st.write("The following information is private and group-specific. Do not share it with others:")
                st.write(
                    f"When playing as **{name_roles_1}**, your reservation value is: **{group_values['minimizer_value']}**;"
                )
                st.write(
                    f"When playing as **{name_roles_2}**, your reservation value is: **{group_values['maximizer_value']}**."
                )
            else:
                st.write("No private information found for this game.")

        submission = get_student_prompt(game_id, CLASS, GROUP_ID)

        if selected_game["status"] == "Active":
            if selected_game not in st.session_state.not_show_game_password_form:
                with st.form("insert_password_form"):
                    st.write("Please introduce the Password to play this Game.")
                    password_input = st.text_input(
                        "Enter the Game Password", key="game_password_input", placeholder="4-digit code"
                    )

                    play_now_btn = st.form_submit_button("Play now!")

                    if play_now_btn:
                        if selected_game["password"] == password_input:
                            st.success("Password verified.")
                            st.session_state.not_show_game_password_form.append(selected_game)
                            st.rerun()
                        else:
                            st.error("Incorrect Password. Please try again.")

            if selected_game in st.session_state.not_show_game_password_form:
                st.write("")

                if submission:
                    submission_parts = submission.split("#_;:)")
                    default_prompt_1 = submission_parts[0].strip()
                    default_prompt_2 = submission_parts[1].strip() if len(submission_parts) > 1 else ""
                else:
                    default_prompt_1 = ""
                    default_prompt_2 = ""

                prompt_key_base = f"prompt_{game_id}_{CLASS}_{GROUP_ID}"
                with st.form(key="form_inputs"):
                    text_area_1 = st.text_area(
                        f"{name_roles_1} Prompt",
                        max_chars=7000,
                        value=default_prompt_1,
                        key=f"{prompt_key_base}_role1",
                        help="A good prompt should be clear, specific, and provide enough context and detail about your position, interests, and desired outcomes. The game explanation and private info are not passed automatically; include them in the prompt if you want the agent to use them.",
                    )
                    text_area_2 = st.text_area(
                        f"{name_roles_2} Prompt",
                        max_chars=7000,
                        value=default_prompt_2,
                        key=f"{prompt_key_base}_role2",
                    )
                    submit_button = st.form_submit_button("Submit")

                if submit_button:
                    prompts = text_area_1 + "\n\n" + "#_;:)" + "\n\n" + text_area_2
                    insert_student_prompt(game_id, CLASS, GROUP_ID, prompts, USER_ID)
                    st.success("Prompts submitted.")
                    st.info("You can adjust your prompts anytime before the submission deadline shown above.")
                    st.info("Want to test prompt variations? Try the Playground to experiment before submitting.")
                    st.page_link("pages/3_Playground.py", label="Go to Playground", icon=":material/science:")
        else:
            if submission:
                with st.expander("**View Prompts**"):
                    submission_parts = submission.split("#_;:)")
                    st.write(f"**{name_roles_1}:** {submission_parts[0].strip()}")
                    st.write(f"**{name_roles_2}:** {submission_parts[1].strip()}")
            else:
                st.write("No prompts found. Please contact your Instructor.")

        if selected_game["available"] == 1:
            round_data = get_round_data_by_class_group_id(game_id, CLASS, GROUP_ID)
            if round_data:
                if not isinstance(st.session_state.game_started, dict):
                    st.session_state.game_started = {}

                if str(game_id) in st.session_state.game_started:
                    del st.session_state.game_started[str(game_id)]

                files_names = []
                for i in range(len(round_data)):
                    round_number = round_data[i][0]
                    class_1, group_1, class_2, group_2 = (
                        round_data[i][1],
                        round_data[i][2],
                        round_data[i][3],
                        round_data[i][4],
                    )
                    if class_1 == CLASS and group_1 == GROUP_ID:
                        files_names.append([round_number, class_2, group_2])
                    else:
                        files_names.append([round_number, class_1, group_1])

                options = [name_roles_1, name_roles_2]
                col1, col2 = st.columns(2)
                with col1:
                    selection = st.radio(label="Select Your Position", options=options, horizontal=True)

                options_chat = [f"Round {i[0]} (vs Class {i[1]} - Group {i[2]})" for i in files_names]
                with col2:
                    chat_selector = st.selectbox("Select Negotiation Chat", options_chat)

                st.markdown(f"### {chat_selector}")

                aux_ = chat_selector.split("Class ")
                round_number = int(re.findall(r"\d+", aux_[0])[0])
                class_ = aux_[1][0]
                group_ = int(re.findall(r"\d+", aux_[1])[0])

                if selection == name_roles_1:
                    chat = get_negotiation_chat(game_id, round_number, CLASS, GROUP_ID, class_, group_)
                    if chat:
                        st.write(chat.replace("$", r"\$"))
                    else:
                        st.write("Chat not found. Please contact your Instructor.")
                elif selection == name_roles_2:
                    chat = get_negotiation_chat(game_id, round_number, class_, group_, CLASS, GROUP_ID)
                    if chat:
                        st.write(chat.replace("$", r"\$"))
                    else:
                        st.write("Chat not found. Please contact your Instructor.")
            else:
                st.write("You do not have any chats available. Please contact your Instructor.")
        else:
            st.write("Negotiation Chats are not available yet.")
    else:
        st.info(
            "No games available yet. Your instructor will create games for you to join. "
            "In the meantime, you can test prompt ideas in the Playground."
        )
        st.page_link("pages/3_Playground.py", label="Go to Playground", icon=":material/science:")
