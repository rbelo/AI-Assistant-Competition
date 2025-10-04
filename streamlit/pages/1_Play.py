import streamlit as st
import re
import time 
from datetime import datetime as dt
from modules.database_handler import (
    fetch_current_games_data_by_user_id, get_group_id_from_user_id, 
    get_class_from_user_id, get_round_data_by_class_group_id,
    get_academic_years_of_students, get_classes_of_students, 
    get_groups_of_students, get_user_id_of_student,
    get_group_values 
)
from modules.drive_file_manager import get_text_from_file, overwrite_text_file, get_text_from_file_without_timestamp
from modules.metrics_handler import record_game_start, record_game_end, record_game_interaction

# ------------------------ SET THE DEFAULT SESSION STATE FOR THE PLAY SECTION ---------------------------- #

# Initialize session state for show password form
if "not_show_game_password_form" not in st.session_state:
    st.session_state.not_show_game_password_form = []

# Initialize session state for game tracking
if "game_started" not in st.session_state:
    st.session_state.game_started = {}
elif not isinstance(st.session_state.game_started, dict):
    st.session_state.game_started = {}

# -------------------------------------------------------------------------------------------------------- #

@st.cache_resource
def get_text_from_file_aux(name):
    text = get_text_from_file(f'{name}.txt')
    return text

@st.cache_resource
def get_text_from_file_without_timestamp_aux(name):
    text = get_text_from_file_without_timestamp(name)
    return text

