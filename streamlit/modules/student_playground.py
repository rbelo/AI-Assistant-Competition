"""
Student Playground Module for AI Assistant Competition Platform

This module adds a playground feature to the platform, allowing students to:
1. Test their AI agents in a sandbox environment
2. Run practice negotiations with their own agents
3. Experiment with different prompts and configurations
4. View and analyze results without affecting official game scores
"""

import re

import autogen

import streamlit as st

from .database_handler import (
    get_class_from_user_id,
    get_group_id_from_user_id,
    get_playground_results,
    insert_playground_result,
)
from .negotiations import build_llm_config, is_invalid_api_key_error, is_valid_termination


# Function for cleaning dialogue messages to remove agent name prefixes
def clean_agent_message(agent_name_1, agent_name_2, message):
    if not message:  # Handle possible empty messages
        return ""

    # Define a regex pattern to match "Agent_name: " at the start of the message for either agent
    pattern = rf"^\s*(?:{re.escape(agent_name_1)}|{re.escape(agent_name_2)})\s*:\s*"

    # Use regex substitution to remove the pattern from the message
    clean_message = re.sub(pattern, "", message, flags=re.IGNORECASE)

    return clean_message


# Function to create and run test negotiations
def run_playground_negotiation(
    role1_prompt,
    role2_prompt,
    role1_name,
    role2_name,
    starting_message,
    num_turns,
    api_key,
    model="gpt-4o-mini",
    conversation_starter=None,
    negotiation_termination_message="Pleasure doing business with you",
):
    # Configure agents
    config_list = build_llm_config(model, api_key)

    # Create a closure to capture chat history
    def create_termination_check(history):
        return lambda msg: is_valid_termination(msg, history, negotiation_termination_message)

    role1_agent = autogen.ConversableAgent(
        name=f"{role1_name}",
        llm_config=config_list,
        human_input_mode="NEVER",
        chat_messages=None,
        system_message=role1_prompt
        + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about {num_turns} opportunities to intervene.",
        is_termination_msg=create_termination_check([]),
    )

    role2_agent = autogen.ConversableAgent(
        name=f"{role2_name}",
        llm_config=config_list,
        human_input_mode="NEVER",
        chat_messages=None,
        system_message=role2_prompt
        + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about {num_turns} opportunities to intervene.",
        is_termination_msg=create_termination_check([]),
    )

    # Initialize chat
    initiator = role2_agent if conversation_starter == role2_name else role1_agent
    responder = role1_agent if initiator is role2_agent else role2_agent
    chat = initiator.initiate_chat(
        responder,
        clear_history=True,
        max_turns=num_turns,
        message=starting_message,
    )

    # Update termination checks with actual chat history
    role1_agent.is_termination_msg = create_termination_check(chat.chat_history)
    role2_agent.is_termination_msg = create_termination_check(chat.chat_history)

    # Process chat history for display
    negotiation_text = ""
    for i in range(len(chat.chat_history)):
        clean_msg = clean_agent_message(role1_agent.name, role2_agent.name, chat.chat_history[i]["content"])
        formatted_msg = chat.chat_history[i]["name"] + ": " + clean_msg + "\n\n"
        negotiation_text += formatted_msg

    return negotiation_text, chat.chat_history


# Save playground negotiation results for future reference
def save_playground_results(user_id, class_, group_id, role1_name, role2_name, negotiation_text, model=None):
    return insert_playground_result(
        user_id=user_id,
        class_=class_,
        group_id=group_id,
        role1_name=role1_name,
        role2_name=role2_name,
        transcript=negotiation_text,
        model=model,
    )


# Load previous playground negotiation results
def load_playground_results(user_id, class_, group_id):
    return get_playground_results(user_id, class_, group_id)


