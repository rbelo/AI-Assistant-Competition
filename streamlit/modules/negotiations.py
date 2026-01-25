import re
import time

import autogen
from modules.metrics_handler import (
    record_conversation_metrics,
    record_conversation_processing,
    record_deal_analysis,
    record_deal_metrics,
    record_prompt_metrics,
    record_prompt_submission,
)

from .database_handler import (
    get_error_matchups,
    get_game_by_id,
    get_student_prompt,
    insert_negotiation_chat,
    insert_round_data,
    update_round_data,
)
from .schedule import berger_schedule


# Function for cleaning of the dialogue messages that may include in the message "Agent Name:"
def clean_agent_message(agent_name_1, agent_name_2, message):
    if not message:  # Handle possible empty messages
        return ""

    # Define a regex pattern to match "Agent_name: " at the start of the message for either agent
    pattern = rf"^\s*(?:{re.escape(agent_name_1)}|{re.escape(agent_name_2)})\s*:\s*"

    # Use regex substitution to remove the pattern from the message
    clean_message = re.sub(pattern, "", message, flags=re.IGNORECASE)

    return clean_message


def _build_summary_context(chat_history, role1_name=None, role2_name=None, history_size=4):
    if not chat_history:
        return ""

    if history_size is None:
        recent_history = chat_history
    else:
        recent_history = chat_history[-history_size:] if history_size else []

    summary_context = ""
    for entry in recent_history:
        content = entry.get("content", "")
        if role1_name and role2_name:
            content = clean_agent_message(role1_name, role2_name, content)
        summary_context += f"{entry.get('name', '')}: {content}\n\n\n"
    return summary_context


def _extract_summary_text(summary_eval, summary_agent_name):
    if not summary_eval or not getattr(summary_eval, "chat_history", None):
        return ""

    for entry in reversed(summary_eval.chat_history):
        if entry.get("name") == summary_agent_name and entry.get("content"):
            return entry["content"]

    last_entry = summary_eval.chat_history[-1]
    return last_entry.get("content", "") if last_entry else ""


def parse_deal_value(summary_text, summary_termination_message):
    if not summary_text or not summary_termination_message:
        return -1

    for line in summary_text.splitlines():
        stripped = line.strip()
        if summary_termination_message in stripped:
            value_str = stripped.split(summary_termination_message, 1)[1].strip()
            value_str = value_str.replace("$", "").replace(",", "")
            match = re.findall(r"-?\d+(?:[.,]\d+)?", value_str)
            if not match:
                return -1
            try:
                return float(match[0].replace(",", "."))
            except Exception:
                return -1

    return -1


def evaluate_deal_summary(
    chat_history,
    summary_prompt,
    summary_termination_message,
    user,
    summary_agent,
    role1_name=None,
    role2_name=None,
    history_size=4,
):
    if not summary_agent or not user:
        return "", -1

    summary_context = _build_summary_context(chat_history, role1_name, role2_name, history_size)
    summary_eval = user.initiate_chat(
        summary_agent, clear_history=True, max_turns=1, message=summary_context + (summary_prompt or "")
    )
    summary_text = _extract_summary_text(summary_eval, summary_agent.name)
    return summary_text, parse_deal_value(summary_text, summary_termination_message)


def extract_summary_from_transcript(transcript, summary_termination_message):
    if not transcript:
        return "", -1

    parts = [part.strip() for part in transcript.split("\n\n\n") if part.strip()]
    if not parts:
        return "", -1

    summary_text = parts[-1]
    if summary_termination_message and summary_termination_message not in summary_text:
        return "", -1

    return summary_text, parse_deal_value(summary_text, summary_termination_message)