# Check if the user is authenticated
if st.session_state['authenticated']:

    col1, _, col3 = st.columns([2, 8, 2])
    with col3:
        # Sign out button
        sign_out_btn = st.button("Sign Out", key="sign_out", use_container_width=True)

        if sign_out_btn:
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.cache_resource.clear()
            # time.sleep(1)
            st.switch_page("0_Home.py")  # Redirect to home page

    if st.session_state['professor']: 
        academic_years_students = get_academic_years_of_students()
        select_year = st.sidebar.selectbox('Select Academic Year', academic_years_students)
        
        classes_students = get_classes_of_students(select_year)
        CLASS = st.sidebar.selectbox('Select Class', classes_students)

        groups_students = get_groups_of_students(select_year, CLASS)
        GROUP_ID = st.sidebar.selectbox('Select Group', groups_students)
        
        USER_ID =get_user_id_of_student(select_year, CLASS, GROUP_ID)
        
    else:
        GROUP_ID = get_group_id_from_user_id(st.session_state['user_id'])
        CLASS = get_class_from_user_id(st.session_state['user_id'])
        USER_ID = st.session_state.user_id
    
    option = st.sidebar.radio("See:", ('Current Games', 'Past Games'),horizontal=True)
    st.header(option)

    # Fetch the list of games from the database
    if option == 'Current Games':
                
        games = fetch_current_games_data_by_user_id('<', USER_ID)
        
        if games != []:

            # Streamlit sidebar selectbox for games
            game_names = [game['game_name'] for game in games]
            selected_game_name = st.sidebar.selectbox("Select Game", game_names)

            st.markdown(f'## {selected_game_name}')

            # Find the selected game
            selected_game = next((game for game in games if game['game_name'] == selected_game_name), None)

            # Retrieve the ID, professor ID and timestamp of the game
            game_id = selected_game['game_id']
            professor_id = selected_game['created_by']
            timestamp_game_creation = selected_game['timestamp_game_creation']
            name_roles = selected_game['name_roles'].split('#_;:)')
            name_roles_1, name_roles_2 = name_roles[0], name_roles[1]

            # Ensure game_started is a dictionary
            if not isinstance(st.session_state.game_started, dict):
                st.session_state.game_started = {}

            # Record game start if not already started
            if str(game_id) not in st.session_state.game_started:
                st.session_state.game_started[str(game_id)] = True
                record_game_start(st.session_state.get('user_id', 'anonymous'), game_id)

            with st.expander("**Explanation**"):

                # Get the Game explanation from Google Drive using the filename
                game_explanation = get_text_from_file_aux(f'Explanation_{professor_id}_{game_id}_{timestamp_game_creation}')
                if game_explanation:
                    st.write(f"{game_explanation}\n\n**Note:** The game explanation is not passed automatically to the agent. If you want to do it, you must place it in the prompt explicitly.")
                else:
                    st.write("No explanation found for this game. Please contact your Professor.")
                
            with st.expander("**Private Information**"):
    
                # Get the Private Information from the database instead
                group_values = get_group_values(game_id, CLASS, GROUP_ID)
                if group_values:
                    st.write(f"The following information is private and group-specific. Do not share it with others:")
                    st.write(f"When playing as **{name_roles_1}**, your reservation value is: **{group_values['minimizer_value']}**;")
                    st.write(f"When playing as **{name_roles_2}**, your reservation value is: **{group_values['maximizer_value']}**.")
                else:
                    st.write("No private information found for this game.")

            with st.expander("**Submission Deadline**"):
                st.write(f"{selected_game['timestamp_submission_deadline']}")
            
            if selected_game not in st.session_state.not_show_game_password_form:
                with st.form("insert_password_form"):
                    st.write("Please introduce the Password to play this Game.")
                    password_input = st.text_input("Enter the Game Password", type="password", key="game_password_input")
                    
                    play_now_btn = st.form_submit_button("Play now!")

                    if play_now_btn:
                        if selected_game['password'] == password_input:
                            st.success("Correct Password.")
                            st.session_state.not_show_game_password_form.append(selected_game)
                            # time.sleep(1)
                            st.rerun()

                        else:
                            st.error("Incorrect Password. Please try again.")
                    
            if selected_game in st.session_state.not_show_game_password_form:

                st.write('')
                
                with st.form(key='form_inputs'):
                    text_area_1 = st.text_area(f'{name_roles_1} Prompt', max_chars = 7000, help='A good prompt should be clear, specific, and provide enough context and detail about your position, interests, and desired outcomes. Note that the game explanation is not passed automatically to the agent. If you want to do it, you must place it in the prompt explicitly.')
                    text_area_2 = st.text_area(f'{name_roles_2} Prompt', max_chars = 7000)
                    submit_button = st.form_submit_button('Submit')

                if submit_button:                    
                    prompts = text_area_1 + '\n\n' + '#_;:)' + '\n\n' + text_area_2
                    overwrite_text_file(prompts, f"Game{game_id}_Class{CLASS}_Group{GROUP_ID}_{dt.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    success = st.success('Submission Successful. You can adjust your prompts until the deadline.')
                    
                    # Record game interaction when prompts are submitted
                    record_game_interaction(
                        user_id=st.session_state.get('user_id', 'anonymous'),
                        game_type="zero-sum",  # Since this is a zero-sum game
                        game_id=str(game_id),  # Convert to string as required
                        completion_time=0,  # Will be updated when game ends
                        score=0  # Will be updated after simulation
                    )

        else:
            st.write("There are no current games.")

    if option == 'Past Games': 

        past_games = fetch_current_games_data_by_user_id('>', USER_ID) 

        # If there are past games (in which the student took part)
        if past_games != []:
            past_game_names = [past_game['game_name'] for past_game in past_games]
            selected_past_game_name = st.sidebar.selectbox("Select Game", past_game_names)
            selected_past_game = next((game for game in past_games if game['game_name'] == selected_past_game_name), None)
             
            st.header(selected_past_game_name)

            game_id = selected_past_game['game_id']
            professor_id = selected_past_game['created_by']
            timestamp_game_creation = selected_past_game['timestamp_game_creation']
            name_roles = selected_past_game['name_roles'].split('#_;:)')
            name_roles_1, name_roles_2 = name_roles[0], name_roles[1]

            submission = get_text_from_file_without_timestamp_aux(f'Game{game_id}_Class{CLASS}_Group{GROUP_ID}_')

            with st.expander("**Explanation**"):
                game_explanation = get_text_from_file_without_timestamp_aux(f'Explanation_{professor_id}_{game_id}_')
                if game_explanation: st.write(f"{game_explanation}")
                else: st.write("No explanation found for this game. Please contact your Professor.")

            with st.expander("**Private Information**"):
                # Get the Private Information from the database instead
                group_values = get_group_values(game_id, CLASS, GROUP_ID)
                if group_values:
                    st.write(f"The following information is private and group-specific. Do not share it with others:")
                    st.write(f"When playing as **{name_roles_1}**, your valuation is: **{group_values['minimizer_value']}**;")
                    st.write(f"When playing as **{name_roles_2}**, your valuation is: **{group_values['maximizer_value']}**.")
                else:
                    st.write("No private information found for this game. Please contact your Professor.")

            if submission:
                with st.expander("**View Prompts**"):
                    submission = submission.split('#_;:)')
                    st.write(f'**{name_roles_1}:** {submission[0].strip()}')
                    st.write(f'**{name_roles_2}:** {submission[1].strip()}')
            else:
                st.write('No prompts found. Please contact your Professor.')

            # If negotiation chats of the game are already available to students
            if selected_past_game['available']==1:
                
                round_data=get_round_data_by_class_group_id(selected_past_game['game_id'], CLASS, GROUP_ID)
  
                if round_data:
                    # Ensure game_started is a dictionary
                    if not isinstance(st.session_state.game_started, dict):
                        st.session_state.game_started = {}

                    # Record game end when viewing past game results
                    if str(selected_past_game['game_id']) in st.session_state.game_started:
                        record_game_end(st.session_state.get('user_id', 'anonymous'), selected_past_game['game_id'])
                        del st.session_state.game_started[str(selected_past_game['game_id'])]

                    files_names=[]
                    for i in range(len(round_data)):
                        round = round_data[i][0] 
                        class_1, group_1, class_2, group_2 =  round_data[i][1], round_data[i][2], round_data[i][3], round_data[i][4]
                        if class_1 == CLASS and group_1 == GROUP_ID:
                            files_names.append([round, class_2, group_2])
                        else: files_names.append([round, class_1, group_1])

                    options = [name_roles_1, name_roles_2]
                    selection = st.sidebar.radio(label= 'Select Your Position', options=options, horizontal=True)

                    options_chat = [f'Round {i[0]} (vs Class {i[1]} - Group {i[2]})' for i in files_names]
                    chat_selector = st.sidebar.selectbox('Select Negotiation Chat', options_chat)

                    st.markdown(f'### {chat_selector}')

                    aux_ = chat_selector.split('Class ')
                    round_ = int(re.findall(r'\d+', aux_[0])[0])
                    class_ = aux_[1][0]
                    group_ = int(re.findall(r'\d+', aux_[1])[0])

                    if selection == name_roles_1:
                        chat = get_text_from_file_aux(f'Game{game_id}_Round{round_}_Class{CLASS}_Group{GROUP_ID}_Class{class_}_Group{group_}')
                        if chat: st.write(chat.replace('$', '\$'))
                        else: st.write('Chat not found. Please contact your Professor.')

                    elif selection == name_roles_2:
                        chat = get_text_from_file_aux(f'Game{game_id}_Round{round_}_Class{class_}_Group{group_}_Class{CLASS}_Group{GROUP_ID}')
                        if chat: st.write(chat.replace('$', '\$'))
                        else: st.write('Chat not found. Please contact your Professor.')
                
                else: st.write('You do not have any chats available. Please contact your Professor.')
    
            # If negotiation chats of the game are not yet available to students
            else: 
                st.write('Negotiation Chats are not available yet.')

        # If there are not any past games (in which the student took part)
        else: 
            st.write('No past games to show.') 

# If the user is not authenticated yet   
else:
    st.header('Play')
    st.write('Please Login first.')