# Main playground page function
def display_student_playground():
    st.title("AI Agent Playground")

    # Check if user is authenticated
    if not st.session_state.get("authenticated", False):
        st.warning("Please login first to access the Playground.")
        return

    # Get user details
    user_id = st.session_state.get("user_id", "")
    class_ = get_class_from_user_id(user_id)
    group_id = get_group_id_from_user_id(user_id)

    # Playground tabs
    tab1, tab2, tab3 = st.tabs(["Create Test", "My Tests", "Playground Help"])

    with tab1:
        st.header("Create New Test Negotiation")

        model_options = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-5-mini", "gpt-5-nano"]
        model_explanations = {
            "gpt-4o-mini": "Best value for negotiation: fast, low cost, strong dialog quality.",
            "gpt-4.1-mini": "More consistent reasoning while staying inexpensive.",
            "gpt-5-mini": "Higher quality reasoning at a moderate cost.",
            "gpt-5-nano": "Ultra-cheap for large batches; weakest negotiation quality.",
        }
        with st.form(key="playground_form"):
            col1, col2 = st.columns(2)

            with col1:
                role1_name = st.text_input("Role 1 Name", value="Buyer")
                role1_value = st.number_input("Role 1 Reservation Value", value=20)
                role1_prompt = st.text_area(
                    "Role 1 Prompt",
                    height=200,
                    value=f"You are a buyer negotiating to purchase an item. Your reservation value is {role1_value}, which means you won't pay more than this amount. Try to negotiate the lowest price possible.",
                )

            with col2:
                role2_name = st.text_input("Role 2 Name", value="Seller")
                role2_value = st.number_input("Role 2 Reservation Value", value=10)
                role2_prompt = st.text_area(
                    "Role 2 Prompt",
                    height=200,
                    value=f"You are a seller negotiating to sell an item. Your reservation value is {role2_value}, which means you won't accept less than this amount. Try to negotiate the highest price possible.",
                )

            st.subheader("Negotiation Settings")
            conversation_options = [f"{role1_name} ➡ {role2_name}", f"{role2_name} ➡ {role1_name}"]
            conversation_starter = st.radio(
                "Conversation Starter",
                conversation_options,
                horizontal=True,
                index=0,
                key="playground_conversation_starter",
            )
            starting_message = st.text_input("Starting Message", value="Hello, I'm interested in negotiating with you.")
            num_turns = st.slider("Maximum Turns", min_value=5, max_value=30, value=15)
            st.subheader("Run Configuration")
            model = st.selectbox(
                "Model",
                options=model_options,
                index=0,
                format_func=lambda name: f"{name} — {model_explanations.get(name, '')}",
                help="Model descriptions are shown in the dropdown. Pick the best balance of cost and quality.",
                key="playground_model",
            )
            api_key = st.text_input("OpenAI API Key", type="password")
            save_results = st.checkbox("Save Results", value=True)

            submit_button = st.form_submit_button("Run Test Negotiation")

        if submit_button:
            if not api_key:
                st.error("Please provide an OpenAI API key to run the negotiation")
                return

            with st.spinner("Running negotiation test..."):
                try:
                    negotiation_text, chat_history = run_playground_negotiation(
                        role1_prompt,
                        role2_prompt,
                        role1_name,
                        role2_name,
                        starting_message,
                        num_turns,
                        api_key,
                        model,
                        conversation_starter.split(" ➡ ")[0].strip(),
                    )

                    # Display results
                    st.success("Test negotiation completed!")
                    st.subheader("Negotiation Results")
                    st.text_area("Negotiation Transcript", negotiation_text, height=400)

                    # Save results if requested
                    if save_results:
                        result_id = save_playground_results(
                            user_id, class_, group_id, role1_name, role2_name, negotiation_text, model=model
                        )
                        if result_id:
                            st.success(f"Results saved successfully! Reference ID: {result_id}")
                        else:
                            st.error("Failed to save results.")

                except Exception as e:
                    if is_invalid_api_key_error(e):
                        st.error("Your API key appears invalid or unauthorized. Update it and try again.")
                    else:
                        st.error(f"An error occurred during the negotiation: {str(e)}")

    with tab2:
        st.header("My Previous Tests")

        # Load and display previous tests
        previous_tests = load_playground_results(user_id, class_, group_id)

        if previous_tests:
            total_tests = len(previous_tests)
            for i, test_result in enumerate(previous_tests, 1):
                run_number = total_tests - i + 1
                role_label = ""
                if test_result["role1_name"] and test_result["role2_name"]:
                    role_label = f"{test_result['role1_name']} vs {test_result['role2_name']} - "
                model_label = test_result.get("model") or "Unknown model"
                title = f"{role_label}Test Run {run_number} ({test_result['created_at']}) • {model_label}"
                with st.expander(title, expanded=i == 1):
                    st.caption(f"Model: {model_label}")
                    st.text_area(
                        "Negotiation Transcript",
                        test_result["transcript"],
                        height=400,
                        key=f"playground_test_{test_result['id']}",
                    )
        else:
            st.info("You don't have any previous playground tests. Create a new test to see results here.")

    with tab3:
        st.header("Playground Help")

        st.markdown("""
        ### How to Use the AI Agent Playground

        This playground allows you to test and refine your AI agents before submitting them to official competitions.

        #### Creating Effective Prompts

        1. **Be specific about goals**: Clearly state what your agent should try to accomplish
        2. **Define constraints**: Set reservation values and other limitations
        3. **Add context**: Provide background information that helps the agent understand the scenario
        4. **Include negotiation strategies**: Guide your agent on how to approach the negotiation

        #### Best Practices

        - Test different versions of your prompts to see which performs better
        - Try various negotiation scenarios with different reservation values
        - Analyze successful negotiations to improve your agent's performance
        - Use realistic values and constraints that match official competition settings

        #### Tips for Official Competitions

        - Prompts that perform well in the playground often translate to success in competitions
        - Balance between being too specific (limiting flexibility) and too vague (causing unpredictable behavior)
        - Consider how your agent will interact with opponents using different strategies
        """)
