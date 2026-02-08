import streamlit as st

from .database_handler import get_group_values, get_negotiation_chat_details
from .negotiations_summary import extract_summary_from_transcript


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
    role1_reservation=None,
    role2_reservation=None,
    value_position_key=None,
    viewer_label="You",
    viewer_score=None,
):
    def _viewer_prefix(label):
        normalized = str(label).strip().lower() if label is not None else ""
        if normalized == "you" or not normalized:
            return "You"
        return f"You ({label})"

    if show_heading:
        st.subheader(summary_label)

    if summary_text:
        st.write(_escape_markdown_currency(summary_text))
    else:
        st.info("Summary unavailable for this chat.")

    def _viewer_margin_extraction(viewer_score):
        if viewer_score is None:
            return None, None
        viewer_raw = viewer_score * 100.0
        viewer_clamped = min(100.0, max(0.0, viewer_raw))
        return viewer_raw, viewer_clamped

    def _render_value_slider(reservation_a, reservation_b, agreed_value):
        if reservation_a is None or reservation_b is None or agreed_value is None:
            return
        slider_min = min(reservation_a, reservation_b, agreed_value)
        slider_max = max(reservation_a, reservation_b, agreed_value)
        if slider_min == slider_max:
            slider_min -= 1.0
            slider_max += 1.0

        st.slider(
            "",
            min_value=float(slider_min),
            max_value=float(slider_max),
            value=float(agreed_value),
            disabled=True,
            key=value_position_key,
            label_visibility="collapsed",
        )

        left_label, left_value = (
            (f"{role1_label} Reservation", role1_reservation)
            if role1_reservation <= role2_reservation
            else (f"{role2_label} Reservation", role2_reservation)
        )
        right_label, right_value = (
            (f"{role2_label} Reservation", role2_reservation)
            if role1_reservation <= role2_reservation
            else (f"{role1_label} Reservation", role1_reservation)
        )
        col1, col2 = st.columns(2)
        col1.markdown(
            (
                "<div style='text-align: left; color: rgba(49, 51, 63, 0.6); "
                f"font-size: 0.875rem;'>{left_label}: {left_value:.2f}</div>"
            ),
            unsafe_allow_html=True,
        )
        col2.markdown(
            (
                "<div style='text-align: right; color: rgba(49, 51, 63, 0.6); "
                f"font-size: 0.875rem;'>{right_label}: {right_value:.2f}</div>"
            ),
            unsafe_allow_html=True,
        )

    if deal_value is None:
        st.info("No valid agreement detected.")
        if role1_reservation is not None and role2_reservation is not None:
            low_label, low_value = (
                (f"{role1_label} Reservation", role1_reservation)
                if role1_reservation <= role2_reservation
                else (f"{role2_label} Reservation", role2_reservation)
            )
            high_label, high_value = (
                (f"{role2_label} Reservation", role2_reservation)
                if role1_reservation <= role2_reservation
                else (f"{role1_label} Reservation", role1_reservation)
            )
            col_left, col_right = st.columns(2)
            col_left.markdown(
                (
                    "<div style='text-align: left; color: rgba(49, 51, 63, 0.6); "
                    f"font-size: 0.875rem;'>{low_label}: {low_value:.2f}</div>"
                ),
                unsafe_allow_html=True,
            )
            col_right.markdown(
                (
                    "<div style='text-align: right; color: rgba(49, 51, 63, 0.6); "
                    f"font-size: 0.875rem;'>{high_label}: {high_value:.2f}</div>"
                ),
                unsafe_allow_html=True,
            )
            margin = abs(role2_reservation - role1_reservation)
            if margin == 0:
                st.caption("There was no negotiation margin between the reservation values.")
            else:
                st.caption("No agreement was reached, despite a positive negotiation margin.")
        col1, col2 = st.columns(2)
        col1.metric(f"{role1_label} Score", "0")
        col2.metric(f"{role2_label} Score", "0")
    else:
        viewer_score = viewer_score if viewer_score is not None else score_role1
        viewer_raw, viewer_clamped = _viewer_margin_extraction(viewer_score)
        st.write(f"**Agreed Value:** {deal_value:.2f}")
        if viewer_clamped is not None:
            viewer_prefix = _viewer_prefix(viewer_label)
            if viewer_raw is not None and viewer_raw > 100:
                st.caption(f"{viewer_prefix} extracted more than 100% of the negotiation margin.")
            elif viewer_raw is not None and viewer_raw < 0:
                st.caption(f"{viewer_prefix} extracted less than 0% of the negotiation margin.")
            else:
                st.caption(f"{viewer_prefix} extracted {viewer_clamped:.0f}% of the negotiation margin.")
        _render_value_slider(role1_reservation, role2_reservation, deal_value)
        col1, col2 = st.columns(2)
        col1.metric(f"{role1_label} Score", f"{score_role1 * 100:.0f}")
        col2.metric(f"{role2_label} Score", f"{score_role2 * 100:.0f}")
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


