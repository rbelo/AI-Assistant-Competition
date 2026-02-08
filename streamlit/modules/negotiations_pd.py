"""Prisoner's Dilemma with cheap-talk negotiation.

Three-phase game flow
---------------------
1. **Cheap talk** -- agents negotiate openly via ``run_bilateral``.
   Promises, threats, and signals are allowed but *not* binding.
2. **Private decision** -- each agent independently submits
   ``cooperate`` or ``defect`` via ``single_decision``.  The other
   agent never sees this message.
3. **Scoring** -- the payoff matrix resolves the outcome.
"""

import time

from .conversation_engine import ConversationEngine, GameAgent
from .database_handler import (
    get_game_by_id,
    get_student_prompt,
    insert_negotiation_chat,
    insert_round_data,
    update_round_data,
)
from .negotiations_common import (
    DEFAULT_PD_PAYOFF_MATRIX,
    PD_DECISION_KEYWORD,
    build_llm_config,
    clean_agent_message,
    compute_pd_scores,
    parse_pd_action,
    parse_team_name,
)
from .negotiations_run_helpers import (
    build_diagnostics_summary,
    build_timing_summary,
    format_unsuccessful_matchups,
)
from .schedule import berger_schedule


# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------

def _build_pd_system_message(
    student_prompt,
    payoff_matrix,
    private_value=None,
    negotiation_termination_message="DONE",
    words=50,
):
    """Build the system prompt for a PD agent.

    The payoff matrix is presented from a first-person perspective
    (works correctly for symmetric matrices -- the standard PD case).
    """
    m = payoff_matrix
    matrix_text = (
        "Payoff matrix (your score, opponent's score):\n"
        f"  Both cooperate:              ({m['cooperate_cooperate'][0]}, {m['cooperate_cooperate'][1]})\n"
        f"  You cooperate, they defect:  ({m['cooperate_defect'][0]}, {m['cooperate_defect'][1]})\n"
        f"  You defect, they cooperate:  ({m['defect_cooperate'][0]}, {m['defect_cooperate'][1]})\n"
        f"  Both defect:                 ({m['defect_defect'][0]}, {m['defect_defect'][1]})"
    )

    private_info = ""
    if private_value is not None:
        private_info = (
            f"\n\nPRIVATE INFORMATION (only you know this): "
            f"Your private value is {private_value}. "
            f"This is information only you have access to -- "
            f"the other player does not know this."
        )

    return (
        f"{student_prompt}\n\n"
        f"You are playing a Prisoner's Dilemma game with two phases:\n"
        f"1. NEGOTIATION PHASE: You will have a conversation with the other "
        f"player. You can discuss strategy, make promises, threaten, bluff, "
        f"or try to build trust -- but nothing said here is binding.\n"
        f"2. DECISION PHASE: After the conversation, you will privately "
        f"submit your action (cooperate or defect) to a moderator. The "
        f"other player will NOT see your decision until both decisions "
        f"are revealed simultaneously.\n\n"
        f"{matrix_text}"
        f"{private_info}\n\n"
        f"When the negotiation phase is finished, say "
        f"{negotiation_termination_message}. "
        f"Keep your answers concise, try not to go over {words} words."
    )


def create_pd_agents(
    game_id,
    teams,
    payoff_matrix,
    private_values,
    negotiation_termination_message,
):
    """Create one agent per team for a PD game.

    *private_values* is a list of dicts with ``class``, ``group_id``,
    and ``minimizer_value`` (re-used as the private signal for PD).
    Students submit a single prompt (or the first part before ``#_;:)``).
    """
    team_info = []

    for team in teams:
        try:
            submission = get_student_prompt(game_id, team[0], team[1])
            if not submission:
                raise Exception(f"No submission found for team {team}")

            # Use first prompt segment (before delimiter) for PD
            prompt = submission.split("#_;:)")[0].strip()

            # Look up the team's private value
            private_value = None
            for pv in private_values:
                if pv["class"] == team[0] and int(pv["group_id"]) == team[1]:
                    private_value = pv.get("minimizer_value")
                    break

            system_message = _build_pd_system_message(
                prompt,
                payoff_matrix,
                private_value=private_value,
                negotiation_termination_message=negotiation_termination_message,
            )

            team_info.append(
                {
                    "Name": f"Class{team[0]}_Group{team[1]}",
                    "Private Value": private_value,
                    "Agent": GameAgent(
                        name=f"Class{team[0]}_Group{team[1]}",
                        system_message=system_message,
                    ),
                }
            )
        except Exception as e:
            print(f"Error creating PD agent for team {team}: {e}")
            raise

    return team_info


