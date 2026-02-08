import re

from modules.auth_guard import ensure_session_defaults, require_auth

import streamlit as st

# Set page configuration
st.set_page_config(page_title="AI Assistant Playground", page_icon="🧪")
ensure_session_defaults()
require_auth("Playground")

from modules.sidebar import render_sidebar

render_sidebar(current_page="playground")

NEGOTIATION_TERMINATION_MESSAGE = "Pleasure doing business with you"
SUMMARY_TERMINATION_MESSAGE = "Agreed value:"
SUMMARY_PROMPT = "Summarize the negotiation and determine if there was a valid agreement."

try:
    from modules.conversation_engine import ConversationEngine, GameAgent
    from modules.database_handler import (
        delete_all_playground_results,
        delete_playground_result,
        get_class_from_user_id,
        get_group_id_from_user_id,
        get_playground_results,
        get_user_api_key,
        insert_playground_result,
        list_user_api_keys,
    )
    from modules.llm_models import MODEL_EXPLANATIONS, MODEL_OPTIONS
    from modules.negotiation_display import render_chat_summary
    from modules.negotiations_common import (
        build_llm_config,
        compute_deal_scores,
        is_invalid_api_key_error,
    )
    from modules.negotiations_summary import build_summary_agent, evaluate_deal_summary
except Exception as exc:
    st.title("AI Agent Playground")
    st.error("Playground dependencies failed to load. Please contact the app admin.")
    st.caption(f"Technical details: {exc}")
    st.stop()


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
    num_turns,
    api_key,
    model="gpt-5-mini",
    conversation_starter=None,
    negotiation_termination_message=NEGOTIATION_TERMINATION_MESSAGE,
):
    # Configure engine
    llm_config = build_llm_config(model, api_key)
    engine = ConversationEngine(llm_config)

    role1_agent = GameAgent(
        name=f"{role1_name}",
        system_message=role1_prompt
        + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about {num_turns} opportunities to intervene.",
    )

    role2_agent = GameAgent(
        name=f"{role2_name}",
        system_message=role2_prompt
        + f" When the negotiation is finished, say {negotiation_termination_message}. This is a short conversation, you will have about {num_turns} opportunities to intervene.",
    )

    # Determine initiator and responder
    initiator = role2_agent if conversation_starter == role2_name else role1_agent
    responder = role1_agent if initiator is role2_agent else role2_agent

    def termination_fn(msg, history):
        return negotiation_termination_message in msg["content"]

    chat = engine.run_bilateral(initiator, responder, num_turns, termination_fn)

    # Process chat history for display
    negotiation_text = ""
    for entry in chat.chat_history:
        clean_msg = clean_agent_message(role1_agent.name, role2_agent.name, entry["content"])
        formatted_msg = entry["name"] + ": " + clean_msg + "\n\n"
        negotiation_text += formatted_msg

    return negotiation_text, chat.chat_history


# Save playground negotiation results for future reference
def save_playground_results(
    user_id,
    class_,
    group_id,
    role1_name,
    role2_name,
    negotiation_text,
    summary=None,
    deal_value=None,
    score_role1=None,
    score_role2=None,
    model=None,
):
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
        model=model,
    )


# Search and load previous playground negotiation results
def find_playground_results(class_, group_id):
    user_id = st.session_state.get("user_id", "")
    return get_playground_results(user_id, class_, group_id)


# Get user details
user_id = st.session_state.get("user_id", "")
class_ = get_class_from_user_id(user_id)
group_id = get_group_id_from_user_id(user_id)

st.title("AI Agent Playground")
st.write("Test and refine your AI agents in this sandbox environment before submitting them to official competitions.")

# Playground tabs
tab1, tab2, tab3 = st.tabs(["Create Test", "My Tests", "Playground Help"])

