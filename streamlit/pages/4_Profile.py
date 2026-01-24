import streamlit as st
import pandas as pd
import hashlib
import time
from modules.database_handler import update_password, get_class_from_user_id, get_group_id_from_user_id
from modules.database_handler import fetch_games_data, fetch_and_compute_scores_for_year, get_academic_year_from_user_id, fetch_and_compute_scores_for_year_game
from modules.database_handler import get_instructor_api_key, upsert_instructor_api_key
from modules.sidebar import render_sidebar

# Initialize session state for buttons if not set
if 'password_edit_mode' not in st.session_state:
    st.session_state['password_edit_mode'] = False

if 'show_password' not in st.session_state:
    st.session_state['show_password'] = False  # Track password visibility state

if 'show_api_key' not in st.session_state:
    st.session_state['show_api_key'] = False
if 'api_key_edit_mode' not in st.session_state:
    st.session_state['api_key_edit_mode'] = False

render_sidebar()

def render_password_section(email):
    st.markdown(f"<h3 style='font-size: 24px;'>Password</h3>", unsafe_allow_html=True)
    password = st.session_state.get('login_password', '')
    if st.session_state['show_password']:
        st.write(f"{password if password else 'Not defined'}")
    else:
        st.text('*******' if password else 'Not defined')

    col1, col2 = st.columns([1, 1])
    with col1:
        st.checkbox("Show password", key="show_password")
    with col2:
        if st.button("Edit password", key="edit_password"):
            st.session_state['password_edit_mode'] = not st.session_state['password_edit_mode']
            st.rerun()

    if st.session_state['password_edit_mode']:
        with st.form(key="password_form"):
            new_password = st.text_input("**Enter new password**", type="password", key="new_password_input")
            confirm_password = st.text_input("**Confirm new password**", type="password", key="confirm_password_input")
            update_password_btn = st.form_submit_button("Update Password")

            if update_password_btn:
                if new_password and confirm_password:
                    if new_password == confirm_password:
                        if (len(new_password) >= 8 and
                            any(char.isupper() for char in new_password) and
                            any(char.islower() for char in new_password) and
                            any(char.isdigit() for char in new_password) and
                            any(char in '!@#$%^&*()-_=+[]{}|;:,.<>?/`~' for char in new_password)):

                            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()

                            if update_password(email, hashed_password):
                                st.success("Password updated successfully!")
                                st.session_state['login_password'] = new_password
                                st.session_state['password_edit_mode'] = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to update password.")
                        else:
                            st.error("Password must be at least 8 characters long and include an uppercase letter, \
                                        a lowercase letter, a number, and a special character.")
                    else:
                        st.error("Passwords do not match.")
                else:
                    error = st.error("Please fill in both password fields.")
                    time.sleep(1)
                    error.empty()
