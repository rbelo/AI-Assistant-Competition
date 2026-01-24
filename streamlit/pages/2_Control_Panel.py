import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import random
import re
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, ColumnsAutoSizeMode
from modules.sidebar import render_sidebar
from modules.database_handler import populate_plays_table, insert_student_data, remove_student, store_game_in_db, update_game_in_db, update_num_rounds_game, update_access_to_chats, delete_from_round, store_group_values, store_game_parameters, get_game_parameters
from modules.database_handler import get_academic_year_class_combinations, get_game_by_id, fetch_games_data, get_next_game_id, get_students_from_db, get_group_ids_from_game_id, get_round_data, get_error_matchups, fetch_and_compute_scores_for_year_game, get_negotiation_chat
from modules.database_handler import get_all_group_values, get_student_prompt, get_student_prompt_with_timestamp, upsert_game_simulation_params, get_game_simulation_params, delete_negotiation_chats
from modules.database_handler import get_instructor_api_key, upsert_instructor_api_key
from modules.negotiations import create_chats, create_all_error_chats
from modules.metrics_handler import record_page_entry, record_page_exit
from modules.student_utils import process_student_csv

# ---------------------------- SET THE DEFAULT SESSION STATE FOR ALL CASES ------------------------------- #
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
    st.session_state.cc_students = pd.DataFrame(columns=["User ID", "Email", "Academic Year", "Class", "Created at"])
if "cc_game_created" not in st.session_state:
    st.session_state.cc_game_created = False
if "cc_pending_selected_year" not in st.session_state:
    st.session_state.cc_pending_selected_year = None
if "cc_pending_selected_game" not in st.session_state:
    st.session_state.cc_pending_selected_game = None

render_sidebar()

def build_year_class_options(academic_year_class_combinations):
    combination_options = []
    for year, classes in academic_year_class_combinations.items():
        combination_options.append(f"{year}")
        combination_options.extend([f"{year} - {cls}" for cls in classes])
    return combination_options

def parse_year_class(selection):
    if "-" in selection:
        game_academic_year, game_class = selection.replace(" ", "").split("-")
    else:
        game_academic_year = selection
        game_class = "_"
    return game_academic_year, game_class