with tab1:
    st.header("Create New Test Negotiation")
    model_options = MODEL_OPTIONS
    model_explanations = MODEL_EXPLANATIONS
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
    current_starter = st.session_state.get("playground_conversation_starter")
    if current_starter not in conversation_options:
        st.session_state["playground_conversation_starter"] = conversation_options[0]
    conversation_starter = st.radio(
        "Conversation Starter",
        conversation_options,
        horizontal=True,
        key="playground_conversation_starter",
    )
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
    saved_keys = list_user_api_keys(user_id)
    key_options = {key["key_name"]: key["key_id"] for key in saved_keys}
    has_keys = bool(key_options)
    selected_key_id = None
    if has_keys:
        selected_label = st.selectbox(
            "API Key",
            options=list(key_options.keys()),
            key="playground_api_key_select",
        )
        selected_key_id = key_options[selected_label]
    else:
        st.info("No API keys saved. Add one in Profile to run a playground test.")
    save_results = st.checkbox("Save Results", value=True)

    submit_button = st.button("Run Test Negotiation", disabled=not has_keys, key="playground_run_test")

    if submit_button:
        resolved_api_key = None
        if selected_key_id:
            resolved_api_key = get_user_api_key(user_id, selected_key_id)
        if not resolved_api_key:
            st.error("Please select an API key in Profile before running the negotiation.")
            st.stop()
        with st.spinner("Running negotiation test..."):
            try:
                negotiation_text, chat_history = run_playground_negotiation(
                    role1_prompt,
                    role2_prompt,
                    role1_name,
                    role2_name,
                    num_turns,
                    resolved_api_key,
                    model,
                    conversation_starter.split(" ➡ ")[0].strip(),
                    NEGOTIATION_TERMINATION_MESSAGE,
                )
                summary_text = ""
                deal_value = None
                try:
                    summary_llm_config = build_llm_config(model, resolved_api_key)
                    summary_engine = ConversationEngine(summary_llm_config)
                    summary_agent = build_summary_agent(
                        SUMMARY_TERMINATION_MESSAGE,
                        NEGOTIATION_TERMINATION_MESSAGE,
                        include_summary=True,
                    )
                    summary_text, deal_value = evaluate_deal_summary(
                        summary_engine,
                        chat_history,
                        SUMMARY_PROMPT,
                        SUMMARY_TERMINATION_MESSAGE,
                        summary_agent,
                        role1_name,
                        role2_name,
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
                st.success("Test negotiation completed.")
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
                    transcript_key="playground_latest_transcript",
                )

                # Save results if requested
                if save_results:
                    result_id = save_playground_results(
                        user_id,
                        class_,
                        group_id,
                        role1_name,
                        role2_name,
                        negotiation_text,
                        summary_text,
                        deal_value,
                        score_role1,
                        score_role2,
                        model=model,
                    )
                    if result_id:
                        st.success("Results saved.")
                    else:
                        st.error("Failed to save results.")
            except Exception as e:
                if is_invalid_api_key_error(e):
                    st.error("Your API key appears invalid or unauthorized. Update it in Profile and try again.")
                else:
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
        total_tests = len(previous_tests)
        for i, test_result in enumerate(previous_tests, 1):
            run_number = total_tests - i + 1
            role_label = ""
            if test_result["role1_name"] and test_result["role2_name"]:
                role_label = f"{test_result['role1_name']} vs {test_result['role2_name']} - "
            model_label = test_result.get("model") or "Unknown model"
            created_at = test_result["created_at"]
            if hasattr(created_at, "replace"):
                created_at = created_at.replace(microsecond=0)
            title = f"{role_label}Test Run {run_number} ({created_at}) • {model_label}"
            with st.expander(title, expanded=i == 1):
                st.caption(f"Model: {model_label}")
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
                    transcript_key=f"playground_test_transcript_{test_result['id']}",
                )
    else:
        st.info(
            "You don't have any previous playground tests. "
            "Create a new test in the 'Create Test' tab to experiment with prompts and see results here."
        )

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
    - API keys must be added in your Profile before running tests
    - Your test results can be saved for future reference
    """)
