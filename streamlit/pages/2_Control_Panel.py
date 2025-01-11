import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import random
import re
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, ColumnsAutoSizeMode
from modules.database_handler import populate_plays_table, insert_student_data, remove_student, store_game_in_db, update_game_in_db, update_num_rounds_game, update_access_to_chats
from modules.database_handler import get_academic_year_class_combinations, get_game_by_id, fetch_games_data, get_next_game_id, get_students_from_db, get_group_ids_from_game_id, get_round_data
from modules.drive_file_manager import overwrite_text_file, get_text_from_file, upload_text_as_file, get_text_from_file_without_timestamp
from modules.negotiations import create_chats

# ---------------------------- SET THE DEFAULT SESSION STATE FOR ALL CASES ------------------------------- #

# Initialize session state for action selection
if "action" not in st.session_state:
    st.session_state.action = "Select Option"

# Initialize session state for back button
if "back_button" not in st.session_state:
    st.session_state.back_button = False

# -------------------- SET THE DEFAULT SESSION STATE FOR STUDENT MANAGEMENT CASE ------------------------- #

if "add_students" not in st.session_state:
    st.session_state.add_students = False
if "add_student" not in st.session_state:
    st.session_state.add_student = False
if "remove_student" not in st.session_state:
    st.session_state.remove_student = False
if "selected_student" not in st.session_state:
    st.session_state.selected_student = None
if "students" not in st.session_state:
    st.session_state.students = pd.DataFrame(columns=["User ID", "Email", "Academic Year", "Class", "Created at"])

# ----------------------- SET THE DEFAULT SESSION STATE FOR AVAILABLE GAMES CASE ------------------------- #

if "edit_game" not in st.session_state:
    st.session_state.edit_game = False
