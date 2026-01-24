import re
import autogen
from .database_handler import insert_round_data, update_round_data, get_error_matchups, get_game_by_id, insert_negotiation_chat, get_student_prompt
from .schedule import berger_schedule
from modules.metrics_handler import record_prompt_metrics, record_prompt_submission, record_conversation_metrics, record_conversation_processing, record_deal_metrics, record_deal_analysis
import time


# Function for cleaning of the dialogue messages that may include in the message "Agent Name:"
def clean_agent_message(agent_name_1, agent_name_2, message):
    if not message:  # Handle possible empty messages
        return ""

    # Define a regex pattern to match "Agent_name: " at the start of the message for either agent
    pattern = rf"^\s*(?:{re.escape(agent_name_1)}|{re.escape(agent_name_2)})\s*:\s*"

    # Use regex substitution to remove the pattern from the message
    clean_message = re.sub(pattern, "", message, flags=re.IGNORECASE)

    return clean_message


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


def create_chat(game_id, order, team1, team2, starting_message, num_turns, summary_prompt,
                round_num, user, summary_agent, summary_termination_message,
                store_in_db=True, game_type="zero-sum"):
    """
    Create a negotiation chat between two teams.

    Args:
        game_id: The game ID
        order: 'same' or 'opposite' for role ordering
        team1: First team dict with 'Agent 1', 'Agent 2', 'Name', 'Value 1', 'Value 2'
        team2: Second team dict
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

    # Use agents from team dicts
    agent1 = team1["Agent 1"]
    agent2 = team2["Agent 2"]
    name1 = agent1.name
    name2 = agent2.name

    # Add game context to agent prompts
    if hasattr(agent1, 'system_message') and agent1.system_message:
        agent1.update_system_message(game_context + agent1.system_message)
    if hasattr(agent2, 'system_message') and agent2.system_message:
        agent2.update_system_message(game_context + agent2.system_message)

    chat = agent1.initiate_chat(
        agent2,
        clear_history=True,
        max_turns=num_turns,
        message=starting_message
    )

    negotiation = ""
    summ = ""

    for i, entry in enumerate(chat.chat_history):
        clean_msg = clean_agent_message(name1, name2, entry['content'])
        formatted = f"{entry['name']}: {clean_msg}\n\n\n"
        negotiation += formatted
        if i >= len(chat.chat_history) - 4:
            summ += formatted

    deal_str = ""
    if summary_agent and user:
        summary_eval = user.initiate_chat(
            summary_agent,
            clear_history=True,
            max_turns=1,
            message=summ + summary_prompt
        )
        deal_str = summary_eval.chat_history[1]['content']
        negotiation += "\n" + deal_str

    if store_in_db and team1 and team2 and game_id and round_num is not None:
        storage_team1 = team1
        storage_team2 = team2
        if order == "opposite":
            storage_team1 = team2
            storage_team2 = team1
        class1, group1 = parse_team_name(storage_team1["Name"])
        class2, group2 = parse_team_name(storage_team2["Name"])
        if class1 and group1 is not None and class2 and group2 is not None:
            try:
                insert_negotiation_chat(
                    game_id=game_id,
                    round_number=round_num,
                    group1_class=class1,
                    group1_id=group1,
                    group2_class=class2,
                    group2_id=group2,
                    transcript=negotiation
                )
            except Exception as e:
                print(f"Warning: Failed to store negotiation chat: {e}")

    # Parse the result value
    deal_value = -1  # Default to -1 (failed negotiation)
    if summary_termination_message and deal_str.startswith(summary_termination_message):
        try:
            # Clean the value string before parsing
            value_str = deal_str.replace(summary_termination_message, "").strip()
            value_str = value_str.replace("$", "").replace(",", "")
            deal_value = float(re.findall(r'-?\d+(?:[.,]\d+)?', value_str)[0].replace(",", "."))
        except Exception as e:
            print(f"Error parsing deal value: {str(e)}")
            deal_value = -1

    # Record metrics (with safe defaults for optional values)
    start_time = time.time()
    try:
        record_prompt_metrics(
            user_id=user.name if user else None,
            prompt=starting_message,
            response=negotiation,
            processing_time=time.time() - start_time
        )
        record_prompt_submission(user_id=user.name if user else None)

        # Record conversation metrics
        record_conversation_metrics(
            user_id=user.name if user else None,
            conversation_id=f"{game_id}_{round_num}" if game_id and round_num else None,
            duration=time.time() - start_time,
            messages_count=len(chat.chat_history) if chat else 0
        )
        record_conversation_processing(
            user_id=user.name if user else None,
            processing_time=time.time() - start_time
        )

        # Record deal metrics if a deal was made
        if deal_value > 0:
            record_deal_metrics(
                user_id=user.name if user else None,
                deal_id=f"{game_id}_{round_num}_{team1['Name'] if team1 else 'unknown'}",
                value=deal_value,
                duration=time.time() - start_time
            )
            record_deal_analysis(
                user_id=user.name if user else None,
                deal_id=f"{game_id}_{round_num}_{team1['Name'] if team1 else 'unknown'}",
                analysis=deal_str
            )
    except Exception as e:
        # Don't fail the whole negotiation if metrics recording fails
        print(f"Warning: Failed to record metrics: {e}")

    return deal_value

def validate_message(message, game_type="zero-sum"):
    """Validate agent messages based on game type"""
    if game_type == "zero-sum":
        # Check for valid price format
        price_pattern = r'\$\d+'
        return bool(re.search(price_pattern, message))

    elif game_type == "prisoners_dilemma":
        # Check for valid decision
        decision_pattern = r'(COOPERATE|DEFECT)'
        return bool(re.search(decision_pattern, message))

    return False

def create_agent_message(config_list, role, prompt, previous_messages, game_type="zero-sum"):
    """Generate agent messages with game type specific validation"""
    message = generate_message(config_list, role, prompt, previous_messages)

    if not validate_message(message, game_type):
        if game_type == "zero-sum":
            return "Invalid message format. Please include a price in $ format."
        elif game_type == "prisoners_dilemma":
            return "Invalid message format. Please explicitly state COOPERATE or DEFECT."

    return message

# In modules/negotiations.py

def calculate_score(agent_1_msg, agent_2_msg, agent_1_value, agent_2_value, game_type="zero-sum"):
    """Calculate scores based on game type"""
    if game_type == "zero-sum":
        # Extract price from messages
        price = extract_price(agent_1_msg) or extract_price(agent_2_msg)
        if not price:
            return None

        return {
            "minimizer_score": agent_1_value - price,
            "maximizer_score": price - agent_2_value
        }

    elif game_type == "prisoners_dilemma":
        # Extract decisions
        decision1 = "COOPERATE" in agent_1_msg.upper()
        decision2 = "COOPERATE" in agent_2_msg.upper()

        # Prisoner's dilemma payoff matrix
        if decision1 and decision2:  # Both cooperate
            return {"player1_score": 3, "player2_score": 3}
        elif not decision1 and not decision2:  # Both defect
            return {"player1_score": 1, "player2_score": 1}
        elif decision1:  # 1 cooperates, 2 defects
            return {"player1_score": 0, "player2_score": 5}
        else:  # 1 defects, 2 cooperates
            return {"player1_score": 5, "player2_score": 0}


def is_valid_termination(msg, history, negotiation_termination_message):
    """
    Enhanced termination check that verifies legitimate agreement conclusion
    """
    # Check for termination phrase
    if negotiation_termination_message not in msg["content"]:
        return False
        
    # Get the last few messages for context
    last_messages = history[-4:] if len(history) >= 4 else history
    
    # Check for agreement patterns
    agreement_indicators = [
        "agree", "accepted", "deal", "settled", "confirmed",
        "final", "conclude", "complete", "done"
    ]
    
    # Count agreement indicators in recent messages
    agreement_count = sum(1 for m in last_messages 
                         if any(indicator in m["content"].lower() 
                               for indicator in agreement_indicators))
    
    # Require at least 2 agreement indicators in recent messages
    if agreement_count < 2:
        return False
        
    # Check for value consistency
    values = []
    for m in last_messages:
        # Extract numeric values from messages, handling different formats
        # Remove currency symbols and commas
        clean_content = m["content"].replace("$", "").replace(",", "")
        numbers = re.findall(r'-?\d+(?:\.\d+)?', clean_content)
        if numbers:
            values.extend([float(n) for n in numbers])
    
    # If we found values, check if they're consistent
    if values:
        # Values should be within 5% of each other
        max_diff = max(values) * 0.05
        if max(values) - min(values) > max_diff:
            return False
    
    return True

def create_agents(game_id, order, teams, values, name_roles, config_list, negotiation_termination_message):
    team_info = []

    if order == "same":
        role_1, role_2 = name_roles[0].replace(" ", ""), name_roles[1].replace(" ", "")

    elif order == "opposite":
        role_1, role_2 = name_roles[1].replace(" ", ""), name_roles[0].replace(" ", "")

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

            value_dict = next((value for value in values if value["class"] == team[0] and int(value["group_id"]) == team[1]), None)
            if value_dict is None:
                raise Exception(f"No value found for team {team}")
            value1 = int(value_dict["minimizer_value"])
            value2 = int(value_dict["maximizer_value"])

            prompts = [part.strip() for part in submission.split('#_;:)')]

            if order == "opposite":
                aux_val = value1
                value1 = value2
                value2 = aux_val
                prompts = prompts[::-1]  # reverse the prompts

            # Create a closure to capture chat history
            def create_termination_check(history):
                return lambda msg: is_valid_termination(msg, history, negotiation_termination_message)

            new_team = {"Name": f'Class{team[0]}_Group{team[1]}',
                        "Value 1": value1,  # value as role_1
                        "Value 2": value2,  # value as role_2
                        "Agent 1": autogen.ConversableAgent(
                            name=f"Class{team[0]}_Group{team[1]}_{role_1}",
                            llm_config=config_list,
                            human_input_mode="NEVER",
                            chat_messages=None,
                            system_message=prompts[0] + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about 10 opportunities to intervene. Try to keep your answers concise, try not to go over {words} words.",
                            is_termination_msg=create_termination_check([])
                        ),

                        "Agent 2": autogen.ConversableAgent(
                            name=f"Class{team[0]}_Group{team[1]}_{role_2}",
                            llm_config=config_list,
                            human_input_mode="NEVER",
                            chat_messages=None,
                            system_message=prompts[1] + f' When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about 10 opportunities to intervene. Try to keep your answers concise, try not to go over {words} words.',
                            is_termination_msg=create_termination_check([])
                        )
                        }

            team_info.append(new_team)
        except Exception as e:
            print(f"Error creating agents for team {team}: {str(e)}")
            raise

    return team_info


def create_chats(game_id, config_list, name_roles, order, teams, values, num_rounds, starting_message, num_turns,
                 negotiation_termination_message, summary_prompt, summary_termination_message, progress_callback=None):
    schedule = berger_schedule([f'Class{i[0]}_Group{i[1]}' for i in teams], num_rounds)

    team_info = create_agents(game_id, order, teams, values, name_roles, config_list, negotiation_termination_message)

    user = autogen.UserProxyAgent(
        name="User",
        llm_config=config_list,
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: summary_termination_message in msg["content"],
        code_execution_config={"work_dir": "repo", "use_docker": False}
    )

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
- If there is a valid agreement: '{summary_termination_message} [agreed_value]'
- If there is no valid agreement: '{summary_termination_message} -1'

Be thorough in your analysis and only report an agreement if ALL conditions are met."""
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

            insert_round_data(game_id, round_, class1, group1, class2, group2, -1, -1, -1, -1)

            if progress_callback:
                progress_callback(round_, team1, team2, order)

            # Attempt to create the first chat
            for attempt in range(max_retries):
                try:

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    # First chat
                    deal = create_chat(game_id, order, team1, team2, starting_message, num_turns, summary_prompt,
                                       round_, user, summary_agent, summary_termination_message)

                    if deal == -1:
                        score1_team1 = 0
                        score1_team2 = 0

                        update_round_data(game_id, round_, class1, group1, class2, group2, score1_team1, score1_team2,
                                          order)
                        completed_matches += 1

                    else:

                        if order == "same":

                            if deal > team2["Value 2"]:
                                score1_team1 = 0
                                score1_team2 = 1

                            elif deal < team1["Value 1"]:
                                score1_team1 = 1
                                score1_team2 = 0

                            else:
                                score1_team2 = round((deal - team1["Value 1"]) / (team2["Value 2"] - team1["Value 1"]),
                                                     4)
                                score1_team1 = 1 - score1_team2

                            # update_round_data(game_id, round_, class1, group1, class2, group2, score1_team1, score1_team2, order)

                        elif order == "opposite":

                            if deal > team1["Value 1"]:
                                score1_team1 = 1
                                score1_team2 = 0

                            elif deal < team2["Value 2"]:
                                score1_team1 = 0
                                score1_team2 = 1

                            else:
                                score1_team1 = round((deal - team2["Value 2"]) / (team1["Value 1"] - team2["Value 2"]),
                                                     4)
                                score1_team2 = 1 - score1_team1

                        update_round_data(game_id, round_, class1, group1, class2, group2, score1_team1, score1_team2,
                                          order)
                        completed_matches += 1

                    break  # Exit retry loop on success

                except Exception:
                    if attempt == max_retries - 1:
                        if order == "same":
                            errors_matchups.append((round_, team1["Name"], team2["Name"]))
                        elif order == "opposite":
                            errors_matchups.append((round_, team2["Name"], team1["Name"]))

            # Attempt to create the second chat
            for attempt in range(max_retries):
                try:

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    # Second chat
                    deal = create_chat(game_id, order, team2, team1, starting_message, num_turns, summary_prompt,
                                       round_, user, summary_agent, summary_termination_message)

                    if order == "same":

                        if deal == -1:
                            score2_team1 = 0
                            score2_team2 = 0

                        elif deal > team1["Value 2"]:
                            score2_team1 = 1
                            score2_team2 = 0

                        elif deal < team2["Value 1"]:
                            score2_team1 = 0
                            score2_team2 = 1

                        else:
                            score2_team1 = round((deal - team2["Value 1"]) / (team1["Value 2"] - team2["Value 1"]), 4)
                            score2_team2 = 1 - score2_team1

                        update_round_data(game_id, round_, class1, group1, class2, group2, score2_team1, score2_team2,
                                          "opposite")
                        completed_matches += 1

                    elif order == "opposite":

                        if deal == -1:
                            score2_team1 = 0
                            score2_team2 = 0

                        elif deal > team2["Value 1"]:
                            score2_team1 = 0
                            score2_team2 = 1

                        elif deal < team1["Value 2"]:
                            score2_team1 = 1
                            score2_team2 = 0

                        else:
                            score2_team2 = round((deal - team1["Value 2"]) / (team2["Value 1"] - team1["Value 2"]), 4)
                            score2_team1 = 1 - score2_team2

                        update_round_data(game_id, round_, class1, group1, class2, group2, score2_team1, score2_team2,
                                          "same")
                        completed_matches += 1

                    break  # Exit retry loop on success

                except Exception:
                    if attempt == max_retries - 1:
                        if order == "same":
                            errors_matchups.append((round_, team2["Name"], team1["Name"]))
                        elif order == "opposite":
                            errors_matchups.append((round_, team1["Name"], team2["Name"]))

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


