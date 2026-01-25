import streamlit as st
import re
import autogen
from modules.database_handler import get_group_id_from_user_id, get_class_from_user_id, insert_playground_result, get_playground_results
from modules.database_handler import delete_playground_result, delete_all_playground_results
from modules.database_handler import get_instructor_api_key, upsert_instructor_api_key
from modules.negotiations import (
    is_valid_termination,
    compute_deal_scores,
    build_summary_agents,
    evaluate_deal_summary,
)
from modules.negotiation_display import render_chat_summary
from modules.sidebar import render_sidebar

# Set page configuration
st.set_page_config(page_title="AI Assistant Playground", page_icon="🧪")

render_sidebar()

NEGOTIATION_TERMINATION_MESSAGE = "Pleasure doing business with you"
SUMMARY_TERMINATION_MESSAGE = "The value agreed was"
SUMMARY_PROMPT = "Summarize the negotiation and determine if there was a valid agreement."


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
                               negotiation_termination_message=NEGOTIATION_TERMINATION_MESSAGE):
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
                            negotiation_text, summary=None, deal_value=None,
                            score_role1=None, score_role2=None):
    return insert_playground_result(
        user_id=user_id,
        class_=class_,
        group_id=group_id,
        role1_name=role1_name,
        role2_name=role2_name,
        transcript=negotiation_text,
        summary=summary,
        deal_value=deal_value,
        score_role1=score_role1,
        score_role2=score_role2,
    )


# Search and load previous playground negotiation results
def find_playground_results(class_, group_id):
    user_id = st.session_state.get('user_id', '')
    return get_playground_results(user_id, class_, group_id)


# Check if the user is authenticated
if not st.session_state.get('authenticated', False):
    st.title("AI Agent Playground")
    st.warning("Please login first to access the Playground.")
else:
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
            saved_api_key = get_instructor_api_key(user_id)
            use_saved_api_key = st.checkbox(
                "Use saved API key",
                value=bool(saved_api_key),
                key="playground_use_saved_api_key",
            )
            api_key_key = "playground_api_key"
            if use_saved_api_key and saved_api_key:
                if st.session_state.get(api_key_key) != saved_api_key:
                    st.session_state[api_key_key] = saved_api_key
            elif st.session_state.get(api_key_key) == saved_api_key:
                st.session_state[api_key_key] = ""
            api_key = st.text_input("OpenAI API Key", type="password", key=api_key_key)
            save_api_key = st.checkbox("Save API key", value=False, key="playground_save_api_key")
            save_results = st.checkbox("Save Results", value=True)

            submit_button = st.form_submit_button("Run Test Negotiation")

        if submit_button:
            resolved_api_key = api_key or (saved_api_key if use_saved_api_key else "")
            if not resolved_api_key:
                st.error("Please provide an OpenAI API key to run the negotiation")
            else:
                with st.spinner("Running negotiation test..."):
                    try:
                        if save_api_key and api_key:
                            if not upsert_instructor_api_key(user_id, api_key):
                                st.error("Failed to save API key. Check API_KEY_ENCRYPTION_KEY.")
                        negotiation_text, chat_history = run_playground_negotiation(
                            role1_prompt, role2_prompt, role1_name, role2_name,
                            starting_message, num_turns, resolved_api_key, model,
                            NEGOTIATION_TERMINATION_MESSAGE
                        )
                        summary_text = ""
                        deal_value = None
                        try:
                            summary_config = {"config_list": [{"model": model, "api_key": resolved_api_key}],
                                              "temperature": 0.3, "top_p": 0.5}
                            user, summary_agent = build_summary_agents(
                                summary_config,
                                SUMMARY_TERMINATION_MESSAGE,
                                NEGOTIATION_TERMINATION_MESSAGE,
                                include_summary=True,
                            )
                            summary_text, deal_value = evaluate_deal_summary(
                                chat_history,
                                SUMMARY_PROMPT,
                                SUMMARY_TERMINATION_MESSAGE,
                                user,
                                summary_agent,
                                role1_name=role1_name,
                                role2_name=role2_name,
                                history_size=None,
                            )
                        except Exception:
                            st.warning("Summary generation failed for this run.")

                        score_role1 = None
                        score_role2 = None
                        if deal_value is not None:
                            score_role2, score_role1 = compute_deal_scores(
                                deal_value,
                                role2_value,
                                role1_value,
                            )

                        # Display results
                        st.success("Test negotiation completed!")
                        st.subheader("Negotiation Results")
                        render_chat_summary(
                            summary_text,
                            deal_value,
                            score_role1,
                            score_role2,
                            role1_name,
                            role2_name,
                            negotiation_text,
                            transcript_label="View full transcript",
                            transcript_expanded=True,
                        )

                        # Save results if requested
                        if save_results:
                            result_id = save_playground_results(
                                user_id, class_, group_id, role1_name, role2_name,
                                negotiation_text, summary_text, deal_value,
                                score_role1, score_role2
                            )
                            if result_id:
                                st.success(f"Results saved successfully! Reference ID: {result_id}")
                            else:
                                st.error("Failed to save results.")

                    except Exception as e:
                        st.error(f"An error occurred during the negotiation: {str(e)}")

    with tab2:
        st.header("My Previous Tests")
        st.caption("Only the last 20 tests are kept.")

        # Check for and display previous tests
        previous_tests = find_playground_results(class_, group_id)

        if previous_tests:
            @st.dialog("Clear all tests")
            def confirm_clear_all():
                st.warning("This will permanently delete all your saved tests.")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Confirm clear", key="playground_clear_confirm_btn"):
                        if delete_all_playground_results(user_id, class_, group_id):
                            st.success("All tests cleared.")
                            st.rerun()
                        else:
                            st.error("Failed to clear tests.")
                with col2:
                    if st.button("Cancel", key="playground_clear_cancel"):
                        st.rerun()

            if st.button("Clear All", key="playground_clear_all"):
                confirm_clear_all()
            for i, test_result in enumerate(previous_tests, 1):
                role_label = ""
                if test_result["role1_name"] and test_result["role2_name"]:
                    role_label = f"{test_result['role1_name']} vs {test_result['role2_name']} - "
                created_at = test_result["created_at"]
                if hasattr(created_at, "replace"):
                    created_at = created_at.replace(microsecond=0)
                title = f"{role_label}Test Run {i} ({created_at})"
                with st.expander(title, expanded=i == 1):
                    if st.button("Delete Test", key=f"delete_test_{test_result['id']}"):
                        if delete_playground_result(test_result["id"], user_id, class_, group_id):
                            st.success("Test deleted.")
                            st.rerun()
                        else:
                            st.error("Failed to delete test.")
                    render_chat_summary(
                        test_result.get("summary"),
                        test_result.get("deal_value"),
                        test_result.get("score_role1"),
                        test_result.get("score_role2"),
                        test_result.get("role1_name") or "Role 1",
                        test_result.get("role2_name") or "Role 2",
                        test_result.get("transcript"),
                        transcript_label="View full transcript",
                        transcript_expanded=False,
                        show_heading=False,
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
        - Study successful negotiations to identify patterns that lead to good outcomes

        #### Technical Notes

        - The playground uses the same underlying technology as the official competition
        - API keys are required for testing but are never stored by the system
        - Your test results can be saved for future reference
        """)