def build_summary_agents(
    config_list, summary_termination_message, negotiation_termination_message, include_summary=False
):
    user = autogen.UserProxyAgent(
        name="User",
        llm_config=config_list,
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: summary_termination_message in msg["content"],
        code_execution_config={"work_dir": "repo", "use_docker": False},
    )

    summary_prefix = ""
    if include_summary:
        summary_prefix = "Provide a concise 2-3 sentence summary before the final line.\n"

    summary_agent = autogen.AssistantAgent(
        name="Summary_Agent",
        llm_config=config_list,
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: summary_termination_message in msg["content"],
        system_message=f"""You are a sophisticated negotiation analyzer. Your task is to determine if a negotiation has reached a valid agreement.

Key Requirements:
1. Analyze the ENTIRE conversation, not just the last few messages
2. Look for explicit agreement on a specific value from BOTH parties
3. Verify that the agreed value is consistent throughout the conversation
4. Check for confirmation messages from both parties
5. Ensure the negotiation follows a natural flow and reaches a legitimate conclusion
6. Consider the negotiation context and expected value ranges

To determine if there is a valid agreement:
- Both parties must explicitly agree on the same value
- The agreement must be confirmed by both parties
- The conversation must end naturally with {negotiation_termination_message}
- The agreement must be consistent with the negotiation context
- There must be no contradictions or retractions of the agreement

Your response format:
{summary_prefix}- If there is a valid agreement: '{summary_termination_message} [agreed_value]'
- If there is no valid agreement: '{summary_termination_message} -1'

Be thorough in your analysis and only report an agreement if ALL conditions are met.""",
    )

    return user, summary_agent


def parse_team_name(team_name):
    if not team_name:
        return None, None
    parts = team_name.split("_")
    if len(parts) < 2:
        return None, None
    class_part = parts[0].replace("Class", "")
    group_part = parts[1].replace("Group", "")
    try:
        group_part = int(group_part)
    except ValueError:
        pass
    return class_part, group_part


def create_chat(
    game_id,
    minimizer_team,
    maximizer_team,
    initiator_role_index,
    starting_message,
    num_turns,
    summary_prompt,
    round_num,
    user,
    summary_agent,
    summary_termination_message,
    store_in_db=True,
    game_type="zero-sum",
):
    """
    Create a negotiation chat between two teams.

    Args:
        game_id: The game ID
        minimizer_team: Team playing the minimizer role
        maximizer_team: Team playing the maximizer role
        initiator_role_index: Role index (1 or 2) for the initiator team
        starting_message: Initial message to start negotiation
        num_turns: Maximum number of turns
        summary_prompt: Prompt for the summary agent
        round_num: Round number
        user: User proxy agent for summary
        summary_agent: Agent to evaluate deal outcome
        summary_termination_message: Message prefix for deal value extraction
        store_in_db: Whether to store chat in database
        game_type: Type of game (zero-sum, etc.)
    """
    # Get game explanation from database
    game_details = get_game_by_id(game_id)
    game_explanation = game_details.get("explanation", "") if game_details else ""

    # Add game type and explanation to the context
    game_context = f"Game Type: {game_type}\nGame Explanation: {game_explanation}\n\n"

    responder_role_index = 2 if initiator_role_index == 1 else 1
    initiator_team, responder_team = (
        (minimizer_team, maximizer_team) if initiator_role_index == 1 else (maximizer_team, minimizer_team)
    )

    # Use agents from team dicts
    agent1 = get_role_agent(initiator_team, initiator_role_index)
    agent2 = get_role_agent(responder_team, responder_role_index)
    name1 = agent1.name
    name2 = agent2.name

    # Add game context to agent prompts
    if hasattr(agent1, "system_message") and agent1.system_message:
        agent1.update_system_message(game_context + agent1.system_message)
    if hasattr(agent2, "system_message") and agent2.system_message:
        agent2.update_system_message(game_context + agent2.system_message)

    chat = agent1.initiate_chat(agent2, clear_history=True, max_turns=num_turns, message=starting_message)

    negotiation = ""

    for _i, entry in enumerate(chat.chat_history):
        clean_msg = clean_agent_message(name1, name2, entry["content"])
        formatted = f"{entry['name']}: {clean_msg}\n\n\n"
        negotiation += formatted
    summary_text = ""
    deal_value = -1
    if summary_agent and user:
        summary_text, deal_value = evaluate_deal_summary(
            chat.chat_history,
            summary_prompt,
            summary_termination_message,
            user,
            summary_agent,
            role1_name=name1,
            role2_name=name2,
            history_size=4,
        )
        if summary_text:
            negotiation += "\n" + summary_text

    if store_in_db and minimizer_team and maximizer_team and game_id and round_num is not None:
        class1, group1 = parse_team_name(minimizer_team["Name"])
        class2, group2 = parse_team_name(maximizer_team["Name"])
        if class1 and group1 is not None and class2 and group2 is not None:
            try:
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
            except Exception as e:
                print(f"Warning: Failed to store negotiation chat: {e}")

    # Parse the result value
    # Record metrics (with safe defaults for optional values)
    start_time = time.time()
    try:
        record_prompt_metrics(
            user_id=user.name if user else None,
            prompt=starting_message,
            response=negotiation,
            processing_time=time.time() - start_time,
        )
        record_prompt_submission(user_id=user.name if user else None)

        # Record conversation metrics
        record_conversation_metrics(
            user_id=user.name if user else None,
            conversation_id=f"{game_id}_{round_num}" if game_id and round_num else None,
            duration=time.time() - start_time,
            messages_count=len(chat.chat_history) if chat else 0,
        )
        record_conversation_processing(user_id=user.name if user else None, processing_time=time.time() - start_time)

        # Record deal metrics if a deal was made
        if deal_value > 0:
            team_name = minimizer_team["Name"] if minimizer_team else "unknown"
            record_deal_metrics(
                user_id=user.name if user else None,
                deal_id=f"{game_id}_{round_num}_{team_name}",
                value=deal_value,
                duration=time.time() - start_time,
            )
            record_deal_analysis(
                user_id=user.name if user else None, deal_id=f"{game_id}_{round_num}_{team_name}", analysis=summary_text
            )
    except Exception as e:
        # Don't fail the whole negotiation if metrics recording fails
        print(f"Warning: Failed to record metrics: {e}")

    return deal_value