def create_all_error_chats(game_id, config_list, name_roles, order, values, starting_message, num_turns,
                           negotiation_termination_message, summary_prompt, summary_termination_message):
    matches = get_error_matchups(game_id)

    teams1 = [i[1] for i in matches]
    teams2 = [i[2] for i in matches]

    unique_teams = set(tuple(item) for item in (teams1 + teams2))
    teams = [list(team) for team in unique_teams]

    team_info = create_agents(game_id, order, teams, values, name_roles, config_list, negotiation_termination_message)

    user = autogen.UserProxyAgent(
        name="User",
        llm_config=config_list,
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: summary_termination_message in msg["content"],
        code_execution_config={"work_dir": "repo", "use_docker": False}
    )

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
- If there is a valid agreement: '{summary_termination_message} [agreed_value]'
- If there is no valid agreement: '{summary_termination_message} -1'

Be thorough in your analysis and only report an agreement if ALL conditions are met."""
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

            for attempt in range(max_retries):
                try:

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    if order == "same":

                        deal = create_chat(game_id, order, team1, team2, starting_message, num_turns, summary_prompt,
                                           match[0], user, summary_agent, summary_termination_message)

                        if deal == -1:
                            score1_team1 = 0
                            score1_team2 = 0

                        else:

                            if deal > team2["Value 2"]:
                                score1_team1 = 0
                                score1_team2 = 1

                            elif deal < team1["Value 1"]:
                                score1_team1 = 1
                                score1_team2 = 0

                            else:
                                score1_team2 = round((deal - team1["Value 1"]) / (team2["Value 2"] - team1["Value 1"]),
                                                     4)
                                score1_team1 = 1 - score1_team2

                    elif order == "opposite":

                        deal = create_chat(game_id, order, team2, team1, starting_message, num_turns, summary_prompt,
                                           match[0], user, summary_agent, summary_termination_message)

                        if deal == -1:
                            score1_team1 = 0
                            score1_team2 = 0

                        else:

                            if deal > team2["Value 1"]:
                                score1_team1 = 0
                                score1_team2 = 1

                            elif deal < team1["Value 2"]:
                                score1_team1 = 1
                                score1_team2 = 0

                            else:
                                score1_team2 = round((deal - team1["Value 2"]) / (team2["Value 1"] - team1["Value 2"]),
                                                     4)
                                score1_team1 = 1 - score1_team2

                    update_round_data(game_id, match[0], match[1][0], match[1][1], match[2][0], match[2][1],
                                      score1_team1, score1_team2, "same")

                    break

                except Exception:

                    if attempt == max_retries - 1:
                        errors_matchups.append((match[0], team1["Name"], team2["Name"]))

        if match[4] == 1:

            for attempt in range(max_retries):

                try:

                    if attempt % 2 == 0:
                        c = " "
                    else:
                        c = ""

                    starting_message += c

                    if order == "same":

                        deal = create_chat(game_id, order, team2, team1, starting_message, num_turns, summary_prompt,
                                           match[0], user, summary_agent, summary_termination_message)

                        if deal == -1:
                            score2_team1 = 0
                            score2_team2 = 0

                        else:

                            if deal > team1["Value 2"]:
                                score2_team1 = 1
                                score2_team2 = 0

                            elif deal < team2["Value 1"]:
                                score2_team1 = 0
                                score2_team2 = 1

                            else:
                                score2_team1 = round((deal - team2["Value 1"]) / (team1["Value 2"] - team2["Value 1"]),
                                                     4)
                                score2_team2 = 1 - score2_team1

                    elif order == "opposite":

                        deal = create_chat(game_id, order, team1, team2, starting_message, num_turns, summary_prompt,
                                           match[0], user, summary_agent, summary_termination_message)

                        if deal == -1:
                            score2_team1 = 0
                            score2_team2 = 0

                        else:

                            if deal > team1["Value 1"]:
                                score2_team1 = 1
                                score2_team2 = 0

                            elif deal < team2["Value 2"]:
                                score2_team1 = 0
                                score2_team2 = 1

                            else:
                                score2_team1 = round((deal - team2["Value 2"]) / (team1["Value 1"] - team2["Value 2"]),
                                                     4)
                                score2_team2 = 1 - score2_team1

                    update_round_data(game_id, match[0], match[1][0], match[1][1], match[2][0], match[2][1],
                                      score2_team1, score2_team2, "opposite")

                    break

                except Exception:

                    if attempt == max_retries - 1:
                        errors_matchups.append((match[0], team2["Name"], team1["Name"]))

    if not errors_matchups:
        return "All negotiations were completed successfully!"

    else:

        error_message = "The following negotiations were unsuccessful:\n\n"

        for match in errors_matchups:
            error_message += f"- Round {match[0]} - {match[1]} ({name_roles[0]}) vs {match[2]} ({name_roles[1]});\n"

        return error_message
