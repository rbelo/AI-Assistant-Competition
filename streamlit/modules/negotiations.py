import time

from .conversation_engine import ConversationEngine
from .database_handler import (
    get_error_matchups,
    get_game_by_id,
    insert_negotiation_chat,
    insert_round_data,
    update_round_data,
)
from .negotiations_agents import create_agents
from .negotiations_common import (
    build_llm_config,
    clean_agent_message,
    compute_deal_scores,
    get_maximizer_reservation,
    get_minimizer_maximizer,
    get_minimizer_reservation,
    get_role_agent,
    is_invalid_api_key_error,
    is_valid_termination,
    parse_team_name,
    resolve_initiator_role_index,
)
from .negotiations_run_helpers import (
    build_diagnostics_summary,
    build_timing_summary,
    format_unsuccessful_matchups,
)
from .negotiations_summary import (
    _build_summary_context,
    _extract_summary_text,
    build_summary_agent,
    evaluate_deal_summary,
    extract_summary_from_transcript,
    parse_deal_value,
)
from .schedule import berger_schedule

__all__ = [
    "_build_summary_context",
    "_extract_summary_text",
    "build_llm_config",
    "build_summary_agent",
    "clean_agent_message",
    "compute_deal_scores",
    "create_agents",
    "create_all_error_chats",
    "create_chat",
    "create_chats",
    "evaluate_deal_summary",
    "extract_summary_from_transcript",
    "get_maximizer_reservation",
    "get_minimizer_maximizer",
    "get_minimizer_reservation",
    "get_role_agent",
    "is_invalid_api_key_error",
    "is_valid_termination",
    "parse_deal_value",
    "parse_team_name",
    "resolve_initiator_role_index",
]


def _make_termination_fn(negotiation_termination_message):
    """Return a termination predicate that fires when the phrase appears."""
    def fn(msg, history):
        return negotiation_termination_message in msg["content"]
    return fn


def create_chat(
    game_id,
    minimizer_team,
    maximizer_team,
    initiator_role_index,
    num_turns,
    summary_prompt,
    round_num,
    engine,
    summary_agent,
    summary_termination_message,
    negotiation_termination_message,
    store_in_db=True,
    game_type="zero-sum",
    timing_totals=None,
    run_diagnostics=None,
):
    game_details = get_game_by_id(game_id)
    game_explanation = game_details.get("explanation", "") if game_details else ""
    game_context = f"Game Type: {game_type}\nGame Explanation: {game_explanation}\n\n"

    responder_role_index = 2 if initiator_role_index == 1 else 1
    initiator_team, responder_team = (
        (minimizer_team, maximizer_team) if initiator_role_index == 1 else (maximizer_team, minimizer_team)
    )

    agent1 = get_role_agent(initiator_team, initiator_role_index)
    agent2 = get_role_agent(responder_team, responder_role_index)
    name1 = agent1.name
    name2 = agent2.name

    if agent1.system_message:
        agent1.system_message = game_context + agent1.system_message
    if agent2.system_message:
        agent2.system_message = game_context + agent2.system_message

    termination_fn = _make_termination_fn(negotiation_termination_message)

    chat_start = time.perf_counter()
    chat = engine.run_bilateral(agent1, agent2, num_turns, termination_fn)
    chat_elapsed = time.perf_counter() - chat_start

    negotiation = ""
    turn_count = len(chat.chat_history) if getattr(chat, "chat_history", None) else 0

    for entry in chat.chat_history:
        clean_msg = clean_agent_message(name1, name2, entry["content"])
        negotiation += f"{entry['name']}: {clean_msg}\n\n\n"

    summary_text = ""
    deal_value = -1
    summary_elapsed = 0.0
    if summary_agent:
        summary_start = time.perf_counter()
        summary_text, deal_value = evaluate_deal_summary(
            engine,
            chat.chat_history,
            summary_prompt,
            summary_termination_message,
            summary_agent,
            role1_name=name1,
            role2_name=name2,
            history_size=4,
        )
        summary_elapsed = time.perf_counter() - summary_start

    db_elapsed = 0.0
    if store_in_db and minimizer_team and maximizer_team and game_id and round_num is not None:
        class1, group1 = parse_team_name(minimizer_team["Name"])
        class2, group2 = parse_team_name(maximizer_team["Name"])
        if class1 and group1 is not None and class2 and group2 is not None:
            try:
                db_start = time.perf_counter()
                insert_negotiation_chat(
                    game_id=game_id,
                    round_number=round_num,
                    group1_class=class1,
                    group1_id=group1,
                    group2_class=class2,
                    group2_id=group2,
                    transcript=negotiation,
                    summary=summary_text,
                    deal_value=deal_value,
                )
                db_elapsed = time.perf_counter() - db_start
            except Exception as e:
                print(f"Warning: Failed to store negotiation chat: {e}")

    if timing_totals is not None:
        timing_totals["chat_seconds"] += chat_elapsed
        timing_totals["summary_seconds"] += summary_elapsed
        timing_totals["db_seconds"] += db_elapsed
        timing_totals["chats_measured"] += 1

    if run_diagnostics is not None:
        run_diagnostics["total_turns"] += turn_count
        run_diagnostics["summary_calls"] += 1 if summary_agent else 0
        run_diagnostics["successful_chats"] += 1

    return deal_value