if "game_id" not in st.session_state:
    st.session_state.game_id = ""

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
    with col1:
        if st.session_state.back_button:
            # Back button
            if st.button("⬅ Back"):
                if st.session_state.edit_game:
                    st.session_state.edit_game = False
                else:
                    st.session_state.back_button = False
                    st.session_state.add_student = False
                    st.session_state.add_students = False
                    st.session_state.remove_student = False
                    st.session_state.action = "Select Option"
                st.rerun()
    with col3:
        # Sign out button
        sign_out_btn = st.button("Sign Out", key="sign_out", use_container_width=True)

        if sign_out_btn:
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            time.sleep(2)
            st.cache_resource.clear()
            st.switch_page("0_Home.py")  # Redirect to home page

    # Check if the user is a professor
    if st.session_state['professor']: 

        # Handle different actions for the professor
        if st.session_state.action == "Select Option":
            st.header("Select Option")
            st.write("Welcome, Professor! Please select an option.")

            # Action selection dropdown
            c1, _ = st.columns([3, 2])
            selected_option = c1.selectbox("Select Option", ["Student Management", "Create Game", "Available Games",
                                                             "Run Simulation" , "Game Data", "Leaderboard and Performance", "Security"])

            if st.button("Select"):
                st.session_state.action = selected_option  # Update session state only when the button is clicked
                st.session_state.back_button = True
                st.rerun()
        else:
            # Render the selected action
            st.header(st.session_state.action)
            
            # Define behavior for "Student Management"
            match st.session_state.action:

                case "Student Management": # Allow professor to add students, assign students to games and track student activity

                    # --------------------------------------------------- FUNCTIONS --------------------------------------------------- #

                    # Function to add students from a CSV file
                    def add_students_from_csv(file):
                        try:
                            # Read CSV with a semicolon delimiter
                            df = pd.read_csv(file, sep=';', dtype={'academic year': str})
                            
                            # Check if all required columns exist in the CSV
                            if 'userID' not in df.columns or 'email' not in df.columns or 'groupID' not in df.columns or 'academic year' \
                                not in df.columns or 'class' not in df.columns:
                                st.error("CSV must contain 'userID', 'email', 'groupID', 'academic year' and 'class' columns.")
                                return
                            
                            # Insert student data row by row
                            for _, row in df.iterrows():
                                user_id = row['userID']
                                email = row['email']
                                group_id = row['groupID']
                                academic_year = row['academic year']
                                class_ = row['class']

                                if insert_student_data(user_id, email, group_id, "Not defined", academic_year, class_):
                                    continue
                                else:
                                    return False
                            return True
                            
                        except Exception:
                            st.error("Error processing the CSV file. Please try again.")

                    # Function to display the student table with selectable rows
                    def show_student_table():
                        # Fetch data from the database
                        students_from_db = get_students_from_db()
                        
                        # Rename columns for display
                        students_display = students_from_db.rename(columns={
                            "user_id": "User ID",
                            "email": "Email",
                            "group_id": "Group ID",
                            "academic_year": "Academic Year",
                            "class": "Class",
                            "timestamp_user": "Created at"
                        })
                        
                        # Update session state with the dataset
                        st.session_state.students = students_display

                        # Add a "Select" column for row checkboxes
                        students_display[""] = ""
                        
                        ## Configure grid options
                        gb = GridOptionsBuilder.from_dataframe(students_display[["", "User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]])
                    
                        gb.configure_column("", checkboxSelection=True, width=60)
                        gb.configure_column("User ID", width=120)
                        gb.configure_column("Email", width=140)
                        gb.configure_column("Group ID", width=120)
                        gb.configure_column("Academic Year", width=140)
                        gb.configure_column("Class", width=80)
                        gb.configure_column("Created at", width=130)
                        
                        gridOptions = gb.build()

                        # Display the table
                        data = AgGrid(students_display[["", "User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]],
                                    gridOptions=gridOptions,
                                    fit_columns_on_grid_load=True,
                                    height=min(36 + 27 * students_display.shape[0], 300),
                                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                                    columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS)
                        return data

                    # ------------------------------------------------------------------------------------------------------------------------------------ #

                    # Display the student table
                    data = show_student_table()
                    st.session_state.selected_student = data["selected_rows"]

                    # Action buttons
                    _, col1, col2, col3 = st.columns([1,1,1,2])

                    with col1:
                        if st.button("Add Students", key="add_students_via_csv"):
                            st.session_state.add_students = True
                            st.session_state.add_student = False
                            st.session_state.remove_student = False
                    with col2:
                        if st.button("Add Student", key="add_student_manually"):
                            st.session_state.add_student = True
                            st.session_state.add_students = False
                            st.session_state.remove_student = False
                    with col3:
                        if st.button("Remove Student", key="remove_student_manually"):
                            st.session_state.remove_student = True
                            st.session_state.add_student = False
                            st.session_state.add_students = False

                    # Handle adding students via CSV
                    if st.session_state.add_students:
                        with st.form("add_students_form"):
                            uploaded_file = st.file_uploader("Upload CSV with all the Students", type=["csv"])

                            submit_button = st.form_submit_button("Add Students")

                            if submit_button:
                                if uploaded_file is not None:
                                    if add_students_from_csv(uploaded_file):
                                        st.success("Students added successfully!")
                                    else:
                                        st.error("An error occurred when adding the students. Please try again.")
                                else:
                                    st.error("Please upload a valid CSV file.")
                                st.session_state.add_students = False
                                st.session_state.action = "Student Management"
                                time.sleep(2)
                                st.rerun()

                    # Handle manual student addition
                    if st.session_state.add_student:
                        with st.form("add_student_form"):
                            user_id = st.text_input("Introduce User ID:")
                            email = st.text_input("Introduce Email:")
                            group_id = st.text_input("Introduce the Group ID:")
                            academic_year = st.text_input("Introduce academic year:")
                            class_ = st.text_input("Introduce class:")

                            submit_button = st.form_submit_button("Add Student")

                            if submit_button:
                                if not user_id or not email or not group_id or not academic_year or not class_:
                                    st.error("Please fill in all fields.")
                                else:
                                    if insert_student_data(user_id, email, "Not defined", group_id, academic_year, class_):
                                        st.success("Student added successfully!")
                                    else:
                                        st.error("Failed to add student. Please try again.")
                                    st.session_state.add_student = False
                                    st.session_state.action = "Student Management"
                                    time.sleep(2)
                                    st.rerun()

                    # Handle student removal
                    if st.session_state.remove_student:
                        if st.session_state.students.empty:
                            st.warning("No students found. Please add a student.")
                        else:
                            if st.session_state.selected_student is not None:
                                if len(st.session_state.selected_student) != 0:
                                    user_id = st.session_state.selected_student['User ID'].tolist()[0]
                                    if remove_student(user_id):
                                        st.success("Student removed successfully!")
                                        st.session_state.students = st.session_state.students[st.session_state.students["User ID"] != user_id]
                                    else:
                                        st.error("Failed to remove student. Please try again.")
                            else:
                                st.warning("Please select a student to remove.")
                        st.session_state.remove_student = False
                        st.session_state.action = "Student Management"
                        time.sleep(2)
                        st.rerun()

                case "Create Game":  # Allow professor to create a game
                    # Get academic year and class combinations
                    academic_year_class_combinations = get_academic_year_class_combinations()

                    # Create options list with both years and year-class combinations
                    combination_options = []
                    for year, classes in academic_year_class_combinations.items():
                        combination_options.append(f"{year}")  # Add the year itself
                        combination_options.extend([f"{year} - {cls}" for cls in classes])  # Add year-class combinations

                    # Form to handle game creation
                    with st.form("game_creation_form"):
                        # Game details
                        game_name = st.text_input("Game Name", max_chars=100, key="game_name")
                        game_explanation = st.text_area("Game Explanation", key="explanation")
                        num_roles = st.number_input(
                            "Number of Roles", min_value=1, max_value=2, step=1, value=2, key="num_roles"
                        )

                        st.write('')
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            param1 = st.number_input("Minimum Buy Value", min_value=0, step=1, value=9)

                        with col2:
                            param2 = st.number_input("Maximum Buy Value", min_value=0, step=1, value=11)

                        with col3:
                            param3 = st.number_input("Minimum Sell Value", min_value=0, step=1, value=19)

                        with col4:
                            param4 = st.number_input("Maximum Sell Value", min_value=0, step=1, value=21,
                                help='These values are relevant only when the Number of Roles is set to 2. All values are expressed in thousands.')

                        # Academic year and class selection
                        selected_combination = st.selectbox(
                            "Select Academic Year and Class",
                            options=combination_options,
                            key="academic_year_class_combination",
                        )

                        # Extract academic year and class from the selected combination
                        if "-" in selected_combination:
                            game_academic_year, game_class = selected_combination.replace(" ", "").split("-")
                        else:
                            game_academic_year = selected_combination
                            game_class = "_"  # No class selected

                        password = st.text_input("Game Password (4-digit)", type="password", max_chars=4, key="password")

                        # Calculate default date and time
                        default_date = datetime.today().date() + timedelta(weeks=1)
                        default_time = datetime.strptime("23:59", "%H:%M").time()

                        # Create Streamlit inputs with defaults
                        deadline_date = st.date_input("Submission Deadline Date", value=default_date, key="deadline_date")
                        deadline_time = st.time_input("Submission Deadline Time", value=default_time, key="deadline_time")

                        # Submit button for creating the game
                        submit_button = st.form_submit_button("Create Game")

                    # Submit button for creating the game
                    if submit_button:
                        #if create_game_button:
                        if game_name and game_explanation and num_roles and game_academic_year and \
                            game_class and password and deadline_date and deadline_time:
                            try:
                                # Retrieve user ID from session state
                                user_id = st.session_state.get('user_id')

                                # Get the next game ID from the database
                                next_game_id = get_next_game_id()

                                timestamp_game_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                # Store the Game explanation in Google Drive
                                upload_text_as_file(game_explanation, f"{user_id}_{next_game_id}_{timestamp_game_creation}")

                                # Combine the date and time into a single datetime object
                                submission_deadline = datetime.combine(deadline_date, deadline_time)

                                # Store other details in the database
                                store_game_in_db(next_game_id, 0, user_id, game_name, -1, num_roles, game_academic_year,
                                                   game_class, password, timestamp_game_creation, submission_deadline)
                                
                                # Populate the 'plays' table with eligible students
                                if not populate_plays_table(next_game_id, game_academic_year, game_class):
                                    error = st.error("An error occurred while assigning students to the game.")
                                    time.sleep(2)
                                    error.empty()
                                
                                if num_roles==2:
                                    different_groups_classes = get_group_ids_from_game_id(next_game_id)
                                    text = ''
                                    for i in different_groups_classes:
                                        buy_value = int(round(random.uniform(param1*1000, param2*1000), -2))
                                        sell_value = int(round(random.uniform(param3*1000, param4*1000), -2))
                                        text += f"{i[0]},{i[1]},{buy_value},{sell_value}\n"

                                    upload_text_as_file(text, f"{user_id}_{next_game_id}_Values")

                                success = st.success("Game created successfully!")
                                time.sleep(2)
                                success.empty()

                            except Exception:
                                error = st.error("An error occurred. Please try again.")
                                time.sleep(2)
                                error.empty()

                        else:
                            warning = st.warning("Please fill out all fields before submitting.")
                            time.sleep(2)
                            warning.empty()
 
                case "Available Games": # Allow professor to see and edit the available games

                    if not st.session_state.edit_game:

                        # Fetch unique academic years
                        possible_years = fetch_games_data(get_academic_years=True)

                        # Sidebar selectbox for academic year selection
                        selected_year = st.sidebar.selectbox("Select the Academic Year", possible_years)

                        # Fetch games for the selected academic year
                        games_for_selected_year = fetch_games_data(academic_year=selected_year)

                        if games_for_selected_year != []:
                            # Generate game names with class suffixes
                            game_names_with_classes = [
                                f"{game['game_name']}{'' if game['game_class'] == '_' else (' - Class ' + game['game_class'])}"
                                for game in games_for_selected_year
                            ]

                            # Sidebar selectbox for game selection
                            selected_game_with_classes = st.sidebar.selectbox("Select a Game", game_names_with_classes)

                            # Extract game_name and game_class from selected_game_with_classes
                            if " - Class " in selected_game_with_classes:
                                selected_game_name, selected_game_class = selected_game_with_classes.split(" - Class ")
                            else:
                                selected_game_name = selected_game_with_classes
                                selected_game_class = "_"

                            # Find the selected game
                            selected_game = next(
                                (game for game in games_for_selected_year if game['game_name'] == selected_game_name and game['game_class'] == selected_game_class),
                                None
                            )

                            if selected_game:
                                st.subheader(f"Details for {selected_game['game_name']}")
                                st.write(f"**Game ID**: {selected_game['game_id']}")
                                st.write(f"**Available**: {selected_game['available']}")
                                st.write(f"**Created By**: {selected_game['created_by']}")
                                st.write(f"**Number of Rounds**: {selected_game['number_of_rounds']}")
                                st.write(f"**Number of Roles**: {selected_game['num_inputs']}")
                                st.write(f"**Academic Year related to the Game**: {selected_game['game_academic_year']}")
                                st.write(f"**Class related to the Game**: {selected_game['game_class']}")
                                st.write(f"**Password**: {selected_game['password']}")
                                st.write(f"**Creation Time**: {selected_game['timestamp_game_creation']}")
                                st.write(f"**Submission Deadline**: {selected_game['timestamp_submission_deadline']}")

                                # Retrieve user ID from session state
                                user_id = st.session_state.get('user_id')

                                # Get the Game explanation from Google Drive using the filename
                                game_explanation = get_text_from_file_aux(f"{selected_game['created_by']}_{selected_game['game_id']}_{selected_game['timestamp_game_creation']}")
                                if game_explanation:
                                    st.write(f"**Game Explanation**: {game_explanation}")
                                else:
                                    st.write("No explanation found for this game.")
                                
                                game_id = selected_game['game_id']
                                edit_game_button = st.button("Edit Game")
                                st.session_state.update({'game_id': game_id})

                                if edit_game_button:
                                    st.session_state.edit_game = True
                                    st.rerun()
                        else:
                            st.write("There are no available games.")
                    else:
                        # Handle manual game edit
                        game_id = st.session_state.game_id
                        game_details = get_game_by_id(game_id)

                        if game_details:
                            available_stored = game_details["available"]
                            created_by_stored = game_details["created_by"]
                            game_name_stored = game_details["game_name"]
                            number_of_rounds_stored = game_details["number_of_rounds"]
                            num_roles_stored = game_details["num_inputs"]
                            game_academic_year_stored = game_details["game_academic_year"]
                            game_class_stored = game_details["game_class"]
                            password_stored = game_details["password"]
                            timestamp_game_creation_stored = game_details["timestamp_game_creation"]
                            deadline_date_stored = game_details["timestamp_submission_deadline"].date()
                            deadline_time_stored = game_details["timestamp_submission_deadline"].time()

                            # Fetch Game explanation from Google Drive
                            game_explanation_stored = get_text_from_file_aux(f"{created_by_stored}_{game_id}_{timestamp_game_creation_stored}")
                        else:
                            st.error("Game not found.")

                        # Get academic year and class combinations
                        academic_year_class_combinations = get_academic_year_class_combinations()

                        # Create options list with both years and year-class combinations
                        combination_options = []
                        for year, classes in academic_year_class_combinations.items():
                            combination_options.append(f"{year}")  # Add the year itself
                            combination_options.extend([f"{year} - {cls}" for cls in classes])  # Add year-class combinations

                        # Preselect the stored academic year-class combination
                        if game_class_stored != "_":
                            stored_combination = f"{game_academic_year_stored} - {game_class_stored}"
                        else: 
                            stored_combination = f"{game_academic_year_stored}"

                        with st.form("game_edit_form"):
                            # Game details
                            game_name_edit = st.text_input("Game Name", max_chars=100, key="game_name_edit", value=game_name_stored)
                            game_explanation_edit = st.text_area("Game Explanation", key="explanation_edit", value=game_explanation_stored)
                            available_edit = st.number_input("Available", min_value=0, max_value=1, step=1, key="available_edit", value=available_stored)
                            num_roles_edit = st.number_input("Number of Roles", min_value=1, max_value=2, step=1, key="num_roles_edit", value=num_roles_stored)

                            # Academic year-class combination selection
                            selected_combination_edit = st.selectbox(
                                "Select Academic Year and Class",
                                options=combination_options,
                                index=combination_options.index(stored_combination),
                                key="academic_year_class_combination_edit",
                            )

                            # Extract academic year and class from the selected combination
                            game_academic_year_edit, game_class_edit = selected_combination_edit.replace(" ", "").split("-")

                            # Extract academic year and class from the selected combination
                            if "-" in selected_combination_edit:
                                game_academic_year, game_class = selected_combination_edit.replace(" ", "").split("-")
                            else:
                                game_academic_year = selected_combination_edit
                                game_class = "_"  # No class selected

                            password_edit = st.text_input("Game Password (4-digit)", type="password", max_chars=4, key="password_edit", value=password_stored)
                            deadline_date_edit = st.date_input("Submission Deadline Date", key="deadline_date_edit", value=deadline_date_stored)
                            deadline_time_edit = st.time_input("Submission Deadline Time", key="deadline_time_edit", value=deadline_time_stored)

                            # Submit button
                            submit_button = st.form_submit_button("Change Game")

                        # Handle form submission
                        if submit_button:
                            if available_edit and game_name_edit and game_explanation_edit and num_roles_edit and \
                                game_academic_year_edit and game_class_edit and password_edit and deadline_date_edit and deadline_time_edit:
                                try:
                                    # Overwrite file in Google Drive
                                    overwrite_text_file(game_explanation_edit, f"{created_by_stored}_{game_id}_{timestamp_game_creation_stored}")

                                    # Combine the date and time into a single datetime object
                                    submission_deadline = datetime.combine(deadline_date_edit, deadline_time_edit)

                                    # Update other details in the database
                                    update_game_in_db(game_id, available_edit, created_by_stored, game_name_edit, -1, num_roles_edit, game_academic_year_edit,
                                                        game_class_edit, password_edit, timestamp_game_creation_stored, submission_deadline)
                                    
                                    # Populate the 'plays' table with eligible students (after update)
                                    if not populate_plays_table(game_id, game_academic_year_edit, game_class_edit):
                                        st.error("An error occurred while assigning students to the game.")

                                    st.success("Game changed successfully!")
                                    
                                except Exception:
                                    st.error(f"An error occurred. Please try again.")
                            else:
                                st.error("Please fill out all fields before submitting.")
                            st.session_state.edit_game = False
                            st.session_state.action = "Available Games"
                            time.sleep(2)
                            st.rerun()

                case "Run Simulation":

                    # Fetch unique academic years
                    possible_years = fetch_games_data(get_academic_years=True)

                    # Sidebar selectbox for academic year selection
                    selected_year = st.sidebar.selectbox("Select the Academic Year", possible_years)

                    # Fetch games for the selected academic year
                    games_for_selected_year = fetch_games_data(academic_year=selected_year)

                    if games_for_selected_year != []:
                        # Generate game names with class suffixes
                        game_names_with_classes = [
                            f"{game['game_name']}{'' if game['game_class'] == '_' else (' - Class ' + game['game_class'])}"
                            for game in games_for_selected_year
                        ]

                        # Sidebar selectbox for game selection
                        selected_game_with_classes = st.sidebar.selectbox("Select a Game", game_names_with_classes)

                        # Extract game_name and game_class from selected_game_with_classes
                        if " - Class " in selected_game_with_classes:
                            selected_game_name, selected_game_class = selected_game_with_classes.split(" - Class ")
                        else:
                            selected_game_name = selected_game_with_classes
                            selected_game_class = "_"

                        # Find the selected game
                        selected_game = next(
                            (game for game in games_for_selected_year if game['game_name'] == selected_game_name and game['game_class'] == selected_game_class),
                            None
                        )
                        
                        game_id = selected_game['game_id']

                        teams = get_group_ids_from_game_id(game_id)

                        missing_submissions = ''
                        for i in teams:
                            prompts = get_text_from_file_without_timestamp_aux(f'Game{game_id}_Class{i[0]}_Group{i[1]}')
                            if not prompts: 
                                missing_submissions += f' Class{i[0]}-Group{i[1]},'
                        
                        if len(missing_submissions) > 0:
                            missing_submissions = missing_submissions[:-1]
                            st.warning(f'''Attention: Not all groups have submitted their prompts yet.\n
                                          Missing submissions from:{missing_submissions}.''')
                        
                        with st.form(key='my_form'):
                            api_key = st.text_input('API Key', value=1)
                            model = st.selectbox('OpenAI Model', ['gpt-4o', 'gpt-4o-mini'])
                            temperature = 0# st.number_input('Temperature', min_value=0.0, max_value=1.0, value=0.0)
                            num_rounds =  st.number_input('Number of Rounds', step=1, min_value=1, value=1, max_value=len(teams)-1)
                            if selected_game['num_inputs']==2:
                                conversation_starter = st.radio('Conversation Starter', ['Buyer > Seller', 'Seller > Buyer'], horizontal=True)
                            starting_message =  st.text_input('Starting Messsage', value='I want to buy this car.')
                            num_turns =  st.number_input('Number of Turns', step=1, min_value=1, value=5)
                            negotiation_termination_message = st.text_input('Negotiation Termination Message', value='Pleasure doing business with you')
                            summary_prompt = st.text_input('Negotiation Summary Prompt', value='For how much was the car sold?')
                            summary_termination_message = st.text_input('Summary Termination Message', value='The value agreed was')

                            submit_button = st.form_submit_button(label='Run')

                        if submit_button:
                            update_num_rounds_game(num_rounds, game_id)
                            config_list = [{"api_key": api_key, "model": model, "temperature": temperature}]
                            #create_chats(game_id, config_list, teams, num_rounds, starting_message, num_turns, negotiation_termination_message, summary_prompt, summary_termination_message)
                            success = st.success('All negotiations successfully created.')
                            time.sleep(3)
                            success.empty()

                    else:
                        st.write('There are no available games.')

                case "Game Data":

                    # Fetch unique academic years
                    possible_years = fetch_games_data(get_academic_years=True)

                    # Sidebar selectbox for academic year selection
                    selected_year = st.sidebar.selectbox("Select the Academic Year", possible_years)

                    # Fetch games for the selected academic year
                    games_for_selected_year = fetch_games_data(academic_year=selected_year)
                    
                    if games_for_selected_year != []:
                        # Generate game names with class suffixes
                        game_names_with_classes = [
                            f"{game['game_name']}{'' if game['game_class'] == '_' else (' - Class ' + game['game_class'])}"
                            for game in games_for_selected_year
                        ]

                        # Sidebar selectbox for game selection
                        selected_game_with_classes = st.sidebar.selectbox("Select a Game", game_names_with_classes)

                        # Extract game_name and game_class from selected_game_with_classes
                        if " - Class " in selected_game_with_classes:
                            selected_game_name, selected_game_class = selected_game_with_classes.split(" - Class ")
                        else:
                            selected_game_name = selected_game_with_classes
                            selected_game_class = "_"

                        # Find the selected game
                        selected_game = next(
                            (game for game in games_for_selected_year if game['game_name'] == selected_game_name and game['game_class'] == selected_game_class),
                            None
                        )

                        game_id = selected_game['game_id']
                        professor_id = selected_game['created_by']
                        num_rounds = selected_game['number_of_rounds']
                        game_timestamp = selected_game['timestamp_game_creation'] 

                        teams = get_group_ids_from_game_id(game_id)

                        options = ['View Prompts', 'View Chats']
                        selection = st.sidebar.radio(label= 'Select an option', options=options, horizontal=True)

                        st.header(f"{selected_game_name}")

                        with st.expander("Explanation"):
                            # Get the Game explanation from Google Drive using the filename
                            game_explanation = get_text_from_file_aux(f'{professor_id}_{game_id}_{game_timestamp}')
                            if game_explanation:
                                st.write(f"{game_explanation}")
                            else:
                                st.write("No explanation found for this game.")

                        if selection == 'View Prompts':

                            if teams:
                                for i in teams: 
                                    class_ = i[0]
                                    group_id = i[1]
                                    prompts = get_text_from_file_without_timestamp_aux(f'Game{game_id}_Class{class_}_Group{group_id}')

                                    # Display group header
                                    st.write(f"### Class {class_} - Group {group_id}")

                                    # Expandable section for viewing prompts
                                    if prompts:
                                        with st.expander(f"View Prompts"):
                                            st.write(prompts)
                                    else:
                                        st.write(f"No submission found.")

                        elif selection == 'View Chats':

                            # Check if the game is currently enabled
                            round_data = get_round_data(game_id)

                            if round_data:

                                is_enabled = selected_game['available']

                                if is_enabled:
                                    access_disabled = st.button('Disable Student Access to these Negotiation Chats')

                                    if access_disabled: 
                                        update_access_to_chats(0, selected_game['game_id'])
                                        success = st.success('Student Access successfully disabled.')
                                        time.sleep(3)
                                        success.empty()
                                        st.rerun()
                                
                                else:
                                    access_enabled = st.button('Enable Student Access to Negotiation Chats')

                                    if access_enabled: 
                                        update_access_to_chats(1, selected_game['game_id'])
                                        success = st.success('Student Access successfully enabled.')
                                        time.sleep(3)
                                        success.empty()
                                        st.rerun()

                                # Extract unique round numbers
                                unique_rounds = sorted(set(round_ for round_, _, _, _, _, _, _, in round_data))

                                round_options = [f"Round {round_}" for round_ in unique_rounds]
                                selected_round_label = st.sidebar.selectbox("Select Round", round_options)

                                # Extract the selected round number from the label
                                selected_round_number = int(re.search(r'\d+', selected_round_label).group())

                                st.markdown(f"### Round {selected_round_number}")

                                # Ensure unique round-teams combinations
                                unique_round_teams = [(class_1, team_1, class_2, team_2) for round_, class_1, team_1, class_2, team_2, _, _, in round_data if round_ == selected_round_number ]  

                                for class_1, team_1, class_2, team_2 in unique_round_teams:

                                    # Fetch the chat data before creating the expander
                                    chat_buyer = get_text_from_file_aux(f'Game{game_id}_Round{selected_round_number}_Class{class_1}_Group{team_1}_Class{class_2}_Group{team_2}')
                                    chat_seller = get_text_from_file_aux(f'Game{game_id}_Round{selected_round_number}_Class{class_2}_Group{team_2}_Class{class_1}_Group{team_1}')

                                    # Create an expander only if the chat exists
                                    
                                    with st.expander(f"**Class {class_1} - Group {team_1} (Buyer) vs Class {class_2} - Group {team_2} (Seller)**"):
                                        if chat_buyer: st.write(chat_buyer)
                                        else: st.write('Chat not found.')                                            

                                    with st.expander(f"**Class {class_1} - Group {team_1} (Seller) vs Class {class_2} - Group {team_2} (Buyer)**"):
                                        if chat_seller: st.write(chat_seller)
                                        else: st.write('Chat not found.') 

                            else: 
                                st.write('No chats found.')                                           

                    else: 
                        st.write('There are no available games.')    

                case "Leaderboard and Performance":
                    st.write("To be implemented.")

                case "Security":
                    st.write("To be implemented.")
                    
    else:
        st.write('Page accessible only to Professors.')

else:
    st.write('Please Login first (Page accessible only to Professors.)')