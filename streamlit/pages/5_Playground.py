import streamlit as st
import pandas as pd
import time
import re
import autogen
import random
from datetime import datetime
import hashlib
from modules.database_handler import get_group_id_from_user_id, get_class_from_user_id
from modules.drive_file_manager import get_text_from_file_without_timestamp, overwrite_text_file, upload_text_as_file, find_and_delete
from modules.negotiations import is_valid_termination

# Set page configuration
st.set_page_config(page_title="AI Assistant Playground", page_icon="🧪")


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
def run_playground_negotiation(role1_prompt, role2_prompt, role1_name, role2_name,
                               starting_message, num_turns, api_key, model="gpt-4o-mini",
                               negotiation_termination_message="Pleasure doing business with you"):
    # Configure agents
    config_list = {"config_list": [{"model": model, "api_key": api_key}],
                   "temperature": 0.3, "top_p": 0.5}

    # Create a closure to capture chat history
    def create_termination_check(history):
        return lambda msg: is_valid_termination(msg, history, negotiation_termination_message)

    role1_agent = autogen.ConversableAgent(
        name=f"{role1_name}",
        llm_config=config_list,
        human_input_mode="NEVER",
        chat_messages=None,
        system_message=role1_prompt + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about {num_turns} opportunities to intervene.",
        is_termination_msg=create_termination_check([])
    )

    role2_agent = autogen.ConversableAgent(
        name=f"{role2_name}",
        llm_config=config_list,
        human_input_mode="NEVER",
        chat_messages=None,
        system_message=role2_prompt + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about {num_turns} opportunities to intervene.",
        is_termination_msg=create_termination_check([])
    )

    # Initialize chat
    chat = role1_agent.initiate_chat(
        role2_agent,
        clear_history=True,
        max_turns=num_turns,
        message=starting_message
    )

    # Update termination checks with actual chat history
    role1_agent.is_termination_msg = create_termination_check(chat.chat_history)
    role2_agent.is_termination_msg = create_termination_check(chat.chat_history)

    # Process chat history for display
    negotiation_text = ""
    for i in range(len(chat.chat_history)):
        clean_msg = clean_agent_message(role1_agent.name, role2_agent.name,
                                        chat.chat_history[i]['content'])
        formatted_msg = chat.chat_history[i]['name'] + ': ' + clean_msg + '\n\n'
        negotiation_text += formatted_msg

    return negotiation_text, chat.chat_history


# Save playground negotiation results for future reference
def save_playground_results(user_id, class_, group_id, role1_name, role2_name,
                            negotiation_text):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"Playground_Class{class_}_Group{group_id}_{timestamp}"
    overwrite_text_file(negotiation_text, filename, remove_timestamp=False)
    return filename


# Search and load previous playground negotiation results
def find_playground_results(class_, group_id):
    pattern = f"Playground_Class{class_}_Group{group_id}"
    return get_text_from_file_without_timestamp(pattern)


# Check if the user is authenticated
if not st.session_state.get('authenticated', False):
    st.title("AI Agent Playground")
    st.warning("Please login first to access the Playground.")
else:
    # Create sign-out button
    _, _, col3 = st.columns([2, 8, 2])
    with col3:
        sign_out_btn = st.button("Sign Out", key="sign_out", use_container_width=True)

        if sign_out_btn:
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.cache_resource.clear()
            st.switch_page("0_Home.py")  # Redirect to home page

    # Get user details
    user_id = st.session_state.get('user_id', '')
    class_ = get_class_from_user_id(user_id)
    group_id = get_group_id_from_user_id(user_id)

    st.title("AI Agent Playground")
    st.write(
        "Test and refine your AI agents in this sandbox environment before submitting them to official competitions.")

    # Playground tabs
    tab1, tab2, tab3 = st.tabs(["Create Test", "My Tests", "Playground Help"])

    with tab1:
        st.header("Create New Test Negotiation")

        with st.form(key="playground_form"):
            col1, col2 = st.columns(2)

            with col1:
                role1_name = st.text_input("Role 1 Name", value="Buyer")
                role1_value = st.number_input("Role 1 Reservation Value", value=20)
                role1_prompt = st.text_area("Role 1 Prompt", height=200,
                                            value=f"You are a buyer negotiating to purchase an item. Your reservation value is {role1_value}, which means you won't pay more than this amount. Try to negotiate the lowest price possible.")

            with col2:
                role2_name = st.text_input("Role 2 Name", value="Seller")
                role2_value = st.number_input("Role 2 Reservation Value", value=10)
                role2_prompt = st.text_area("Role 2 Prompt", height=200,
                                            value=f"You are a seller negotiating to sell an item. Your reservation value is {role2_value}, which means you won't accept less than this amount. Try to negotiate the highest price possible.")

            st.subheader("Negotiation Settings")
            starting_message = st.text_input("Starting Message", value="Hello, I'm interested in negotiating with you.")
            num_turns = st.slider("Maximum Turns", min_value=5, max_value=30, value=15)
            model = st.selectbox("Model", options=["gpt-4o-mini", "gpt-4o"], index=0)
            api_key = st.text_input("OpenAI API Key", type="password")
            save_results = st.checkbox("Save Results", value=True)

            submit_button = st.form_submit_button("Run Test Negotiation")

        if submit_button:
            if not api_key:
                st.error("Please provide an OpenAI API key to run the negotiation")
            else:
                with st.spinner("Running negotiation test..."):
                    try:
                        negotiation_text, chat_history = run_playground_negotiation(
                            role1_prompt, role2_prompt, role1_name, role2_name,
                            starting_message, num_turns, api_key, model
                        )

                        # Display results
                        st.success("Test negotiation completed!")
                        st.subheader("Negotiation Results")
                        st.text_area("Negotiation Transcript", negotiation_text, height=400)

                        # Save results if requested
                        if save_results:
                            filename = save_playground_results(
                                user_id, class_, group_id, role1_name, role2_name,
                                negotiation_text
                            )
                            st.success(f"Results saved successfully! Reference ID: {filename}")

                    except Exception as e:
                        st.error(f"An error occurred during the negotiation: {str(e)}")

    with tab2:
        st.header("My Previous Tests")

        # Check for and display previous tests
        previous_tests = find_playground_results(class_, group_id)

        if previous_tests:
            # Split the combined test results by the separator
            test_results = previous_tests.split("\n\n---\n\n")
            
            # Display each test result in an expander
            for i, test_result in enumerate(test_results, 1):
                with st.expander(f"Test Run {i}", expanded=i==1):
                    st.text_area("Negotiation Transcript", test_result, height=400, key=f"test_{i}")
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
        - Study successful negotiations to identify patterns that lead to good outcomes

        #### Technical Notes

        - The playground uses the same underlying technology as the official competition
        - API keys are required for testing but are never stored by the system
        - Your test results can be saved for future reference
        """)