def compute_deal_scores(deal, maximizer_value, minimizer_value, precision=4):
    """Compute normalized scores using (deal, maximizer_reservation, minimizer_reservation).

    When a deal is feasible for both sides, maximizer_value < minimizer_value.
    In that case, deals within the overlap use a ratio (maximizer share), while
    deals outside the overlap give a full score to the side whose reservation is met.
    If maximizer_value >= minimizer_value, there is no overlap; only deals outside
    both reservations score, otherwise (0, 0).
    """
    if deal is None:
        return 0, 0
    if deal == -1:
        return -1, -1

    if maximizer_value < minimizer_value:
        if deal < maximizer_value:
            return 0, 1
        if deal > minimizer_value:
            return 1, 0
        ratio = round((deal - maximizer_value) / (minimizer_value - maximizer_value), precision)
        ratio = max(0, min(1, ratio))
        return ratio, 1 - ratio

    if deal > maximizer_value:
        return 1, 0
    if deal < minimizer_value:
        return 0, 1

    return 0, 0


def resolve_initiator_role_index(name_roles, conversation_order):
    """Resolve which role starts the conversation (1 or 2)."""
    if not conversation_order:
        return 1

    normalized = str(conversation_order).strip()
    if normalized == "same":
        return 1
    if normalized == "opposite":
        return 2

    if normalized == name_roles[0]:
        return 1
    if normalized == name_roles[1]:
        return 2

    return 1


def get_role_agent(team, role_index):
    if role_index == 1:
        return team["Agent 1"]
    if role_index == 2:
        return team["Agent 2"]
    raise ValueError(f"Invalid role index: {role_index}")


def get_minimizer_reservation(team):
    return team["Value 1"]


def get_maximizer_reservation(team):
    return team["Value 2"]


def get_minimizer_maximizer(initiator_team, responder_team, initiator_role_index):
    if initiator_role_index == 1:
        return initiator_team, responder_team
    return responder_team, initiator_team