def create_chats(
    game_id,
    llm_config,
    name_roles,
    conversation_order,
    teams,
    values,
    num_rounds,
    num_turns,
    negotiation_termination_message,
    summary_prompt,
    summary_termination_message,
    progress_callback=None,
):
    schedule = berger_schedule([f"Class{i[0]}_Group{i[1]}" for i in teams], num_rounds)

    engine = ConversationEngine(llm_config)
    team_info = create_agents(game_id, teams, values, name_roles, negotiation_termination_message)
    initiator_role_index = resolve_initiator_role_index(name_roles, conversation_order)
    initiator_role_name = name_roles[initiator_role_index - 1]
    responder_role_name = name_roles[1 if initiator_role_index == 1 else 0]

    summary_agent = build_summary_agent(
        summary_termination_message,
        negotiation_termination_message,
        include_summary=True,
    )

    max_retries = 10
    total_matches = sum(len(round_matches) * 2 for round_matches in schedule)
    completed_matches = 0
    processed_matches = 0
    timing_totals = {
        "chat_seconds": 0.0,
        "summary_seconds": 0.0,
        "db_seconds": 0.0,
        "chats_measured": 0,
    }
    run_diagnostics = {
        "attempts_total": 0,
        "attempts_failed": 0,
        "summary_calls": 0,
        "total_turns": 0,
        "successful_chats": 0,
    }

    def emit_progress(round_num, team1, team2, role1_name, role2_name, phase, attempt=None, elapsed_seconds=None):
        if progress_callback:
            progress_callback(
                round_num=round_num,
                team1=team1,
                team2=team2,
                role1_name=role1_name,
                role2_name=role2_name,
                completed_matches=processed_matches,
                total_matches=total_matches,
                phase=phase,
                attempt=attempt,
                elapsed_seconds=elapsed_seconds,
            )

    errors_matchups = []

    for round_, round_matches in enumerate(schedule, 1):
        for match in round_matches:
            team1 = next((team for team in team_info if team["Name"] == match[0]), None)
            team2 = next((team for team in team_info if team["Name"] == match[1]), None)

            class_group_1 = team1["Name"].split("_")
            class1 = class_group_1[0][5:]
            group1 = class_group_1[1][5:]

            class_group_2 = team2["Name"].split("_")
            class2 = class_group_2[0][5:]
            group2 = class_group_2[1][5:]

            insert_round_data(game_id, round_, class1, group1, class2, group2, None, None, None, None)

            first_chat_success = False
            for attempt in range(max_retries):
                attempt_start = time.perf_counter()
                try:
                    run_diagnostics["attempts_total"] += 1
                    emit_progress(
                        round_, team1, team2, initiator_role_name, responder_role_name, "running", attempt + 1
                    )

                    minimizer_team, maximizer_team = get_minimizer_maximizer(team1, team2, initiator_role_index)
                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        num_turns,
                        summary_prompt,
                        round_,
                        engine,
                        summary_agent,
                        summary_termination_message,
                        negotiation_termination_message,
                        timing_totals=timing_totals,
                        run_diagnostics=run_diagnostics,
                    )
                    score_maximizer, score_minimizer = compute_deal_scores(
                        deal,
                        get_maximizer_reservation(maximizer_team),
                        get_minimizer_reservation(minimizer_team),
                    )

                    if minimizer_team is team1:
                        score_team1, score_team2 = score_minimizer, score_maximizer
                        team1_role_index, team2_role_index = 1, 2
                    else:
                        score_team1, score_team2 = score_maximizer, score_minimizer
                        team1_role_index, team2_role_index = 2, 1

                    update_round_data(
                        game_id,
                        round_,
                        class1,
                        group1,
                        class2,
                        group2,
                        score_team1,
                        score_team2,
                        team1_role_index,
                        team2_role_index,
                    )
                    completed_matches += 1
                    first_chat_success = True
                    break

                except Exception:
                    run_diagnostics["attempts_failed"] += 1
                    elapsed = round(time.perf_counter() - attempt_start, 2)
                    emit_progress(
                        round_,
                        team1,
                        team2,
                        initiator_role_name,
                        responder_role_name,
                        "retrying",
                        attempt + 1,
                        elapsed_seconds=elapsed,
                    )
                    if attempt == max_retries - 1:
                        errors_matchups.append((round_, team1["Name"], team2["Name"]))

            elapsed = round(time.perf_counter() - attempt_start, 2)
            processed_matches += 1
            emit_progress(
                round_,
                team1,
                team2,
                initiator_role_name,
                responder_role_name,
                "completed" if first_chat_success else "failed",
                elapsed_seconds=elapsed,
            )

            second_chat_success = False
            for attempt in range(max_retries):
                attempt_start = time.perf_counter()
                try:
                    run_diagnostics["attempts_total"] += 1
                    emit_progress(
                        round_, team2, team1, initiator_role_name, responder_role_name, "running", attempt + 1
                    )

                    minimizer_team, maximizer_team = get_minimizer_maximizer(team2, team1, initiator_role_index)
                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        num_turns,
                        summary_prompt,
                        round_,
                        engine,
                        summary_agent,
                        summary_termination_message,
                        negotiation_termination_message,
                        timing_totals=timing_totals,
                        run_diagnostics=run_diagnostics,
                    )
                    score_maximizer, score_minimizer = compute_deal_scores(
                        deal,
                        get_maximizer_reservation(maximizer_team),
                        get_minimizer_reservation(minimizer_team),
                    )

                    if minimizer_team is team1:
                        score_team1, score_team2 = score_minimizer, score_maximizer
                        team1_role_index, team2_role_index = 1, 2
                    else:
                        score_team1, score_team2 = score_maximizer, score_minimizer
                        team1_role_index, team2_role_index = 2, 1

                    update_round_data(
                        game_id,
                        round_,
                        class1,
                        group1,
                        class2,
                        group2,
                        score_team1,
                        score_team2,
                        team1_role_index,
                        team2_role_index,
                    )
                    completed_matches += 1
                    second_chat_success = True
                    break

                except Exception:
                    run_diagnostics["attempts_failed"] += 1
                    elapsed = round(time.perf_counter() - attempt_start, 2)
                    emit_progress(
                        round_,
                        team2,
                        team1,
                        initiator_role_name,
                        responder_role_name,
                        "retrying",
                        attempt + 1,
                        elapsed_seconds=elapsed,
                    )
                    if attempt == max_retries - 1:
                        errors_matchups.append((round_, team2["Name"], team1["Name"]))

            elapsed = round(time.perf_counter() - attempt_start, 2)
            processed_matches += 1
            emit_progress(
                round_,
                team2,
                team1,
                initiator_role_name,
                responder_role_name,
                "completed" if second_chat_success else "failed",
                elapsed_seconds=elapsed,
            )

    timing_summary = build_timing_summary(timing_totals)
    diag_summary = build_diagnostics_summary(run_diagnostics, processed_matches)

    if not errors_matchups:
        return {
            "status": "success",
            "completed_matches": completed_matches,
            "processed_matches": processed_matches,
            "total_matches": total_matches,
            "timing": timing_summary,
            "diagnostics": diag_summary,
        }

    return {
        "status": "partial",
        "completed_matches": completed_matches,
        "processed_matches": processed_matches,
        "total_matches": total_matches,
        "errors": errors_matchups,
        "message": format_unsuccessful_matchups(errors_matchups, name_roles),
        "timing": timing_summary,
        "diagnostics": diag_summary,
    }