# ---------------------------------------------------------------------------
# Chat helpers
# ---------------------------------------------------------------------------

def _format_chat_for_decision(chat_history, name1, name2):
    """Format the cheap-talk transcript as context for the decision phase."""
    lines = []
    for entry in chat_history:
        clean = clean_agent_message(name1, name2, entry["content"])
        lines.append(f"{entry['name']}: {clean}")
    return "\n\n".join(lines)


def _build_decision_prompt():
    """Prompt sent to each agent for their private, binding decision."""
    return (
        "\n\n---\n\n"
        "The negotiation phase is now OVER. You must now make your "
        "FINAL, BINDING decision.\n"
        "The other player will NOT see your decision until both "
        "decisions are revealed simultaneously.\n\n"
        "Consider everything discussed during the negotiation, but "
        "remember: promises made during negotiation are NOT binding.\n\n"
        f"Reply with exactly one line:\n"
        f"  {PD_DECISION_KEYWORD} cooperate\n"
        f"or:\n"
        f"  {PD_DECISION_KEYWORD} defect"
    )


# ---------------------------------------------------------------------------
# Single-match orchestration
# ---------------------------------------------------------------------------

def create_pd_chat(
    game_id,
    team1,
    team2,
    num_turns,
    payoff_matrix,
    round_num,
    engine,
    negotiation_termination_message,
    store_in_db=True,
    timing_totals=None,
    run_diagnostics=None,
):
    """Run one PD match: cheap talk -> private decisions -> scoring.

    Returns ``(action1, action2, score1, score2)``.
    """
    game_details = get_game_by_id(game_id)
    game_explanation = game_details.get("explanation", "") if game_details else ""
    game_context = (
        f"Game Type: prisoners_dilemma\n"
        f"Game Explanation: {game_explanation}\n\n"
    )

    agent1 = team1["Agent"]
    agent2 = team2["Agent"]
    name1 = agent1.name
    name2 = agent2.name

    # Temporarily prepend game context to system messages
    original_sys1 = agent1.system_message
    original_sys2 = agent2.system_message
    agent1.system_message = game_context + agent1.system_message
    agent2.system_message = game_context + agent2.system_message

    def termination_fn(msg, history):
        return negotiation_termination_message in msg["content"]

    # -- Phase 1: Cheap talk --------------------------------------------------
    chat_start = time.perf_counter()
    chat = engine.run_bilateral(agent1, agent2, num_turns, termination_fn)
    chat_elapsed = time.perf_counter() - chat_start

    turn_count = len(chat.chat_history) if getattr(chat, "chat_history", None) else 0

    negotiation_transcript = ""
    for entry in chat.chat_history:
        clean_msg = clean_agent_message(name1, name2, entry["content"])
        negotiation_transcript += f"{entry['name']}: {clean_msg}\n\n\n"

    # -- Phase 2: Private decisions -------------------------------------------
    decision_start = time.perf_counter()
    conversation_context = _format_chat_for_decision(chat.chat_history, name1, name2)
    decision_prompt = _build_decision_prompt()
    decision_context = conversation_context + decision_prompt

    response1 = engine.single_decision(agent1, decision_context)
    response2 = engine.single_decision(agent2, decision_context)

    action1 = parse_pd_action(response1)
    action2 = parse_pd_action(response2)
    decision_elapsed = time.perf_counter() - decision_start

    # -- Phase 3: Scoring -----------------------------------------------------
    score1, score2 = compute_pd_scores(
        action1 or "", action2 or "", payoff_matrix
    )

    # Restore original system messages
    agent1.system_message = original_sys1
    agent2.system_message = original_sys2

    # Build summary
    summary_text = (
        f"{name1} decision: {action1 or 'unclear'}\n"
        f"{name2} decision: {action2 or 'unclear'}\n"
        f"Outcome: ({score1}, {score2})"
    )

    # -- Persist ---------------------------------------------------------------
    db_elapsed = 0.0
    if store_in_db and game_id and round_num is not None:
        class1, group1 = parse_team_name(team1["Name"])
        class2, group2 = parse_team_name(team2["Name"])
        if class1 and group1 is not None and class2 and group2 is not None:
            try:
                db_start = time.perf_counter()
                full_transcript = (
                    negotiation_transcript
                    + "\n\n--- PRIVATE DECISIONS ---\n\n"
                    + summary_text
                )
                insert_negotiation_chat(
                    game_id=game_id,
                    round_number=round_num,
                    group1_class=class1,
                    group1_id=group1,
                    group2_class=class2,
                    group2_id=group2,
                    transcript=full_transcript,
                    summary=summary_text,
                    deal_value=None,
                )
                db_elapsed = time.perf_counter() - db_start
            except Exception as e:
                print(f"Warning: Failed to store PD chat: {e}")

    if timing_totals is not None:
        timing_totals["chat_seconds"] += chat_elapsed
        timing_totals["summary_seconds"] += decision_elapsed
        timing_totals["db_seconds"] += db_elapsed
        timing_totals["chats_measured"] += 1

    if run_diagnostics is not None:
        run_diagnostics["total_turns"] += turn_count
        run_diagnostics["summary_calls"] += 1
        run_diagnostics["successful_chats"] += 1

    return action1, action2, score1, score2