# Check if the user is logged in
if st.session_state['authenticated']:

    if st.session_state.instructor == True:

        st.title("Profile")

        # Display email
        email = st.session_state['login_email']
        st.markdown(f"<h3 style='font-size: 24px;'>Email</h3>", unsafe_allow_html=True)
        st.write(f"{email}")

        # Display user_id
        user_id = st.session_state['user_id']
        st.markdown(f"<h3 style='font-size: 24px;'>User ID</h3>", unsafe_allow_html=True)
        st.write(f"{user_id}")

        render_password_section(email)

        st.markdown(f"<h3 style='font-size: 24px;'>API Key</h3>", unsafe_allow_html=True)
        saved_api_key = get_instructor_api_key(st.session_state.get('user_id'))
        if st.session_state['show_api_key'] and saved_api_key:
            st.write(saved_api_key)
        else:
            st.text("••••••••" if saved_api_key else "Not defined")

        col1, col2 = st.columns([1, 1])
        with col1:
            st.checkbox("Show API key", key="show_api_key")
        with col2:
            if st.session_state.get("api_key_edit_mode", False):
                if st.button("Cancel", key="cancel_api_key"):
                    st.session_state["api_key_edit_mode"] = False
                    st.rerun()
            else:
                if st.button("Edit API key", key="edit_api_key"):
                    st.session_state["api_key_edit_mode"] = True
                    st.rerun()

        if st.session_state.get("api_key_edit_mode", False):
            with st.form(key="api_key_form"):
                api_key_input = st.text_input("**Enter new API key**", type="password", key="api_key_input")
                submit_api_key = st.form_submit_button("Save API key")
                if submit_api_key:
                    if api_key_input:
                        if upsert_instructor_api_key(st.session_state.get('user_id'), api_key_input):
                            st.success("API key saved successfully!")
                            st.session_state["api_key_edit_mode"] = False
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to save API key. Check API_KEY_ENCRYPTION_KEY.")
                    else:
                        st.error("Please enter an API key.")

    elif st.session_state.instructor == False:
            
        ACADEMIC_YEAR = get_academic_year_from_user_id(st.session_state.user_id)
        CLASS = get_class_from_user_id(st.session_state['user_id'])
        GROUP_ID = get_group_id_from_user_id(st.session_state['user_id'])
        
        st.title("Profile")
        selection = st.sidebar.radio(label= '', options=['Leaderboard','Personal Data'], horizontal=True)

        if selection == 'Personal Data':

            st.header("Personal Data")

            # Display email
            email = st.session_state['login_email']
            st.markdown(f"<h3 style='font-size: 24px;'>Email</h3>", unsafe_allow_html=True)
            st.write(f"{email}")

            # Display user_id
            user_id = st.session_state['user_id']
            st.markdown(f"<h3 style='font-size: 24px;'>User ID</h3>", unsafe_allow_html=True)
            st.write(f"{user_id}")

            render_password_section(email)

        if selection == 'Leaderboard':
            st.header("Leaderboard")

            games = fetch_games_data(academic_year=ACADEMIC_YEAR)

            if games != []:

                game_names_with_classes = [
                                f"{game['game_name']}{'' if game['game_class'] == '_' else (' - Class ' + game['game_class'])}"
                                for game in games
                            ]

                game_names_with_classes.insert(0, "All")

                selected_game_with_classes = st.sidebar.selectbox("Select Game", game_names_with_classes)

                def color_coding(row):
                        return ['background-color:rgba(0, 255, 0, 0.25'] * len(row) if row["Class"] == CLASS  and row["Group ID"] == GROUP_ID else [''] * len(row)

                if selected_game_with_classes == "All":

                    st.subheader(ACADEMIC_YEAR)

                    leaderboard = fetch_and_compute_scores_for_year(ACADEMIC_YEAR, student=True)

                    if leaderboard:
                                            
                        leaderboard_with_position = [
                            {
                                "Class": row["team_class"],
                                "Group ID": row["team_id"],
                                "Games": row["total_games"],
                                "Avg Rounds": row["avg_rounds_per_game"],
                                "Avg Score": row["average_score"],
                                "Rank (Minimizer Role)": row["position_name_roles_1"],
                                "Score (Minimizer Role)": row["score_name_roles_1"],
                                "Rank (Maximizer Role)": row["position_name_roles_2"],
                                "Score (Maximizer Role)": row["score_name_roles_2"],
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
                                "Rank (Minimizer Role)",
                                "Score (Minimizer Role)",
                                "Rank (Maximizer Role)",
                                "Score (Maximizer Role)"
                            ]
                        )

                        leaderboard_df["Avg Rounds"] = pd.to_numeric(
                            leaderboard_df["Avg Rounds"],
                            errors="coerce"
                        ).round(2)
                        leaderboard_df["Avg Score"] = leaderboard_df["Avg Score"].round(2)
                        leaderboard_df["Score (Minimizer Role)"] = leaderboard_df["Score (Minimizer Role)"].round(2)
                        leaderboard_df["Score (Maximizer Role)"] = leaderboard_df["Score (Maximizer Role)"].round(2)

                        leaderboard_df.index = leaderboard_df.index + 1

                        st.dataframe(
                            leaderboard_df.style.apply(color_coding, axis=1).format(precision=2),
                            use_container_width=True,
                            column_config={
                                "Class": st.column_config.TextColumn(width="small"),
                                "Group ID": st.column_config.NumberColumn(width="small"),
                                "Games": st.column_config.NumberColumn(width="small", help="Total games played"),
                                "Avg Rounds": st.column_config.NumberColumn(width="small", help="Average rounds per game"),
                                "Avg Score": st.column_config.NumberColumn(width="small", help="Average score across games"),
                                "Rank (Minimizer Role)": st.column_config.NumberColumn(width="small"),
                                "Score (Minimizer Role)": st.column_config.NumberColumn(width="small"),
                                "Rank (Maximizer Role)": st.column_config.NumberColumn(width="small"),
                                "Score (Maximizer Role)": st.column_config.NumberColumn(width="small"),
                            },
                        )

                    else: st.write("Leaderboard not available yet.") 

                else:

                    st.subheader(selected_game_with_classes)

                    index_ = game_names_with_classes.index(selected_game_with_classes)-1

                    if games[index_]['available'] == 1:
                        leaderboard = fetch_and_compute_scores_for_year_game(games[index_]['game_id'])

                        if leaderboard:                         

                            role_labels = games[index_]['name_roles'].split('#_;:)')
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
                                    f"Score ({role_2_label})"
                                ]
                            )

                            leaderboard_df["Avg Rounds"] = pd.to_numeric(
                                leaderboard_df["Avg Rounds"],
                                errors="coerce"
                            ).round(2)
                            leaderboard_df["Avg Score"] = leaderboard_df["Avg Score"].round(2)
                            leaderboard_df[f"Score ({role_1_label})"] = leaderboard_df[f"Score ({role_1_label})"].round(2)
                            leaderboard_df[f"Score ({role_2_label})"] = leaderboard_df[f"Score ({role_2_label})"].round(2)

                            leaderboard_df.index = leaderboard_df.index + 1

                            st.dataframe(
                                leaderboard_df.style.apply(color_coding, axis=1).format(precision=2),
                                use_container_width=True,
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

                    elif games[index_]['available'] == 0: st.write("Leaderboard not available yet.") 

            else: st.write('No games played yet.')

else:
    st.title("Profile")
    st.warning("Please login first to access Profile.")
