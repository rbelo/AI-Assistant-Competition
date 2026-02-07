import autogen

from .database_handler import get_student_prompt
from .negotiations_common import is_valid_termination


def create_agents(game_id, teams, values, name_roles, config_list, negotiation_termination_message):
    team_info = []

    role_1, role_2 = name_roles[0].replace(" ", ""), name_roles[1].replace(" ", "")
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

            def create_termination_check(history):
                return lambda msg: is_valid_termination(msg, history, negotiation_termination_message)

            new_team = {
                "Name": f"Class{team[0]}_Group{team[1]}",
                "Value 1": value1,
                "Value 2": value2,
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
