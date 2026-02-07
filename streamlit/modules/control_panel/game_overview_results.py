import time

import pandas as pd

import streamlit as st

from ..database_handler import (
    fetch_and_compute_scores_for_year_game,
    get_game_simulation_params,
    get_negotiation_chat_details,
    get_round_data,
    update_access_to_chats,
)
from ..negotiation_display import render_chat_summary
from ..negotiations import extract_summary_from_transcript


def render_results_tab(selected_game: dict) -> None:
    game_id = selected_game["game_id"]
    name_roles = selected_game["name_roles"].split("#_;:)")
    name_roles_1, name_roles_2 = name_roles[0], name_roles[1]

    round_data = get_round_data(game_id)
    has_simulation = bool(round_data)
    access_state = "Enabled" if selected_game["available"] else "Disabled"
    st.write(f"Student Access: {access_state}")
    if selected_game["available"]:
        access_disabled = st.button(
            "Disable Student Access to Negotiation Chats and Leaderboard", key="cc_disable_access"
        )
        if access_disabled:
            update_access_to_chats(0, selected_game["game_id"])
            success = st.success("Student access disabled.")
            time.sleep(1)
            success.empty()
            st.rerun()
    else:
        if has_simulation:
            access_enabled = st.button(
                "Enable Student Access to Negotiation Chats and Leaderboard", key="cc_enable_access"
            )
            if access_enabled:
                update_access_to_chats(1, selected_game["game_id"])
                success = st.success("Student access enabled.")
                time.sleep(1)
                success.empty()
                st.rerun()
        else:
            st.button(
                "Enable Student Access to Negotiation Chats and Leaderboard",
                key="cc_enable_access_disabled",
                disabled=True,
            )
            st.info("Run a simulation to publish results.")

    if not round_data:
        st.write("No chats found.")
        return

    matchups = [
        (
            round_,
            class_1,
            team_1,
            class_2,
            team_2,
            score_team1_role1,
            score_team2_role2,
            score_team1_role2,
            score_team2_role1,
        )
        for round_, class_1, team_1, class_2, team_2, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1 in round_data
    ]

    def render_matchups(matchups_to_show, selected_class, selected_group_id, summary_termination_message):
        if not matchups_to_show:
            st.write("No chats found.")
            return
        for (
            round_,
            class_1,
            team_1,
            class_2,
            team_2,
            score_team1_role1,
            score_team2_role2,
            score_team1_role2,
            score_team2_role1,
        ) in matchups_to_show:
            if selected_class == class_2 and selected_group_id == team_2:
                buyer_role1 = (class_2, team_2)
                seller_role2 = (class_1, team_1)
            else:
                buyer_role1 = (class_1, team_1)
                seller_role2 = (class_2, team_2)

            buyer_details = get_negotiation_chat_details(
                game_id, round_, buyer_role1[0], buyer_role1[1], seller_role2[0], seller_role2[1]
            )
            seller_details = get_negotiation_chat_details(
                game_id, round_, seller_role2[0], seller_role2[1], buyer_role1[0], buyer_role1[1]
            )
            chat_buyer = buyer_details.get("transcript") if buyer_details else None
            chat_seller = seller_details.get("transcript") if seller_details else None

            def role_scores(
                role1_class,
                role1_team,
                role2_class,
                role2_team,
                _class_1=class_1,
                _team_1=team_1,
                _score_team1_role1=score_team1_role1,
                _score_team2_role2=score_team2_role2,
                _score_team2_role1=score_team2_role1,
                _score_team1_role2=score_team1_role2,
            ):
                if role1_class == _class_1 and role1_team == _team_1:
                    return _score_team1_role1, _score_team2_role2
                return _score_team2_role1, _score_team1_role2

            header = f"Round {round_}: Class {class_1} - Group {team_1} vs Class {class_2} - Group {team_2}"
            st.markdown(f"#### {header}")
            with st.expander(f"**{name_roles_1} chat**"):
                summary_text = buyer_details.get("summary") if buyer_details else ""
                deal_value = buyer_details.get("deal_value") if buyer_details else None
                if not summary_text and chat_buyer:
                    summary_text, deal_value = extract_summary_from_transcript(chat_buyer, summary_termination_message)
                buyer_score, seller_score = role_scores(
                    buyer_role1[0], buyer_role1[1], seller_role2[0], seller_role2[1]
                )
                render_chat_summary(
                    summary_text,
                    deal_value,
                    buyer_score,
                    seller_score,
                    name_roles_1,
                    name_roles_2,
                    chat_buyer,
                    transcript_label="View full transcript",
                    transcript_expanded=False,
                    show_heading=False,
                    transcript_key=(
                        f"chat_transcript_{game_id}_{round_}_"
                        f"{buyer_role1[0]}_{buyer_role1[1]}_"
                        f"{seller_role2[0]}_{seller_role2[1]}_role1"
                    ),
                )

            with st.expander(f"**{name_roles_2} chat**"):
                summary_text = seller_details.get("summary") if seller_details else ""
                deal_value = seller_details.get("deal_value") if seller_details else None
                if not summary_text and chat_seller:
                    summary_text, deal_value = extract_summary_from_transcript(chat_seller, summary_termination_message)
                buyer_score, seller_score = role_scores(
                    seller_role2[0], seller_role2[1], buyer_role1[0], buyer_role1[1]
                )
                render_chat_summary(
                    summary_text,
                    deal_value,
                    buyer_score,
                    seller_score,
                    name_roles_1,
                    name_roles_2,
                    chat_seller,
                    transcript_label="View full transcript",
                    transcript_expanded=False,
                    show_heading=False,
                    transcript_key=(
                        f"chat_transcript_{game_id}_{round_}_"
                        f"{seller_role2[0]}_{seller_role2[1]}_"
                        f"{buyer_role1[0]}_{buyer_role1[1]}_role2"
                    ),
                )

    st.markdown("### Leaderboard")
    leaderboard = fetch_and_compute_scores_for_year_game(game_id)
    if not leaderboard:
        st.write("No leaderboard available.")
        return

    role_labels = selected_game["name_roles"].split("#_;:)")
    role_1_label = role_labels[0]
    role_2_label = role_labels[1]
    leaderboard_with_position = [
        {
            "Class": row["team_class"],
            "Group ID": row["team_id"],
            "Games": row["total_games"],
            "Avg Rounds": row["avg_rounds_per_game"],
            "Avg Score": row["average_score"],
            f"Rank ({role_1_label})": row["position_name_roles_1"],
            f"Score ({role_1_label})": row["score_name_roles_1"],
            f"Rank ({role_2_label})": row["position_name_roles_2"],
            f"Score ({role_2_label})": row["score_name_roles_2"],
        }
        for row in leaderboard
    ]
    leaderboard_df = pd.DataFrame(
        leaderboard_with_position,
        columns=[
            "Class",
            "Group ID",
            "Games",
            "Avg Rounds",
            "Avg Score",
            f"Rank ({role_1_label})",
            f"Score ({role_1_label})",
            f"Rank ({role_2_label})",
            f"Score ({role_2_label})",
        ],
    )
    leaderboard_df["Avg Rounds"] = pd.to_numeric(leaderboard_df["Avg Rounds"], errors="coerce").round(2)
    leaderboard_df["Avg Score"] = leaderboard_df["Avg Score"].round(2)
    leaderboard_df[f"Score ({role_1_label})"] = leaderboard_df[f"Score ({role_1_label})"].round(2)
    leaderboard_df[f"Score ({role_2_label})"] = leaderboard_df[f"Score ({role_2_label})"].round(2)
    leaderboard_df.index = leaderboard_df.index + 1

    st.dataframe(
        leaderboard_df.style.format(precision=2),
        width="stretch",
        column_config={
            "Class": st.column_config.TextColumn(width="small"),
            "Group ID": st.column_config.NumberColumn(width="small"),
            "Games": st.column_config.NumberColumn(width="small", help="Total games played"),
            "Avg Rounds": st.column_config.NumberColumn(width="small", help="Average rounds per game"),
            "Avg Score": st.column_config.NumberColumn(width="small", help="Average score across games"),
            f"Rank ({role_1_label})": st.column_config.NumberColumn(width="small"),
            f"Score ({role_1_label})": st.column_config.NumberColumn(width="small"),
            f"Rank ({role_2_label})": st.column_config.NumberColumn(width="small"),
            f"Score ({role_2_label})": st.column_config.NumberColumn(width="small"),
        },
    )

    group_options = [f"Class {row['team_class']} - Group {row['team_id']}" for row in leaderboard]
    selected_group = st.selectbox("Select Group to Review Chats", group_options, key="cc_results_lb_group_select")
    class_ = selected_group.split("Class ")[1].split(" - ")[0]
    group_id = int(selected_group.split("Group ")[1])
    group_matchups = [
        m for m in matchups if (m[1] == class_ and m[2] == group_id) or (m[3] == class_ and m[4] == group_id)
    ]
    simulation_params = get_game_simulation_params(game_id)
    summary_termination_message = (
        simulation_params.get("summary_termination_message") if simulation_params else "The value agreed was"
    )
    render_matchups(group_matchups, class_, group_id, summary_termination_message)