def render_control_center():
    st.title("Control Panel")
    st.write("Welcome, Instructor!")
    if st.session_state.cc_game_created:
        st.success("Game created successfully!")
        st.session_state.cc_game_created = False

    tabs = st.tabs(["Game Overview", "Create Game", "Student Management"])

    with tabs[0]:
        if st.session_state.cc_pending_selected_year:
            st.session_state.cc_selected_year = st.session_state.cc_pending_selected_year
            st.session_state.cc_pending_selected_year = None
        if st.session_state.cc_pending_selected_game:
            st.session_state.cc_selected_game = st.session_state.cc_pending_selected_game
            st.session_state.cc_pending_selected_game = None

        possible_years = fetch_games_data(get_academic_years=True)
        if not possible_years:
            st.info("No games found yet. Create your first game in the Create Game tab.")
            return

        year_options = ["All"] + possible_years

        col1, col2 = st.columns(2)
        with col1:
            selected_year = st.selectbox("Academic Year", year_options, key="cc_selected_year")

        if selected_year == "All":
            games_for_selected_year = []
            for year in possible_years:
                games_for_selected_year.extend(fetch_games_data(academic_year=year))
            games_for_selected_year.sort(key=lambda game: game["game_id"], reverse=True)
        else:
            games_for_selected_year = fetch_games_data(academic_year=selected_year)
        if not games_for_selected_year:
            st.write("No games for the selected academic year.")
            return

        game_labels = [
            f"{game['game_academic_year']}{'' if game['game_class'] == '_' else (' - ' + game['game_class'])} • {game['game_name']}"
            for game in games_for_selected_year
        ]
        game_id_by_label = {
            label: game["game_id"]
            for label, game in zip(game_labels, games_for_selected_year)
        }

        with col2:
            selected_game_label = st.selectbox("Game", game_labels, key="cc_selected_game")

        selected_game_id = game_id_by_label.get(selected_game_label)
        selected_game = next(
            (game for game in games_for_selected_year if game['game_id'] == selected_game_id),
            None
        )

        if not selected_game:
            st.warning("Game not found.")
            return

        game_key_suffix = str(selected_game["game_id"])

        st.subheader(selected_game['game_name'])
        overview_tabs = st.tabs(["Setup", "Submissions", "Simulation", "Results"])

        with overview_tabs[0]:
            game_id = selected_game['game_id']
            game_details = get_game_by_id(game_id)
            if not game_details:
                st.error("Game not found.")
                return

            created_by_stored = game_details["created_by"]
            game_name_stored = game_details["game_name"]
            name_roles_1_stored = game_details["name_roles"].split('#_;:)')[0]
            name_roles_2_stored = game_details["name_roles"].split('#_;:)')[1]
            game_academic_year_stored = game_details["game_academic_year"]
            game_class_stored = game_details["game_class"]
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
                    params_data["max_maximizer"]
                ]
            else:
                params_stored = [0, 0, 0, 0]
                st.warning("Game parameters not found.")

            academic_year_class_combinations = get_academic_year_class_combinations()
            if not academic_year_class_combinations:
                st.error("No academic year and class combinations found.")
                return

            combination_options = build_year_class_options(academic_year_class_combinations)
            if game_class_stored != "_":
                stored_combination = f"{game_academic_year_stored} - {game_class_stored}"
            else:
                stored_combination = f"{game_academic_year_stored}"
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

                st.write('')
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    param1_edit = st.number_input(
                        "Minimum Minimizer",
                        min_value=0,
                        step=1,
                        value=int(params_stored[0]),
                        key=f"cc_param1_edit_{game_key_suffix}",
                    )
                with col2:
                    param2_edit = st.number_input(
                        "Maximum Minimizer",
                        min_value=0,
                        step=1,
                        value=int(params_stored[1]),
                        key=f"cc_param2_edit_{game_key_suffix}",
                    )
                with col3:
                    param3_edit = st.number_input(
                        "Minimum Maximizer",
                        min_value=0,
                        step=1,
                        value=int(params_stored[2]),
                        key=f"cc_param3_edit_{game_key_suffix}",
                    )
                with col4:
                    param4_edit = st.number_input(
                        "Maximum Maximizer",
                        min_value=0,
                        step=1,
                        value=int(params_stored[3]),
                        key=f"cc_param4_edit_{game_key_suffix}",
                        help='All values are expressed in the unit mentioned in description.'
                    )

                selected_combination_edit = st.selectbox(
                    "Select Academic Year and Class",
                    options=combination_options,
                    index=stored_index,
                    key=f"cc_academic_year_class_combination_edit_{game_key_suffix}",
                )
                game_academic_year_edit, game_class_edit = parse_year_class(selected_combination_edit)

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

            if submit_button:
                if game_name_edit and game_explanation_edit and name_roles_1_edit and name_roles_2_edit and \
                    selected_combination_edit and password_edit and deadline_date_edit and deadline_time_edit:
                    update_success = False
                    try:
                        submission_deadline = datetime.combine(deadline_date_edit, deadline_time_edit)
                        name_roles_edit = name_roles_1_edit + '#_;:)' + name_roles_2_edit

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
                            game_explanation_edit
                        )

                        if not populate_plays_table(game_id, game_academic_year_edit, game_class_edit):
                            st.error("An error occurred while assigning students to the game.")

                        different_groups_classes = get_group_ids_from_game_id(game_id)
                        if not store_game_parameters(game_id, param1_edit, param2_edit, param3_edit, param4_edit):
                            st.error("Failed to update game parameters.")

                        if (game_class_stored != game_class_edit or
                            str(game_academic_year_stored) != game_academic_year_edit or
                            params_stored[0] != param1_edit or params_stored[1] != param2_edit or
                            params_stored[2] != param3_edit or params_stored[3] != param4_edit):
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
                        st.success("Game updated successfully!")
                        st.rerun()
                else:
                    warning = st.warning("Please fill out all fields before submitting.")
                    time.sleep(1)
                    warning.empty()

        with overview_tabs[1]:
            game_id = selected_game['game_id']
            name_roles = selected_game['name_roles'].split('#_;:)')
            name_roles_1, name_roles_2 = name_roles[0], name_roles[1]
            teams = get_group_ids_from_game_id(game_id)
            if teams is False:
                st.error("An error occurred while retrieving group information.")
            elif not teams:
                st.write("No teams found for this game.")
            else:
                submissions = []
                missing_groups = []
                for class_, group_id in teams:
                    prompt_data = get_student_prompt_with_timestamp(game_id, class_, group_id)
                    prompts = prompt_data["prompt"] if prompt_data else None
                    updated_at = prompt_data["updated_at"] if prompt_data else None
                    has_prompt = bool(prompts)
                    if not has_prompt:
                        missing_groups.append(f"Class {class_} - Group {group_id}")
                    submissions.append({
                        "Class": class_,
                        "Group": group_id,
                        "Status": "Submitted" if has_prompt else "Missing",
                        "Last Submission": updated_at,
                        "Prompts": prompts
                    })

                submitted_count = sum(1 for row in submissions if row["Status"] == "Submitted")
                st.write(f"Submitted: {submitted_count} / {len(submissions)}")
                if missing_groups:
                    st.warning("Missing submissions: " + ", ".join(missing_groups))

                submissions_df = pd.DataFrame([{
                    "Class": row["Class"],
                    "Group": row["Group"],
                    "Status": row["Status"],
                    "Last Submission": (
                        row["Last Submission"].strftime("%Y-%m-%d %H:%M")
                        if row["Last Submission"] else ""
                    )
                } for row in submissions])
                st.dataframe(submissions_df, use_container_width=True)

                with st.expander("View Prompts"):
                    for row in submissions:
                        with st.expander(f"Class {row['Class']} - Group {row['Group']}"):
                            if row["Prompts"]:
                                prompts = row["Prompts"].split('#_;:)')
                                st.write(f"**{name_roles_1}:** {prompts[0].strip()}")
                                st.write(f"**{name_roles_2}:** {prompts[1].strip()}")
                            else:
                                st.write("No submission found.")

        with overview_tabs[2]:
            game_id = selected_game['game_id']
            name_roles = selected_game['name_roles'].split('#_;:)')
            name_roles_1, name_roles_2 = name_roles[0], name_roles[1]

            sim_tabs = st.tabs(["Run Simulation", "Error Chats"])
            with sim_tabs[0]:
                saved_api_key = get_instructor_api_key(st.session_state.get('user_id'))
                use_saved_api_key = st.checkbox(
                    "Use saved API key",
                    value=bool(saved_api_key),
                    key="cc_use_saved_api_key_sim",
                )
                api_key_key = "cc_api_key_sim"
                if use_saved_api_key and saved_api_key:
                    if st.session_state.get(api_key_key) != saved_api_key:
                        st.session_state[api_key_key] = saved_api_key
                elif st.session_state.get(api_key_key) == saved_api_key:
                    st.session_state[api_key_key] = ""

                teams = get_group_ids_from_game_id(game_id)
                if teams is False:
                    st.error("An error occurred while retrieving group information.")
                    teams = []
                missing_submissions = []
                to_remove = []
                for i in teams:
                    prompts = get_student_prompt(game_id, i[0], i[1])
                    if not prompts:
                        to_remove.append(i)
                        missing_submissions.append(f"Class {i[0]} - Group {i[1]}")

                if missing_submissions:
                    st.warning("Missing submissions from: " + ", ".join(missing_submissions))

                for i in to_remove:
                    teams.remove(i)

                simulation_params = get_game_simulation_params(game_id)
                default_model = simulation_params["model"] if simulation_params else "gpt-4o-mini"
                default_starting_message = simulation_params["starting_message"] if simulation_params else "Hello, shall we start the negotiation?"
                default_num_turns = simulation_params["num_turns"] if simulation_params else 15
                default_negotiation_termination = simulation_params["negotiation_termination_message"] if simulation_params else "Pleasure doing business with you"
                default_summary_prompt = simulation_params["summary_prompt"] if simulation_params else "What was the value agreed?"
                default_summary_termination = simulation_params["summary_termination_message"] if simulation_params else "The value agreed was"
                default_order = simulation_params["conversation_order"] if simulation_params else "same"
                conversation_options = [f'{name_roles_1} ➡ {name_roles_2}', f'{name_roles_2} ➡ {name_roles_1}']
                default_order_index = 0 if default_order == "same" else 1

                if len(teams) >= 2:
                    st.warning(
                        "Attention: Running a new simulation will erase all previous data related to the game. "
                        "This includes all group chats and all group scores."
                    )
                    with st.form(key='cc_simulation_form'):
                        api_key = st.text_input('API Key', type="password", key=api_key_key)
                        save_api_key = st.checkbox("Save API key", value=False, key="cc_save_api_key_sim")
                        model = st.selectbox('OpenAI Model', ['gpt-4o-mini', 'gpt-4o'], index=0 if default_model == 'gpt-4o-mini' else 1, key="cc_model")
                        max_opponents = max(len(teams) - 1, 1)
                        opponents_per_team = st.number_input(
                            'Opponents per Team',
                            step=1,
                            min_value=1,
                            value=max_opponents,
                            max_value=max_opponents,
                            key="cc_opponents_per_team",
                            help="Each opponent is faced in both roles within the same round.",
                        )
                        rounds_to_run = opponents_per_team
                        if len(teams) % 2 != 0:
                            rounds_to_run = opponents_per_team + 1
                        conversation_starter = st.radio(
                            'Conversation Starter',
                            conversation_options,
                            horizontal=True,
                            index=default_order_index,
                            key="cc_conversation_starter",
                        )
                        starting_message = st.text_input('Starting Message', value=default_starting_message, key="cc_starting_message")
                        num_turns = st.number_input('Maximum Number of Turns', step=1, min_value=1, value=int(default_num_turns), key="cc_num_turns")
                        negotiation_termination_message = st.text_input(
                            'Negotiation Termination Message',
                            value=default_negotiation_termination,
                            key="cc_negotiation_termination_message",
                        )
                        summary_prompt = st.text_input('Negotiation Summary Prompt', value=default_summary_prompt, key="cc_summary_prompt")
                        summary_termination_message = st.text_input(
                            'Summary Termination Message',
                            value=default_summary_termination,
                            key="cc_summary_termination_message",
                        )

                        submit_button = st.form_submit_button(label='Run')

                    if submit_button:
                        resolved_api_key = api_key or (saved_api_key if use_saved_api_key else "")

                        if resolved_api_key and model and opponents_per_team and conversation_starter and starting_message and num_turns and \
                            negotiation_termination_message and summary_prompt and summary_termination_message:
                            if save_api_key and api_key:
                                if not upsert_instructor_api_key(st.session_state.get('user_id'), api_key):
                                    st.error("Failed to save API key. Check API_KEY_ENCRYPTION_KEY.")

                            status_placeholder = st.empty()
                            status_placeholder.info("Simulation started. This can take a few minutes...")
                            delete_from_round(game_id)
                            delete_negotiation_chats(game_id)

                            order = 'same' if conversation_starter.split(' ➡ ') == name_roles else 'opposite'
                            upsert_game_simulation_params(
                                game_id=game_id,
                                model=model,
                                conversation_order=order,
                                starting_message=starting_message,
                                num_turns=num_turns,
                                negotiation_termination_message=negotiation_termination_message,
                                summary_prompt=summary_prompt,
                                summary_termination_message=summary_termination_message,
                            )

                            update_num_rounds_game(rounds_to_run, game_id)

                            config_list = {"config_list": [{"model": model, "api_key": resolved_api_key}], "temperature": 0.3, "top_p": 0.5}
                            values = get_all_group_values(game_id)
                            if not values:
                                st.error("Failed to retrieve group values from database.")
                                st.stop()

                            progress_placeholder = st.empty()

                            def update_progress(round_num, team1, team2, chat_order):
                                role_1, role_2 = name_roles if chat_order == "same" else name_roles[::-1]
                                progress_placeholder.info(
                                    f"Round {round_num}: {team1['Name']} ({role_1}) vs {team2['Name']} ({role_2})"
                                )

                            with st.spinner("Running negotiations..."):
                                outcome_simulation = create_chats(
                                    game_id,
                                    config_list,
                                    name_roles,
                                    order,
                                    teams,
                                    values,
                                    rounds_to_run,
                                    starting_message,
                                    num_turns,
                                    negotiation_termination_message,
                                    summary_prompt,
                                    summary_termination_message,
                                    progress_callback=update_progress,
                                )
                            progress_placeholder.empty()
                            status_placeholder.empty()
                            if isinstance(outcome_simulation, dict) and outcome_simulation.get("status") == "success":
                                completed = outcome_simulation.get("completed_matches", 0)
                                total = outcome_simulation.get("total_matches", 0)
                                st.success(
                                    f"All negotiations were completed successfully! "
                                    f"Completed {completed} of {total} negotiations."
                                )
                            else:
                                st.warning(outcome_simulation)
                        else:
                            warning = st.warning("Please fill out all fields before submitting.")
                            time.sleep(1)
                            warning.empty()
                else:
                    st.write('There must be at least two submissions in order to run a simulation.')

            with sim_tabs[1]:
                saved_api_key = get_instructor_api_key(st.session_state.get('user_id'))
                use_saved_api_key = st.checkbox(
                    "Use saved API key",
                    value=bool(saved_api_key),
                    key="cc_use_saved_api_key_error",
                )
                api_key_key = "cc_api_key_error"
                if use_saved_api_key and saved_api_key:
                    if st.session_state.get(api_key_key) != saved_api_key:
                        st.session_state[api_key_key] = saved_api_key
                elif st.session_state.get(api_key_key) == saved_api_key:
                    st.session_state[api_key_key] = ""

                st.subheader('Error Chats')
                error_matchups = get_error_matchups(game_id)
                if error_matchups:
                    error_message = "The following negotiations were unsuccessful:\n\n"
                    for match in error_matchups:
                        if match[3] == 1:
                            error_message += f"- Round {match[0]} - Class{match[1][0]}_Group{match[1][1]} ({name_roles_1}) vs Class{match[2][0]}_Group{match[2][1]} ({name_roles_2});\n"
                        if match[4] == 1:
                            error_message += f"- Round {match[0]} - Class{match[2][0]}_Group{match[2][1]} ({name_roles_1}) vs Class{match[1][0]}_Group{match[1][1]} ({name_roles_2});\n"
                    st.warning(error_message)

                    with st.form(key='cc_error_form'):
                        api_key = st.text_input('API Key', type="password", key=api_key_key)
                        save_api_key = st.checkbox("Save API key", value=False, key="cc_save_api_key_error")
                        model = st.selectbox('OpenAI Model', ['gpt-4o-mini', 'gpt-4o'], key="cc_error_model")
                        submit_button = st.form_submit_button(label='Run')

                    if submit_button:
                        resolved_api_key = api_key or (saved_api_key if use_saved_api_key else "")
                        if resolved_api_key and model:
                            if save_api_key and api_key:
                                if not upsert_instructor_api_key(st.session_state.get('user_id'), api_key):
                                    st.error("Failed to save API key. Check API_KEY_ENCRYPTION_KEY.")
                            simulation_params = get_game_simulation_params(game_id)
                            if not simulation_params:
                                st.error("No simulation parameters found for this game.")
                                st.stop()

                            config_list = {"config_list": [{"model": model, "api_key": resolved_api_key}], "temperature": 0.3, "top_p": 0.5}
                            values = get_all_group_values(game_id)
                            if not values:
                                st.error("Failed to retrieve group values from database.")
                                st.stop()

                            with st.spinner("Re-running error chats..."):
                                outcome_errors_simulation = create_all_error_chats(
                                    game_id,
                                    config_list,
                                    name_roles,
                                    simulation_params["conversation_order"],
                                    values,
                                    simulation_params["starting_message"],
                                    simulation_params["num_turns"],
                                    simulation_params["negotiation_termination_message"],
                                    simulation_params["summary_prompt"],
                                    simulation_params["summary_termination_message"],
                                )
                            if outcome_errors_simulation == "All negotiations were completed successfully!":
                                st.success(outcome_errors_simulation)
                                st.rerun()
                            else:
                                st.warning(outcome_errors_simulation)
                                st.rerun()
                        else:
                            warning = st.warning("Please fill out all fields before submitting.")
                            time.sleep(1)
                            warning.empty()
                else:
                    st.write('No error chats found.')

        with overview_tabs[3]:
            game_id = selected_game['game_id']
            name_roles = selected_game['name_roles'].split('#_;:)')
            name_roles_1, name_roles_2 = name_roles[0], name_roles[1]

            round_data = get_round_data(game_id)
            has_simulation = bool(round_data)
            access_state = "Enabled" if selected_game['available'] else "Disabled"
            st.write(f"Student Access: {access_state}")
            if selected_game['available']:
                access_disabled = st.button('Disable Student Access to Negotiation Chats and Leaderboard', key="cc_disable_access")
                if access_disabled:
                    update_access_to_chats(0, selected_game['game_id'])
                    success = st.success('Student Access successfully disabled.')
                    time.sleep(1)
                    success.empty()
                    st.rerun()
            else:
                if has_simulation:
                    access_enabled = st.button('Enable Student Access to Negotiation Chats and Leaderboard', key="cc_enable_access")
                    if access_enabled:
                        update_access_to_chats(1, selected_game['game_id'])
                        success = st.success('Student Access successfully enabled.')
                        time.sleep(1)
                        success.empty()
                        st.rerun()
                else:
                    st.button(
                        'Enable Student Access to Negotiation Chats and Leaderboard',
                        key="cc_enable_access_disabled",
                        disabled=True
                    )
                    st.info("Run a simulation to publish results.")

            if round_data:
                matchups = [
                    (round_, class_1, team_1, class_2, team_2)
                    for round_, class_1, team_1, class_2, team_2, _, _, _, _ in round_data
                ]

                def render_matchups(matchups_to_show):
                    if not matchups_to_show:
                        st.write('No chats found.')
                        return
                    for round_, class_1, team_1, class_2, team_2 in matchups_to_show:
                        chat_buyer = get_negotiation_chat(game_id, round_, class_1, team_1, class_2, team_2)
                        chat_seller = get_negotiation_chat(game_id, round_, class_2, team_2, class_1, team_1)

                        header = f"Round {round_}: Class {class_1} - Group {team_1} vs Class {class_2} - Group {team_2}"
                        st.markdown(f"#### {header}")
                        with st.expander(f"**{name_roles_1} chat**"):
                            if chat_buyer:
                                st.write(chat_buyer.replace('$', '\\$'))
                            else:
                                st.write('Chat not found.')

                        with st.expander(f"**{name_roles_2} chat**"):
                            if chat_seller:
                                st.write(chat_seller.replace('$', '\\$'))
                            else:
                                st.write('Chat not found.')

                st.markdown("### Leaderboard")
                leaderboard = fetch_and_compute_scores_for_year_game(game_id)
                if leaderboard and leaderboard != False:
                    role_labels = selected_game['name_roles'].split('#_;:)')
                    role_1_label = role_labels[0]
                    role_2_label = role_labels[1]
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
                            f"Score ({role_2_label})"
                        ]
                    )
                    leaderboard_df["Avg Rounds"] = pd.to_numeric(
                        leaderboard_df["Avg Rounds"],
                        errors="coerce"
                    ).round(2)
                    leaderboard_df["Avg Score"] = leaderboard_df["Avg Score"].round(2)
                    leaderboard_df[f"Score ({role_1_label})"] = leaderboard_df[f"Score ({role_1_label})"].round(2)
                    leaderboard_df[f"Score ({role_2_label})"] = leaderboard_df[f"Score ({role_2_label})"].round(2)
                    leaderboard_df.index = leaderboard_df.index + 1

                    st.dataframe(
                        leaderboard_df.style.format(precision=2),
                        use_container_width=True,
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

                    group_options = [
                        f"Class {row['team_class']} - Group {row['team_id']}"
                        for row in leaderboard
                    ]
                    selected_group = st.selectbox("Select Group to Review Chats", group_options, key="cc_results_lb_group_select")
                    class_ = selected_group.split("Class ")[1].split(" - ")[0]
                    group_id = int(selected_group.split("Group ")[1])
                    group_matchups = [
                        m for m in matchups
                        if (m[1] == class_ and m[2] == group_id) or (m[3] == class_ and m[4] == group_id)
                    ]
                    render_matchups(group_matchups)
                else:
                    st.write("No leaderboard available.")
            else:
                st.write('No chats found.')

    with tabs[1]:
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
                key="cc_game_type"
            )

            col1, col2 = st.columns(2)
            with col1:
                name_roles_1 = st.text_input("Name of Minimizer Role", value='Buyer', key="cc_name_roles_1")
            with col2:
                name_roles_2 = st.text_input("Name of Maximizer Role", value='Seller', key="cc_name_roles_2")

            st.write('')
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                param1 = st.number_input("Lower Bound for Minimizer Reservation Value", min_value=0, step=1, value=16, key="cc_param1")
            with col2:
                param2 = st.number_input("Upper Bound for Minimizer Reservation Value", min_value=0, step=1, value=25, key="cc_param2")
            with col3:
                param3 = st.number_input("Lower Bound for Maximizer Reservation Value", min_value=0, step=1, value=7, key="cc_param3")
            with col4:
                param4 = st.number_input(
                    "Upper Bound for Maximizer Reservation Value",
                    min_value=0,
                    step=1,
                    value=15,
                    key="cc_param4",
                    help='All values are expressed in the unit mentioned in description.'
                )

            selected_combination = st.selectbox(
                "Select Academic Year and Class",
                options=combination_options,
                key="cc_academic_year_class_combination",
            )
            game_academic_year, game_class = parse_year_class(selected_combination)

            password = st.text_input("Game Password (4-digit)", max_chars=4, key="cc_password")

            default_date = datetime.today().date() + timedelta(weeks=1)
            default_time = datetime.strptime("23:59", "%H:%M").time()
            deadline_date = st.date_input("Submission Deadline Date", value=default_date, key="cc_deadline_date")
            deadline_time = st.time_input("Submission Deadline Time", value=default_time, key="cc_deadline_time")

            submit_button = st.form_submit_button("Create Game")

        if submit_button and not st.session_state.cc_game_creation_in_progress:
            st.session_state.cc_game_creation_in_progress = True
            if game_name and game_explanation and name_roles_1 and name_roles_2 and selected_combination and \
                param1 and param2 and param3 and param4 and password and deadline_date and deadline_time:
                creation_success = False
                try:
                    user_id = st.session_state.get('user_id')
                    next_game_id = get_next_game_id()
                    timestamp_game_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    submission_deadline = datetime.combine(deadline_date, deadline_time)
                    name_roles = name_roles_1 + '#_;:)' + name_roles_2

                    store_game_in_db(
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
                        game_type
                    )

                    if not populate_plays_table(next_game_id, game_academic_year, game_class):
                        st.error("An error occurred while assigning students to the game.")
                        st.stop()

                    different_groups_classes = get_group_ids_from_game_id(next_game_id)
                    if different_groups_classes is False:
                        st.error("An error occurred while retrieving group information.")
                        st.stop()
                    elif not different_groups_classes:
                        st.error("No eligible students found for this game.")
                        st.stop()

                    if not store_game_parameters(next_game_id, param1, param2, param3, param4):
                        st.error("Failed to store game parameters.")
                        st.stop()

                    for i in different_groups_classes:
                        buy_value = int(random.uniform(param1, param2))
                        sell_value = int(random.uniform(param3, param4))
                        if not store_group_values(next_game_id, i[0], i[1], buy_value, sell_value):
                            st.error(f"Failed to store values for group {i[0]}-{i[1]}.")
                            st.stop()

                    creation_success = True
                except Exception:
                    st.error("An error occurred. Please try again.")
                finally:
                    st.session_state.cc_game_creation_in_progress = False

                if creation_success:
                    st.session_state.cc_game_created = True
                    st.session_state.cc_pending_selected_year = game_academic_year
                    if game_class != "_":
                        st.session_state.cc_pending_selected_game = f"{game_name} - Class {game_class}"
                    else:
                        st.session_state.cc_pending_selected_game = game_name
                    st.rerun()
            else:
                st.warning("Please fill out all fields before submitting.")
                st.session_state.cc_game_creation_in_progress = False

    with tabs[2]:
        st.subheader("Student Management")

        def show_cc_student_table():
            students_from_db = get_students_from_db()
            students_display = students_from_db.rename(columns={
                "user_id": "User ID",
                "email": "Email",
                "group_id": "Group ID",
                "academic_year": "Academic Year",
                "class": "Class",
                "timestamp_user": "Created at"
            })

            st.session_state.cc_students = students_display
            students_display[""] = ""

            gb = GridOptionsBuilder.from_dataframe(
                students_display[["", "User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]]
            )
            gb.configure_column("", checkboxSelection=True, width=60)
            gb.configure_column("User ID", width=120)
            gb.configure_column("Email", width=140)
            gb.configure_column("Group ID", width=120)
            gb.configure_column("Academic Year", width=140)
            gb.configure_column("Class", width=80)
            gb.configure_column("Created at", width=130)
            gb.configure_selection('single')
            grid_options = gb.build()

            data = AgGrid(
                students_display[["", "User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]],
                gridOptions=grid_options,
                fit_columns_on_grid_load=True,
                height=min(36 + 27 * students_display.shape[0], 300),
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS
            )
            return data

        data = show_cc_student_table()
        st.session_state.cc_selected_student = data["selected_rows"]

        _, col1, col2, col3 = st.columns([1, 1, 1, 2])

        with col1:
            if st.button("Add Students", key="cc_add_students_via_csv"):
                st.session_state.cc_add_students = True
                st.session_state.cc_add_student = False
                st.session_state.cc_remove_student = False
        with col2:
            if st.button("Add Student", key="cc_add_student_manually"):
                st.session_state.cc_add_student = True
                st.session_state.cc_add_students = False
                st.session_state.cc_remove_student = False
        with col3:
            if st.button("Remove Student", key="cc_remove_student_manually"):
                st.session_state.cc_remove_student = True
                st.session_state.cc_add_student = False
                st.session_state.cc_add_students = False

        if st.session_state.cc_add_students:
            with st.form("cc_add_students_form"):
                uploaded_file = st.file_uploader("Upload CSV with all the Students", type=["csv"], key="cc_upload_csv")
                submit_button = st.form_submit_button("Add Students")

                if submit_button:
                    if uploaded_file is not None:
                        success, message = process_student_csv(uploaded_file)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.error("Please upload a valid CSV file.")
                    st.session_state.cc_add_students = False
                    st.rerun()

        if st.session_state.cc_add_student:
            with st.form("cc_add_student_form"):
                user_id = st.text_input("Introduce User ID:", key="cc_user_id")
                email = st.text_input("Introduce Email:", key="cc_email")
                group_id = st.text_input("Introduce the Group ID:", key="cc_group_id")
                academic_year = st.text_input("Introduce academic year:", key="cc_academic_year")
                class_ = st.text_input("Introduce class:", key="cc_class")

                submit_button = st.form_submit_button("Add Student")

                if submit_button:
                    if not user_id or not email or not group_id or not academic_year or not class_:
                        st.error("Please fill in all fields.")
                    else:
                        if insert_student_data(user_id, email, "Not defined", group_id, academic_year, class_):
                            st.success("Student added successfully!")
                        else:
                            st.error("Failed to add student. Please try again.")
                        st.session_state.cc_add_student = False
                        st.rerun()

        if st.session_state.cc_remove_student:
            if st.session_state.cc_students.empty:
                st.warning("No students found. Please add a student.")
            else:
                if st.session_state.cc_selected_student is not None:
                    if len(st.session_state.cc_selected_student) != 0:
                        if isinstance(st.session_state.cc_selected_student, pd.DataFrame):
                            user_id = st.session_state.cc_selected_student['User ID'].tolist()[0]
                        else:
                            user_id = st.session_state.cc_selected_student[0]['User ID']

                        if remove_student(user_id):
                            st.success("Student removed successfully!")
                            st.session_state.cc_students = st.session_state.cc_students[
                                st.session_state.cc_students["User ID"] != user_id
                            ]
                        else:
                            st.error("Failed to remove student. Please try again.")
                else:
                    st.warning("Please select a student to remove.")
            st.session_state.cc_remove_student = False
            st.rerun()

# -------------------------------------------------------------------------------------------------------- #

st.set_page_config("Control Panel")

# Record page entry
if 'authenticated' in st.session_state and st.session_state['authenticated']:
    record_page_entry(st.session_state.get('user_id', 'anonymous'), 'Control Panel')

# Check if the user is authenticated
if st.session_state['authenticated']:

    if st.session_state['instructor']:
        render_control_center()
    else:
        st.title("Control Panel")
        st.write('Page accessible only to Instructors.')

    # Record page exit
    if 'authenticated' in st.session_state and st.session_state['authenticated']:
        record_page_exit('Control Panel')

else:
    st.title("Control Panel")
    st.write('Please Login first. (Page accessible only to Instructors)')