def create_all_error_chats(
    game_id,
    llm_config,
    name_roles,
    conversation_order,
    values,
    num_turns,
    negotiation_termination_message,
    summary_prompt,
    summary_termination_message,
):
    matches = get_error_matchups(game_id)

    teams1 = [i[1] for i in matches]
    teams2 = [i[2] for i in matches]

    unique_teams = {tuple(item) for item in (teams1 + teams2)}
    teams = [list(team) for team in unique_teams]

    engine = ConversationEngine(llm_config)
    team_info = create_agents(game_id, teams, values, name_roles, negotiation_termination_message)
    initiator_role_index = resolve_initiator_role_index(name_roles, conversation_order)
    summary_agent = build_summary_agent(
        summary_termination_message,
        negotiation_termination_message,
        include_summary=True,
    )

    max_retries = 10
    errors_matchups = []

    for match in matches:
        team1 = next((team for team in team_info if team["Name"] == f"Class{match[1][0]}_Group{match[1][1]}"), None)
        team2 = next((team for team in team_info if team["Name"] == f"Class{match[2][0]}_Group{match[2][1]}"), None)

        if team1 is None or team2 is None:
            print(f"Warning: Could not find team1 or team2 for match {match}")
            continue

        if match[3] == 1:
            minimizer_team = team1
            maximizer_team = team2

            for attempt in range(max_retries):
                try:
                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        num_turns,
                        summary_prompt,
                        match[0],
                        engine,
                        summary_agent,
                        summary_termination_message,
                        negotiation_termination_message,
                    )
                    score_maximizer, score_minimizer = compute_deal_scores(
                        deal,
                        get_maximizer_reservation(maximizer_team),
                        get_minimizer_reservation(minimizer_team),
                    )

                    update_round_data(
                        game_id,
                        match[0],
                        match[1][0],
                        match[1][1],
                        match[2][0],
                        match[2][1],
                        score_minimizer,
                        score_maximizer,
                        1,
                        2,
                    )

                    break

                except Exception:
                    if attempt == max_retries - 1:
                        errors_matchups.append((match[0], minimizer_team["Name"], maximizer_team["Name"]))

        if match[4] == 1:
            minimizer_team = team2
            maximizer_team = team1

            for attempt in range(max_retries):
                try:
                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        num_turns,
                        summary_prompt,
                        match[0],
                        engine,
                        summary_agent,
                        summary_termination_message,
                        negotiation_termination_message,
                    )
                    score_maximizer, score_minimizer = compute_deal_scores(
                        deal,
                        get_maximizer_reservation(maximizer_team),
                        get_minimizer_reservation(minimizer_team),
                    )

                    update_round_data(
                        game_id,
                        match[0],
                        match[1][0],
                        match[1][1],
                        match[2][0],
                        match[2][1],
                        score_maximizer,
                        score_minimizer,
                        2,
                        1,
                    )

                    break

                except Exception:
                    if attempt == max_retries - 1:
                        errors_matchups.append((match[0], minimizer_team["Name"], maximizer_team["Name"]))

    if not errors_matchups:
        return "All negotiations were completed successfully!"

    return format_unsuccessful_matchups(errors_matchups, name_roles)