def render_matchup_chats(
    game_id,
    round_number,
    class_1,
    team_1,
    class_2,
    team_2,
    score_team1_role1,
    score_team2_role2,
    score_team1_role2,
    score_team2_role1,
    name_roles_1,
    name_roles_2,
    summary_termination_message,
    transcript_key_prefix,
    focus_class=None,
    focus_group=None,
    viewer_label="Selected group",
    reservation_cache=None,
):
    def _same_team(team_class_a, team_group_a, team_class_b, team_group_b):
        return str(team_class_a) == str(team_class_b) and str(team_group_a) == str(team_group_b)

    def role_scores(role1_class, role1_team_id):
        if role1_class == class_1 and role1_team_id == team_1:
            return score_team1_role1, score_team2_role2
        return score_team2_role1, score_team1_role2

    if reservation_cache is None:
        reservation_cache = {}

    def _reservation_for(team_class, team_id):
        key = (game_id, str(team_class), str(team_id))
        if key not in reservation_cache:
            reservation_cache[key] = get_group_values(game_id, team_class, team_id)
        return reservation_cache[key]

    def reservation_values(role1_class, role1_team_id, role2_class, role2_team_id):
        role1_group_values = _reservation_for(role1_class, role1_team_id)
        role2_group_values = _reservation_for(role2_class, role2_team_id)
        if not role1_group_values or not role2_group_values:
            return None, None
        return role1_group_values.get("minimizer_value"), role2_group_values.get("maximizer_value")

    def build_chat_context(role1_team, role2_team, key_suffix):
        details = get_negotiation_chat_details(
            game_id, round_number, role1_team[0], role1_team[1], role2_team[0], role2_team[1]
        )
        transcript = details.get("transcript") if details else None
        score_for_role1, score_for_role2 = role_scores(role1_team[0], role1_team[1])
        role1_reservation, role2_reservation = reservation_values(
            role1_team[0], role1_team[1], role2_team[0], role2_team[1]
        )
        return {
            "role1_team": role1_team,
            "role2_team": role2_team,
            "details": details,
            "transcript": transcript,
            "score_role1": score_for_role1,
            "score_role2": score_for_role2,
            "role1_reservation": role1_reservation,
            "role2_reservation": role2_reservation,
            "key_suffix": key_suffix,
        }

    def render_chat_context(chat):
        role1_team = chat["role1_team"]
        role2_team = chat["role2_team"]
        details = chat["details"]
        transcript = chat["transcript"]
        score_for_role1 = chat["score_role1"]
        score_for_role2 = chat["score_role2"]
        role1_reservation = chat["role1_reservation"]
        role2_reservation = chat["role2_reservation"]
        key_suffix = chat["key_suffix"]

        if focus_class is not None and _same_team(focus_class, focus_group, role1_team[0], role1_team[1]):
            header_role_name = name_roles_1
            header_team = role1_team
            header_opponent_team = role2_team
            message_role_name = name_roles_1
            message_score = score_for_role1
        elif focus_class is not None and _same_team(focus_class, focus_group, role2_team[0], role2_team[1]):
            header_role_name = name_roles_2
            header_team = role2_team
            header_opponent_team = role1_team
            message_role_name = name_roles_2
            message_score = score_for_role2
        else:
            header_role_name = name_roles_1
            header_team = role1_team
            header_opponent_team = None
            message_role_name = viewer_label
            message_score = score_for_role1

        if header_opponent_team is not None:
            header_context = f"(vs Class {header_opponent_team[0]} • Group {header_opponent_team[1]})"
        else:
            header_context = f"(Class {header_team[0]} • Group {header_team[1]})"

        with st.expander(f"**{header_role_name} chat {header_context}**"):
            summary_text = details.get("summary") if details else ""
            deal_value = details.get("deal_value") if details else None
            if not summary_text and transcript:
                summary_text, deal_value = extract_summary_from_transcript(transcript, summary_termination_message)

            render_chat_summary(
                summary_text,
                deal_value,
                score_for_role1,
                score_for_role2,
                name_roles_1,
                name_roles_2,
                transcript,
                transcript_label="View full transcript",
                transcript_expanded=False,
                show_heading=False,
                transcript_key=f"{transcript_key_prefix}_{key_suffix}_transcript",
                role1_reservation=role1_reservation,
                role2_reservation=role2_reservation,
                value_position_key=f"{transcript_key_prefix}_{key_suffix}_value_position",
                viewer_label=message_role_name,
                viewer_score=message_score,
            )

    chat_role1_to_role2 = build_chat_context((class_1, team_1), (class_2, team_2), "role1")
    chat_role2_to_role1 = build_chat_context((class_2, team_2), (class_1, team_1), "role2")

    if focus_class is not None and _same_team(focus_class, focus_group, class_2, team_2):
        ordered_chats = [chat_role2_to_role1, chat_role1_to_role2]
    else:
        ordered_chats = [chat_role1_to_role2, chat_role2_to_role1]

    for chat in ordered_chats:
        render_chat_context(chat)