# ---------------------------------------------------------------------------
# Tournament orchestration
# ---------------------------------------------------------------------------

def create_pd_chats(
    game_id,
    llm_config,
    teams,
    payoff_matrix,
    private_values,
    num_rounds,
    num_turns,
    negotiation_termination_message,
    progress_callback=None,
):
    """Run a full PD tournament: round-robin pairings with cheap talk.

    Unlike zero-sum, each pair plays **once** per round (PD is symmetric).
    """
    if payoff_matrix is None:
        payoff_matrix = DEFAULT_PD_PAYOFF_MATRIX

    schedule = berger_schedule(
        [f"Class{i[0]}_Group{i[1]}" for i in teams], num_rounds
    )

    engine = ConversationEngine(llm_config)
    team_info = create_pd_agents(
        game_id, teams, payoff_matrix, private_values,
        negotiation_termination_message,
    )

    max_retries = 10
    total_matches = sum(len(round_matches) for round_matches in schedule)
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

    def emit_progress(round_num, team1, team2, phase, attempt=None, elapsed_seconds=None):
        if progress_callback:
            progress_callback(
                round_num=round_num,
                team1=team1,
                team2=team2,
                role1_name="Player",
                role2_name="Player",
                completed_matches=processed_matches,
                total_matches=total_matches,
                phase=phase,
                attempt=attempt,
                elapsed_seconds=elapsed_seconds,
            )

    errors_matchups = []
    name_roles = ["Player 1", "Player 2"]

    for round_, round_matches in enumerate(schedule, 1):
        for match in round_matches:
            team1 = next((t for t in team_info if t["Name"] == match[0]), None)
            team2 = next((t for t in team_info if t["Name"] == match[1]), None)

            class_group_1 = team1["Name"].split("_")
            class1 = class_group_1[0][5:]
            group1 = class_group_1[1][5:]

            class_group_2 = team2["Name"].split("_")
            class2 = class_group_2[0][5:]
            group2 = class_group_2[1][5:]

            insert_round_data(
                game_id, round_, class1, group1, class2, group2,
                None, None, None, None,
            )

            match_success = False
            elapsed = 0.0
            for attempt in range(max_retries):
                attempt_start = time.perf_counter()
                try:
                    run_diagnostics["attempts_total"] += 1
                    emit_progress(round_, team1, team2, "running", attempt + 1)

                    action1, action2, score1, score2 = create_pd_chat(
                        game_id,
                        team1,
                        team2,
                        num_turns,
                        payoff_matrix,
                        round_,
                        engine,
                        negotiation_termination_message,
                        timing_totals=timing_totals,
                        run_diagnostics=run_diagnostics,
                    )

                    update_round_data(
                        game_id, round_,
                        class1, group1, class2, group2,
                        score1, score2, 1, 2,
                    )
                    completed_matches += 1
                    match_success = True
                    break

                except Exception:
                    run_diagnostics["attempts_failed"] += 1
                    elapsed = round(time.perf_counter() - attempt_start, 2)
                    emit_progress(
                        round_, team1, team2, "retrying",
                        attempt + 1, elapsed_seconds=elapsed,
                    )
                    if attempt == max_retries - 1:
                        errors_matchups.append(
                            (round_, team1["Name"], team2["Name"])
                        )

            elapsed = round(time.perf_counter() - attempt_start, 2)
            processed_matches += 1
            emit_progress(
                round_, team1, team2,
                "completed" if match_success else "failed",
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