def is_valid_termination(msg, history, negotiation_termination_message):
    """
    Enhanced termination check that verifies legitimate agreement conclusion
    """
    # Check for termination phrase
    if negotiation_termination_message not in msg["content"]:
        return False

    if not history:
        return True

    # Get the last few messages for context
    last_messages = history[-4:] if len(history) >= 4 else history

    # Check for agreement patterns
    agreement_indicators = [
        "agree",
        "accepted",
        "deal",
        "settled",
        "confirmed",
        "final",
        "conclude",
        "complete",
        "done",
    ]

    # Count agreement indicators in recent messages
    agreement_count = sum(
        1 for m in last_messages if any(indicator in m["content"].lower() for indicator in agreement_indicators)
    )

    # Require at least 2 agreement indicators in recent messages
    if agreement_count < 2:
        return False

    # Check for value consistency
    values = []
    for m in last_messages:
        # Extract numeric values from messages, handling different formats
        # Remove currency symbols and commas
        clean_content = m["content"].replace("$", "").replace(",", "")
        numbers = re.findall(r"-?\d+(?:\.\d+)?", clean_content)
        if numbers:
            values.extend([float(n) for n in numbers])

    # If we found values, check if they're consistent
    if values:
        # Values should be within 5% of each other
        max_diff = max(values) * 0.05
        if max(values) - min(values) > max_diff:
            return False

    return True


def build_llm_config(model, api_key, temperature=0.3, top_p=0.5):
    config_list = {"config_list": [{"model": model, "api_key": api_key}]}
    if not model.startswith("gpt-5"):
        config_list["temperature"] = temperature
        config_list["top_p"] = top_p
    return config_list


def is_invalid_api_key_error(error):
    message = str(error).lower()
    return (
        "invalid api key" in message
        or "incorrect api key" in message
        or "invalid_api_key" in message
        or "unauthorized" in message
        or "authentication" in message
        or "401" in message
    )


def create_agents(game_id, teams, values, name_roles, config_list, negotiation_termination_message):
    team_info = []

    role_1, role_2 = name_roles[0].replace(" ", ""), name_roles[1].replace(" ", "")

    if config_list["config_list"][0]["model"] == "gpt-4o-mini":
        words = 50
    elif config_list["config_list"][0]["model"] == "gpt-4o":
        words = 50
    else:
        words = 50

    for team in teams:
        try:
            submission = get_student_prompt(game_id, team[0], team[1])
            if not submission:
                raise Exception(f"No submission found for team {team}")

            value_dict = next(
                (value for value in values if value["class"] == team[0] and int(value["group_id"]) == team[1]), None
            )
            if value_dict is None:
                raise Exception(f"No value found for team {team}")
            value1 = int(value_dict["minimizer_value"])
            value2 = int(value_dict["maximizer_value"])

            prompts = [part.strip() for part in submission.split("#_;:)")]

            # Create a closure to capture chat history
            def create_termination_check(history):
                return lambda msg: is_valid_termination(msg, history, negotiation_termination_message)

            new_team = {
                "Name": f"Class{team[0]}_Group{team[1]}",
                "Value 1": value1,  # value as role_1
                "Value 2": value2,  # value as role_2
                "Agent 1": autogen.ConversableAgent(
                    name=f"Class{team[0]}_Group{team[1]}_{role_1}",
                    llm_config=config_list,
                    human_input_mode="NEVER",
                    chat_messages=None,
                    system_message=prompts[0]
                    + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about 10 opportunities to intervene. Try to keep your answers concise, try not to go over {words} words.",
                    is_termination_msg=create_termination_check([]),
                ),
                "Agent 2": autogen.ConversableAgent(
                    name=f"Class{team[0]}_Group{team[1]}_{role_2}",
                    llm_config=config_list,
                    human_input_mode="NEVER",
                    chat_messages=None,
                    system_message=prompts[1]
                    + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about 10 opportunities to intervene. Try to keep your answers concise, try not to go over {words} words.",
                    is_termination_msg=create_termination_check([]),
                ),
            }

            team_info.append(new_team)
        except Exception as e:
            print(f"Error creating agents for team {team}: {str(e)}")
            raise

    return team_info


