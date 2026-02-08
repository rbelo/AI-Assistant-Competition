import pandas as pd

import streamlit as st

from ..control_panel_ui_helpers import format_game_selector_label
from ..database_handler import (
    fetch_and_compute_scores_for_game_ids,
    fetch_and_compute_scores_for_year_game,
    fetch_games_data,
)
from .game_overview_results import render_results_tab
from .game_overview_setup import render_setup_tab
from .game_overview_simulation import render_simulation_tab
from .game_overview_submissions import render_submissions_tab


def _render_leaderboard_table(
    leaderboard,
    role_1_label="Minimizer Role",
    role_2_label="Maximizer Role",
):
    if not leaderboard:
        st.info("No leaderboard data available.")
        return

    rows = [
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
    df = pd.DataFrame(
        rows,
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
    df["Avg Rounds"] = pd.to_numeric(df["Avg Rounds"], errors="coerce").round(2)
    df["Avg Score"] = df["Avg Score"].round(2)
    df[f"Score ({role_1_label})"] = df[f"Score ({role_1_label})"].round(2)
    df[f"Score ({role_2_label})"] = df[f"Score ({role_2_label})"].round(2)
    df.index = df.index + 1
    st.dataframe(
        df.style.format(precision=2),
        width="stretch",
        column_config={
            "Class": st.column_config.TextColumn(width="small"),
            "Group ID": st.column_config.NumberColumn(width="small"),
            "Games": st.column_config.NumberColumn(width="small", help="Total games played"),
            "Avg Rounds": st.column_config.NumberColumn(width="small", help="Average rounds per game"),
            "Avg Score": st.column_config.NumberColumn(width="small", help="Average score across selected games"),
            f"Rank ({role_1_label})": st.column_config.NumberColumn(width="small"),
            f"Score ({role_1_label})": st.column_config.NumberColumn(width="small"),
            f"Rank ({role_2_label})": st.column_config.NumberColumn(width="small"),
            f"Score ({role_2_label})": st.column_config.NumberColumn(width="small"),
        },
    )


def render_game_overview_tab() -> None:
    if st.session_state.cc_pending_selected_year:
        st.session_state.cc_selected_year = st.session_state.cc_pending_selected_year
        st.session_state.cc_pending_selected_year = None
    if st.session_state.cc_pending_selected_game:
        st.session_state.cc_selected_game = st.session_state.cc_pending_selected_game
        st.session_state.cc_pending_selected_game = None

    possible_years = fetch_games_data(get_academic_years=True)
    if not possible_years:
        st.info("No games found yet. Create your first game in the Create Game tab.")
        return

    year_options = ["All"] + possible_years
    selected_year = st.selectbox("Academic Year", year_options, key="cc_selected_year")

    if selected_year == "All":
        games_for_selected_year = []
        for year in possible_years:
            games_for_selected_year.extend(fetch_games_data(academic_year=year))
        games_for_selected_year.sort(key=lambda game: game["game_id"], reverse=True)
    else:
        games_for_selected_year = fetch_games_data(academic_year=selected_year)

    if not games_for_selected_year:
        st.write("No games for the selected academic year.")
        return

    tab_game_ops, tab_leaderboards = st.tabs(["Game Operations", "Leaderboards"])

    with tab_game_ops:
        game_labels = [
            format_game_selector_label(game["game_academic_year"], game["game_class"], game["game_name"])
            for game in games_for_selected_year
        ]
        game_id_by_label = {label: game["game_id"] for label, game in zip(game_labels, games_for_selected_year)}
        selected_game_label = st.selectbox("Game", game_labels, key="cc_selected_game")

        selected_game_id = game_id_by_label.get(selected_game_label)
        selected_game = next((game for game in games_for_selected_year if game["game_id"] == selected_game_id), None)

        if not selected_game:
            st.warning("Game not found.")
            return

        game_key_suffix = str(selected_game["game_id"])
        st.subheader(selected_game["game_name"])

        overview_tabs = st.tabs(["Setup", "Submissions", "Simulation", "Results"])

        with overview_tabs[0]:
            render_setup_tab(selected_game, game_key_suffix)

        with overview_tabs[1]:
            render_submissions_tab(selected_game)

        with overview_tabs[2]:
            render_simulation_tab(selected_game)

        with overview_tabs[3]:
            render_results_tab(selected_game)

    with tab_leaderboards:
        lb_tab_overall, lb_tab_by_game = st.tabs(["Overall", "By Game"])

        with lb_tab_overall:
            st.markdown("### Overall Leaderboard")
            overall_game_ids = [game["game_id"] for game in games_for_selected_year]
            overall_leaderboard = fetch_and_compute_scores_for_game_ids(overall_game_ids)
            _render_leaderboard_table(overall_leaderboard)

        with lb_tab_by_game:
            st.markdown("### Individual Game Leaderboard")
            by_game_labels = [
                format_game_selector_label(game["game_academic_year"], game["game_class"], game["game_name"])
                for game in games_for_selected_year
            ]
            by_game_selected_label = st.selectbox("Select Game", by_game_labels, key="cc_lb_selected_game")
            by_game_index = by_game_labels.index(by_game_selected_label)
            game = games_for_selected_year[by_game_index]
            role_labels = game["name_roles"].split("#_;:)")
            role_1_label = role_labels[0]
            role_2_label = role_labels[1]
            per_game_leaderboard = fetch_and_compute_scores_for_year_game(game["game_id"])
            _render_leaderboard_table(per_game_leaderboard, role_1_label, role_2_label)
