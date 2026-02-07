import streamlit as st

from ..database_handler import fetch_games_data
from .game_overview_results import render_results_tab
from .game_overview_setup import render_setup_tab
from .game_overview_simulation import render_simulation_tab
from .game_overview_submissions import render_submissions_tab


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

    col1, col2 = st.columns(2)
    with col1:
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

    game_labels = [
        f"{game['game_academic_year']}{'' if game['game_class'] == '_' else (' - ' + game['game_class'])} • {game['game_name']}"
        for game in games_for_selected_year
    ]
    game_id_by_label = {label: game["game_id"] for label, game in zip(game_labels, games_for_selected_year)}

    with col2:
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
