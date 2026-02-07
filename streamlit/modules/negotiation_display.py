import streamlit as st


def _escape_markdown_currency(text: str) -> str:
    """Prevent Streamlit markdown from treating $...$ as LaTeX math."""
    return text.replace("$", r"\$")


def render_chat_summary(
    summary_text,
    deal_value,
    score_role1,
    score_role2,
    role1_label,
    role2_label,
    transcript,
    summary_label="Negotiation Summary",
    transcript_label="View full transcript",
    transcript_expanded=False,
    show_heading=True,
    transcript_key=None,
):
    if show_heading:
        st.subheader(summary_label)

    if summary_text:
        st.write(_escape_markdown_currency(summary_text))
    else:
        st.info("Summary unavailable for this chat.")

    if deal_value is None:
        st.info("No deal value could be parsed for scoring.")
    elif deal_value == -1 or score_role1 in (None, -1) or score_role2 in (None, -1):
        st.info("No valid agreement detected.")
        col1, col2 = st.columns(2)
        col1.metric(f"{role1_label} Score", "0.0")
        col2.metric(f"{role2_label} Score", "0.0")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Agreed Value", f"{deal_value:.2f}")
        col2.metric(f"{role1_label} Score", f"{score_role1 * 100:.1f}")
        col3.metric(f"{role2_label} Score", f"{score_role2 * 100:.1f}")
        st.caption(f"Scores assume {role1_label} is the minimizer and {role2_label} is the maximizer.")

    with st.expander(transcript_label, expanded=transcript_expanded):
        if transcript:
            st.text_area(
                "Negotiation Transcript",
                transcript,
                height=400,
                key=transcript_key,
            )
        else:
            st.write("Chat not found.")