def create_chats(
    game_id,
    config_list,
    name_roles,
    conversation_order,
    teams,
    values,
    num_rounds,
    starting_message,
    num_turns,
    negotiation_termination_message,
    summary_prompt,
    summary_termination_message,
    progress_callback=None,
):
    schedule = berger_schedule([f"Class{i[0]}_Group{i[1]}" for i in teams], num_rounds)

    team_info = create_agents(game_id, teams, values, name_roles, config_list, negotiation_termination_message)
    initiator_role_index = resolve_initiator_role_index(name_roles, conversation_order)
    initiator_role_name = name_roles[initiator_role_index - 1]
    responder_role_name = name_roles[1 if initiator_role_index == 1 else 0]

    user, summary_agent = build_summary_agents(
        config_list,
        summary_termination_message,
        negotiation_termination_message,
        include_summary=True,
    )

    max_retries = 10
    total_matches = 0
    completed_matches = 0

    errors_matchups = []

    for round_, round_matches in enumerate(schedule, 1):
        total_matches += len(round_matches) * 2

        for match in round_matches:

            # Identify the two teams that play in each match of the round, by their id
            team1 = next((team for team in team_info if team["Name"] == match[0]), None)
            team2 = next((team for team in team_info if team["Name"] == match[1]), None)

            class_group_1 = team1["Name"].split("_")
            class1 = class_group_1[0][5:]
            group1 = class_group_1[1][5:]

            class_group_2 = team2["Name"].split("_")
            class2 = class_group_2[0][5:]
            group2 = class_group_2[1][5:]

            insert_round_data(game_id, round_, class1, group1, class2, group2, None, None, None, None)

            if progress_callback:
                progress_callback(round_, team1, team2, initiator_role_name, responder_role_name)

            # Attempt to create the first chat
            for attempt in range(max_retries):
                try:

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    minimizer_team, maximizer_team = get_minimizer_maximizer(team1, team2, initiator_role_index)
                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        starting_message,
                        num_turns,
                        summary_prompt,
                        round_,
                        user,
                        summary_agent,
                        summary_termination_message,
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

                    break  # Exit retry loop on success

                except Exception:
                    if attempt == max_retries - 1:
                        errors_matchups.append((round_, team1["Name"], team2["Name"]))

            # Attempt to create the second chat
            for attempt in range(max_retries):
                try:

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    minimizer_team, maximizer_team = get_minimizer_maximizer(team2, team1, initiator_role_index)
                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        starting_message,
                        num_turns,
                        summary_prompt,
                        round_,
                        user,
                        summary_agent,
                        summary_termination_message,
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

                    break  # Exit retry loop on success

                except Exception:
                    if attempt == max_retries - 1:
                        errors_matchups.append((round_, team2["Name"], team1["Name"]))

    # error messages
    if not errors_matchups:
        return {
            "status": "success",
            "completed_matches": completed_matches,
            "total_matches": total_matches,
        }

    else:

        error_message = "The following negotiations were unsuccessful:\n\n"

        for match in errors_matchups:
            error_message += f"- Round {match[0]} - {match[1]} ({name_roles[0]}) vs {match[2]} ({name_roles[1]});\n"

        return error_message


def create_all_error_chats(
    game_id,
    config_list,
    name_roles,
    conversation_order,
    values,
    starting_message,
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

    team_info = create_agents(game_id, teams, values, name_roles, config_list, negotiation_termination_message)
    initiator_role_index = resolve_initiator_role_index(name_roles, conversation_order)
    user, summary_agent = build_summary_agents(
        config_list,
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
            continue  # Skip this match

        if match[3] == 1:
            minimizer_team = team1
            maximizer_team = team2

            for attempt in range(max_retries):
                try:

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        starting_message,
                        num_turns,
                        summary_prompt,
                        match[0],
                        user,
                        summary_agent,
                        summary_termination_message,
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

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    deal = create_chat(
                        game_id,
                        minimizer_team,
                        maximizer_team,
                        initiator_role_index,
                        starting_message,
                        num_turns,
                        summary_prompt,
                        match[0],
                        user,
                        summary_agent,
                        summary_termination_message,
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

    else:

        error_message = "The following negotiations were unsuccessful:\n\n"

        for match in errors_matchups:
            error_message += f"- Round {match[0]} - {match[1]} ({name_roles[0]}) vs {match[2]} ({name_roles[1]});\n"

        return error_message
