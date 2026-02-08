import time

import streamlit as st

from ..control_panel_ui_helpers import (
    calculate_planned_chats,
    format_progress_caption,
    format_progress_status_line,
)
from ..database_handler import (
    delete_from_round,
    delete_negotiation_chats,
    get_all_group_values,
    get_error_matchups,
    get_game_simulation_params,
    get_group_ids_from_game_id,
    get_student_prompt,
    get_user_api_key,
    list_user_api_keys,
    update_num_rounds_game,
    upsert_game_simulation_params,
)
from ..llm_models import MODEL_EXPLANATIONS, MODEL_OPTIONS
from ..negotiations import (
    build_llm_config,
    create_all_error_chats,
    create_chats,
    is_invalid_api_key_error,
)


def render_simulation_tab(selected_game: dict) -> None:
    game_id = selected_game["game_id"]
    name_roles = selected_game["name_roles"].split("#_;:)")
    name_roles_1, name_roles_2 = name_roles[0], name_roles[1]

    sim_tabs = st.tabs(["Run Simulation", "Error Chats"])
    with sim_tabs[0]:
        saved_keys = list_user_api_keys(st.session_state.get("user_id"))
        key_options = {key["key_name"]: key["key_id"] for key in saved_keys}
        has_keys = bool(key_options)
        if not key_options:
            st.info("No API keys saved. Add one in Profile to run simulations.")

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
        model_options = MODEL_OPTIONS
        model_explanations = MODEL_EXPLANATIONS
        default_model = simulation_params["model"] if simulation_params else "gpt-5-mini"
        default_num_turns = simulation_params["num_turns"] if simulation_params else 15
        default_negotiation_termination = (
            simulation_params["negotiation_termination_message"]
            if simulation_params
            else "Pleasure doing business with you"
        )
        default_summary_prompt = (
            simulation_params["summary_prompt"] if simulation_params else "What was the value agreed?"
        )
        default_summary_termination = (
            simulation_params["summary_termination_message"] if simulation_params else "Agreed value:"
        )
        default_conversation_starter = simulation_params["conversation_order"] if simulation_params else name_roles_1
        conversation_options = [f"{name_roles_1} ➡ {name_roles_2}", f"{name_roles_2} ➡ {name_roles_1}"]
        if default_conversation_starter == "same":
            default_conversation_starter = name_roles_1
        elif default_conversation_starter == "opposite":
            default_conversation_starter = name_roles_2
        elif default_conversation_starter not in (name_roles_1, name_roles_2):
            default_conversation_starter = name_roles_1
        default_order_index = 0 if default_conversation_starter == name_roles_1 else 1

        if len(teams) >= 2:
            st.warning(
                "Attention: Running a new simulation will erase all previous data related to the game. "
                "This includes all group chats and all group scores."
            )
            with st.form(key="cc_simulation_form"):
                selected_key_id = None
                if key_options:
                    selected_label = st.selectbox(
                        "API Key",
                        options=list(key_options.keys()),
                        key="cc_api_key_select_sim",
                    )
                    selected_key_id = key_options[selected_label]
                model = st.selectbox(
                    "OpenAI Model",
                    model_options,
                    index=model_options.index(default_model) if default_model in model_options else 0,
                    format_func=lambda name: f"{name} — {model_explanations.get(name, '')}",
                    help="Model descriptions are shown in the dropdown. Pick the best balance of cost and quality.",
                    key="cc_model",
                )
                max_opponents = max(len(teams) - 1, 1)
                opponents_per_team = st.number_input(
                    "Opponents per Team",
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
                    "Conversation Starter",
                    conversation_options,
                    horizontal=True,
                    index=default_order_index,
                    key="cc_conversation_starter",
                )
                num_turns = st.number_input(
                    "Maximum Number of Turns",
                    step=1,
                    min_value=1,
                    value=int(default_num_turns),
                    key="cc_num_turns",
                )
                negotiation_termination_message = st.text_input(
                    "Negotiation Termination Message",
                    value=default_negotiation_termination,
                    key="cc_negotiation_termination_message",
                )
                summary_prompt = st.text_input(
                    "Negotiation Summary Prompt", value=default_summary_prompt, key="cc_summary_prompt"
                )
                summary_termination_message = st.text_input(
                    "Summary Termination Message",
                    value=default_summary_termination,
                    key="cc_summary_termination_message",
                )

                submit_button = st.form_submit_button(label="Run", disabled=not has_keys)

            if submit_button:
                resolved_api_key = None
                if selected_key_id:
                    resolved_api_key = get_user_api_key(st.session_state.get("user_id"), selected_key_id)

                if not resolved_api_key:
                    st.error("Please select a saved API key to run the simulation.")
                elif (
                    resolved_api_key
                    and model
                    and opponents_per_team
                    and conversation_starter
                    and num_turns
                    and negotiation_termination_message
                    and summary_prompt
                    and summary_termination_message
                ):
                    status_placeholder = st.empty()
                    delete_from_round(game_id)
                    delete_negotiation_chats(game_id)

                    initiator_role = conversation_starter.split(" ➡ ")[0].strip()
                    upsert_game_simulation_params(
                        game_id=game_id,
                        model=model,
                        conversation_order=initiator_role,
                        starting_message="",
                        num_turns=num_turns,
                        negotiation_termination_message=negotiation_termination_message,
                        summary_prompt=summary_prompt,
                        summary_termination_message=summary_termination_message,
                    )

                    update_num_rounds_game(rounds_to_run, game_id)

                    config_list = build_llm_config(model, resolved_api_key)
                    values = get_all_group_values(game_id)
                    if not values:
                        st.error("Failed to retrieve group values from database.")
                        st.stop()

                    progress_header = st.empty()
                    progress_placeholder = st.empty()
                    progress_bar = st.empty()
                    progress_caption = st.empty()
                    total_matches = calculate_planned_chats(len(teams), rounds_to_run)

                    progress_header.markdown("### Simulation Progress")
                    progress_bar = st.progress(0)
                    progress_caption.caption(
                        f"Planned chats: {total_matches} | Rounds: {rounds_to_run} | Teams: {len(teams)}"
                    )

                    def update_progress(
                        round_num,
                        team1,
                        team2,
                        role1_name,
                        role2_name,
                        completed_matches,
                        total_matches,
                        phase,
                        attempt=None,
                        elapsed_seconds=None,
                    ):
                        visual_completed = completed_matches
                        if phase in {"running", "retrying"} and total_matches:
                            # Show partial progress while a blocking chat call is in flight.
                            visual_completed = min(completed_matches + 0.5, total_matches)

                        if total_matches:
                            progress_bar.progress(min(visual_completed / total_matches, 1.0))

                        progress_placeholder.info(
                            format_progress_status_line(
                                round_num,
                                team1["Name"],
                                team2["Name"],
                                role1_name,
                                role2_name,
                                phase,
                                attempt=attempt,
                                elapsed_seconds=elapsed_seconds,
                            )
                        )
                        progress_caption.caption(format_progress_caption(completed_matches, total_matches, phase))

                    with st.spinner("Running negotiations..."):
                        try:
                            outcome_simulation = create_chats(
                                game_id,
                                config_list,
                                name_roles,
                                initiator_role,
                                teams,
                                values,
                                rounds_to_run,
                                num_turns,
                                negotiation_termination_message,
                                summary_prompt,
                                summary_termination_message,
                                progress_callback=update_progress,
                            )
                        except Exception as e:
                            progress_placeholder.empty()
                            progress_bar.empty()
                            progress_caption.empty()
                            progress_header.empty()
                            status_placeholder.empty()
                            if is_invalid_api_key_error(e):
                                st.error(
                                    "Your API key appears invalid or unauthorized. Update it in Profile and try again."
                                )
                            else:
                                st.error(f"Simulation failed: {str(e)}")
                            st.stop()
                    progress_placeholder.empty()
                    progress_bar.empty()
                    progress_caption.empty()
                    progress_header.empty()
                    status_placeholder.empty()
                    if isinstance(outcome_simulation, dict) and outcome_simulation.get("status") == "success":
                        completed = outcome_simulation.get("completed_matches", 0)
                        processed = outcome_simulation.get("processed_matches", completed)
                        total = outcome_simulation.get("total_matches", 0)
                        st.success(
                            f"All negotiations were completed successfully! "
                            f"Successful: {completed} | Processed: {processed} of {total} chats."
                        )
                    elif isinstance(outcome_simulation, dict):
                        completed = outcome_simulation.get("completed_matches", 0)
                        processed = outcome_simulation.get("processed_matches", 0)
                        total = outcome_simulation.get("total_matches", 0)
                        st.warning(
                            f"Simulation completed with errors. Successful: {completed} | "
                            f"Processed: {processed} of {total} chats."
                        )
                        st.warning(outcome_simulation.get("message", "Some negotiations were unsuccessful."))
                    else:
                        st.warning(str(outcome_simulation))

                    if isinstance(outcome_simulation, dict):
                        timing = outcome_simulation.get("timing", {})
                        st.caption(
                            "Timing diagnostics (seconds per chat avg): "
                            f"Negotiation={timing.get('chat_seconds_avg', 0):.2f}, "
                            f"Summary={timing.get('summary_seconds_avg', 0):.2f}, "
                            f"DB={timing.get('db_seconds_avg', 0):.2f}"
                        )
                        diagnostics = outcome_simulation.get("diagnostics", {})
                        st.caption(
                            "Run diagnostics: "
                            f"attempts={diagnostics.get('attempts_total', 0)}, "
                            f"retries={diagnostics.get('retries_used', 0)}, "
                            f"failed_attempts={diagnostics.get('attempts_failed', 0)}, "
                            f"summary_calls={diagnostics.get('summary_calls', 0)}, "
                            f"avg_turns/successful_chat={diagnostics.get('avg_turns_per_successful_chat', 0):.2f}"
                        )
                else:
                    warning = st.warning("Please fill out all fields before submitting.")
                    time.sleep(1)
                    warning.empty()
        else:
            st.write("There must be at least two submissions in order to run a simulation.")

    with sim_tabs[1]:
        saved_keys = list_user_api_keys(st.session_state.get("user_id"))
        key_options = {key["key_name"]: key["key_id"] for key in saved_keys}
        has_keys = bool(key_options)
        if not key_options:
            st.info("No API keys saved. Add one in Profile to re-run error chats.")

        st.subheader("Error Chats")
        error_matchups = get_error_matchups(game_id)
        if error_matchups:
            error_message = "The following negotiations were unsuccessful:\n\n"
            for match in error_matchups:
                if match[3] == 1:
                    error_message += f"- Round {match[0]} - Class{match[1][0]}_Group{match[1][1]} ({name_roles_1}) vs Class{match[2][0]}_Group{match[2][1]} ({name_roles_2});\n"
                if match[4] == 1:
                    error_message += f"- Round {match[0]} - Class{match[2][0]}_Group{match[2][1]} ({name_roles_1}) vs Class{match[1][0]}_Group{match[1][1]} ({name_roles_2});\n"
            st.warning(error_message)

            with st.form(key="cc_error_form"):
                selected_key_id = None
                if key_options:
                    selected_label = st.selectbox(
                        "API Key",
                        options=list(key_options.keys()),
                        key="cc_api_key_select_error",
                    )
                    selected_key_id = key_options[selected_label]
                model = st.selectbox(
                    "OpenAI Model",
                    model_options,
                    index=model_options.index(default_model) if default_model in model_options else 0,
                    format_func=lambda name: f"{name} — {model_explanations.get(name, '')}",
                    help="Model descriptions are shown in the dropdown. Pick the best balance of cost and quality.",
                    key="cc_error_model",
                )
                submit_button = st.form_submit_button(label="Run", disabled=not has_keys)

            if submit_button:
                resolved_api_key = None
                if selected_key_id:
                    resolved_api_key = get_user_api_key(st.session_state.get("user_id"), selected_key_id)
                if not resolved_api_key:
                    st.error("Please select a saved API key to re-run error chats.")
                elif resolved_api_key and model:
                    simulation_params = get_game_simulation_params(game_id)
                    if not simulation_params:
                        st.error("No simulation parameters found for this game.")
                        st.stop()

                    config_list = build_llm_config(model, resolved_api_key)
                    values = get_all_group_values(game_id)
                    if not values:
                        st.error("Failed to retrieve group values from database.")
                        st.stop()

                    with st.spinner("Re-running error chats..."):
                        try:
                            outcome_errors_simulation = create_all_error_chats(
                                game_id,
                                config_list,
                                name_roles,
                                simulation_params["conversation_order"],
                                values,
                                simulation_params["num_turns"],
                                simulation_params["negotiation_termination_message"],
                                simulation_params["summary_prompt"],
                                simulation_params["summary_termination_message"],
                            )
                        except Exception as e:
                            if is_invalid_api_key_error(e):
                                st.error(
                                    "Your API key appears invalid or unauthorized. Update it in Profile and try again."
                                )
                            else:
                                st.error(f"Error chat run failed: {str(e)}")
                            st.stop()
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
            st.write("No error chats found.")
