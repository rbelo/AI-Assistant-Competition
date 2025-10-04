import streamlit as st
import psycopg2
import pandas as pd
from flask import Flask

app = Flask(__name__)
app.secret_key = 'key' 

# Helper to get the database connection string at runtime
def get_db_connection_string():
    try:
        return st.secrets["database"]["url"]
    except (KeyError, AttributeError) as e:
        print(f"Error accessing database connection string: {str(e)}")
        return None

# Function to populate the 'plays' table with students who match the academic year and class of the created game
def populate_plays_table(game_id, game_academic_year, game_class):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                if game_class == '_':
                    query = """
                    SELECT u.user_id
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL AND u.academic_year = %(param1)s;
                    
                """
                    cur.execute(query, {'param1': game_academic_year})


                else:
                    query = """
                    SELECT u.user_id
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL AND u.academic_year = %(param1)s AND u.class = %(param2)s;
                """
                    cur.execute(query, {'param1': game_academic_year, 'param2': game_class})
                
                students = cur.fetchall()

                if students:

                    # Delete existing rows in the 'plays' table for the given game_id
                    query = """
                        DELETE FROM plays
                        WHERE game_id = %s;
                    """
                    cur.execute(query, (game_id,))

                    # Insert eligible students into 'plays' table
                    query = """
                        INSERT INTO plays (user_id, game_id)
                        VALUES (%(param1)s, %(param2)s);
                    """
                    for student in students:
                        cur.execute(query, {'param1': student[0], 'param2': game_id})

                    return True

                return False
            
    except Exception:
        return False

# Function to retrieve academic year and class combinations
def get_academic_year_class_combinations():
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    SELECT DISTINCT u.academic_year, u.class
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL
                    ORDER BY u.academic_year DESC, u.class ASC;
                """

                cur.execute(query)

                possible_academic_year_class_combs = cur.fetchall()
                
                if possible_academic_year_class_combs:
                    # Process the result into a dictionary
                    combinations = {}
                    for row in possible_academic_year_class_combs:
                        academic_year, class_ = row
                        if academic_year not in combinations:
                            combinations[academic_year] = []
                        combinations[academic_year].append(class_)
                    
                    return combinations
                return False
    
    except Exception:
        return False

# Function to get a game using the game_id
def get_game_by_id(game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    SELECT available, created_by, game_name, number_of_rounds, 
                           name_roles, game_academic_year, game_class, password, timestamp_game_creation, 
                           timestamp_submission_deadline, explanation
                    FROM game
                    WHERE game_id = %s;
                """

                cur.execute(query, (game_id,))

                result = cur.fetchone()
                
                if result:
                    return {
                        "available": result[0],
                        "created_by": result[1],
                        "game_name": result[2],
                        "number_of_rounds": result[3],
                        "name_roles": result[4],
                        "game_academic_year": result[5],
                        "game_class": result[6],
                        "password": result[7],
                        "timestamp_game_creation": result[8],
                        "timestamp_submission_deadline": result[9],
                        "explanation": result[10]
                    }
                return False
            
    except Exception:
        return False

# Function to get all unique academic years or games linked with a specific academic year
def fetch_games_data(academic_year=None, get_academic_years=False):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                if get_academic_years:
                    # Query to get unique academic years
                    query1 = "SELECT DISTINCT game_academic_year FROM game ORDER BY game_academic_year DESC;"

                    cur.execute(query1)

                    return [row[0] for row in cur.fetchall()]

                # Query to fetch games for a specific academic year
                query2 = """
                    SELECT game_id, game_name, game_class, available, created_by, number_of_rounds, 
                           name_roles, game_academic_year, password, timestamp_game_creation, timestamp_submission_deadline, explanation
                    FROM game
                    WHERE game_academic_year = %(param1)s
                    ORDER BY game_id DESC;
                """
                
                cur.execute(query2, {'param1': academic_year})

                games_data = cur.fetchall()
                
                return [
                    {
                        "game_id": row[0],
                        "game_name": row[1],
                        "game_class": row[2],
                        "available": row[3],
                        "created_by": row[4],
                        "number_of_rounds": row[5],
                        "name_roles": row[6],
                        "game_academic_year": row[7],
                        "password": row[8],
                        "timestamp_game_creation": row[9],
                        "timestamp_submission_deadline": row[10],
                        "explanation": row[11] if len(row) > 11 else None
                    }
                    for row in games_data
                ]
    
    except Exception:
        return []
    
# Function to fetch current (or past) games data by user_id
def fetch_current_games_data_by_user_id(sign, user_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = f"""
                    SELECT * 
                    FROM game g JOIN plays p 
                        ON g.game_id = p.game_id                
                    WHERE (p.user_id =  %(param1)s 
                    AND CURRENT_TIMESTAMP {sign} g.timestamp_submission_deadline)
                    ORDER BY g.game_id DESC; """
        
                cur.execute(query , {'param1': user_id})

                games_data = cur.fetchall()
                if games_data:
                    games = []
                    for row in games_data:
                        game = {
                            "game_id": row[0],
                            "available": row[1],
                            "created_by": row[2],
                            "game_name": row[3],
                            "number_of_rounds": row[4],
                            "name_roles": row[5],
                            "game_academic_year": row[6],
                            "game_class": row[7],
                            "password": row[8],
                            "timestamp_game_creation": row[9],
                            "timestamp_submission_deadline": row[10],
                            "explanation": row[11] if len(row) > 11 else None
                        }
                        games.append(game)
            
                    return games
                return []
    
    except Exception:
        return []
    
# Function to retrieve the last gameID from the database and increment it
def get_next_game_id():
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                cur.execute("SELECT MAX(game_id) FROM game;")
         
                # Fetch the result
                last_game_id = cur.fetchone()[0]

                # Increment the last game ID or start at 1 if none exists
                return (last_game_id + 1) if last_game_id is not None else 1
            
    except Exception:
        return False
    
# Function to update game details in the database
def update_game_in_db(game_id, created_by, game_name, number_of_rounds, name_roles, game_academic_year, game_class, password, timestamp_game_creation, submission_deadline, explanation):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query1 = """
                    UPDATE game
                    SET created_by = %(param1)s, game_name = %(param2)s, number_of_rounds = %(param3)s, name_roles = %(param4)s,
                        game_academic_year = %(param5)s, game_class = %(param6)s, password = %(param7)s, timestamp_game_creation = %(param8)s, 
                        timestamp_submission_deadline = %(param9)s, explanation = %(param10)s
                    WHERE game_id = %(param11)s;
                """

                cur.execute(query1, {
                    'param1': created_by, 
                    'param2': game_name, 
                    'param3': number_of_rounds, 
                    'param4': name_roles,
                    'param5': game_academic_year,
                    'param6': game_class,
                    'param7': password, 
                    'param8': timestamp_game_creation,
                    'param9': submission_deadline,
                    'param10': explanation,
                    'param11': game_id
                })

                query2 = """
                    SELECT * 
                    FROM game
                    ORDER BY game_id;
                """

                cur.execute(query2)        

                return True
            
    except Exception:
        return False
    
# Function to update access of negotiation chats to students 
def update_access_to_chats(access, game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query1 = """
                    UPDATE game
                    SET available = %(param1)s
                    WHERE game_id = %(param2)s;
                """

                cur.execute(query1, {
                    'param1': access,
                    'param2': game_id
                })

                query2 = """
                    SELECT * 
                    FROM game
                    ORDER BY game_id;
                """

                cur.execute(query2)

                return True
            
    except Exception:
        return False

# Function to store game details in the database
def store_game_in_db(game_id, available, created_by, game_name, number_of_rounds, name_roles, game_academic_year, game_class, password, timestamp_game_creation, submission_deadline, explanation, game_type="zero_sum"):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First, get the mode_id for the game type
                query_mode = """
                    SELECT mode_id FROM game_modes WHERE mode_name = %(mode)s;
                """
                cur.execute(query_mode, {'mode': game_type})
                mode_result = cur.fetchone()
                
                if not mode_result:
                    # If mode doesn't exist, create it
                    query_insert_mode = """
                        INSERT INTO game_modes (mode_name, description)
                        VALUES (%(mode)s, %(desc)s)
                        RETURNING mode_id;
                    """
                    cur.execute(query_insert_mode, {
                        'mode': game_type,
                        'desc': f'Configuration for {game_type} games'
                    })
                    mode_id = cur.fetchone()[0]
                else:
                    mode_id = mode_result[0]

                # Now insert the game with the mode_id
                query = """
                    INSERT INTO game (game_id, available, created_by, game_name, number_of_rounds, name_roles, 
                                    game_academic_year, game_class, password, timestamp_game_creation, 
                                    timestamp_submission_deadline, explanation, mode_id)
                    VALUES (%(param1)s, %(param2)s, %(param3)s, %(param4)s, %(param5)s, %(param6)s, 
                            %(param7)s, %(param8)s, %(param9)s, %(param10)s, %(param11)s, %(param12)s, %(param13)s);
                """

                cur.execute(query, {
                    'param1': game_id,
                    'param2': available,
                    'param3': created_by, 
                    'param4': game_name, 
                    'param5': number_of_rounds, 
                    'param6': name_roles, 
                    'param7': game_academic_year,
                    'param8': game_class,
                    'param9': password, 
                    'param10': timestamp_game_creation,
                    'param11': submission_deadline,
                    'param12': explanation,
                    'param13': mode_id
                })

                return True
            
    except Exception as e:
        print(f"Error in store_game_in_db: {str(e)}")
        return False
    
# Function to get the group id of the user_id
def get_group_id_from_user_id(user_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = "SELECT group_id FROM user_ WHERE user_id = %(param1)s;"

                cur.execute(query, {'param1': user_id})
                group_id = cur.fetchone()[0]

                return group_id

    except Exception:
        return False
    
# Function to get the academic_year of the user_id
def get_academic_year_from_user_id(user_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = "SELECT academic_year FROM user_ WHERE user_id = %(param1)s;"

                cur.execute(query, {'param1': user_id})
                academic_year = cur.fetchone()[0]

                return academic_year

    except Exception:
        return False

# Function to get the class of the user_id
def get_class_from_user_id(user_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = "SELECT class FROM user_ WHERE user_id = %(param1)s;"

                cur.execute(query, {'param1': user_id})
                group_id = cur.fetchone()[0]

                return group_id

    except Exception:
        return False

# Function to remove a student from the database
def remove_student(user_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = "DELETE FROM plays WHERE user_id = %(param1)s;"
                cur.execute(query, {'param1': user_id})

                query = "DELETE FROM user_ WHERE user_id = %(param1)s;"
                cur.execute(query, {'param1': user_id})
         
                return True
            
    except Exception:
        return False

# Function to fetch student data from the database
def get_students_from_db():
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query = """
                    SELECT u.user_id, u.email, u.group_id, u.academic_year, u.class, u.timestamp_user
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL;
                """
                cur.execute(query)
                
                # Fetch all results from the query
                rows = cur.fetchall()
                
                # If data exists, create a DataFrame
                if rows:
                    # Convert the result set into a pandas DataFrame
                    df = pd.DataFrame(rows, columns=["user_id", "email", "group_id", "academic_year", "class", "timestamp_user"])
                    return df
                else:
                    return pd.DataFrame(columns=["user_id", "email", "group_id", "academic_year", "class", "timestamp_user"])
    
    except Exception:
        return False

# Function to insert email and into the user table
def insert_student_data(user_id, email, temp_password, group_id, academic_year, class_):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                print(f"User ID: {user_id}, Email: {email}, Temp Password: {temp_password}, Group ID: {group_id}, Academic Year: {academic_year}, Class: {class_}")

                # Check if user already exists
                query = "SELECT EXISTS(SELECT 1 FROM user_ WHERE user_id = %(param1)s);"
                
                cur.execute(query, {'param1': user_id})

                exists = cur.fetchone()[0]

                # If exists, we do not add to the table user_
                if exists:
                    return True

                query = """
                    INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
                    VALUES (%(param1)s, %(param2)s, %(param3)s, %(param4)s, %(param5)s, %(param6)s);
                """

                cur.execute(query, {
                    'param1': user_id, 
                    'param2': email, 
                    'param3': temp_password, 
                    'param4': group_id, 
                    'param5': academic_year,
                    'param6': class_
                })

                return True
            
    except Exception:
        return False

# Function to insert round data into the 'round' table
def insert_round_data(game_id, round_number, group1_class, group1_id, group2_class, group2_id, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    INSERT INTO round (game_id, round_number, group1_class, group1_id, group2_class, group2_id, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1)
                    VALUES (%(param1)s, %(param2)s, %(param3)s, %(param4)s, %(param5)s, %(param6)s, %(param7)s, %(param8)s, %(param9)s, %(param10)s);
                """

                cur.execute(query, {
                    'param1': game_id, 
                    'param2': round_number, 
                    'param3': group1_class, 
                    'param4': group1_id, 
                    'param5': group2_class, 
                    'param6': group2_id, 
                    'param7': score_team1_role1, 
                    'param8': score_team2_role2,
                    'param9': score_team1_role2, 
                    'param10': score_team2_role1,
                })
         
                return True
            
    except Exception:
        return False

# Function to get the round information of a specific game from a specific game
def get_round_data(game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = '''SELECT round_number, group1_class, group1_id, group2_class, group2_id, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1
                           FROM round WHERE game_id=%(param1)s;'''

                cur.execute(query,{
                    'param1': game_id
                })

                round_data = cur.fetchall()

                return round_data

    except Exception:
        return False

# Function to get the round information of a specific group from a specific game
def get_round_data_by_class_group_id(game_id, class_, group_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = '''SELECT round_number, group1_class, group1_id, group2_class, group2_id 
                           FROM round 
                           WHERE ((group1_class = %(param2)s AND group1_id = %(param3)s) OR (group2_class = %(param2)s AND group2_id = %(param3)s)) AND game_id=%(param1)s;'''

                cur.execute(query,{
                    'param1': game_id, 
                    'param2': class_,
                    'param3': group_id, 
                })
                round_data = cur.fetchall()

                return round_data

    except Exception:
        return False

# Function to get the ids of the groups that played a specific game
def get_group_ids_from_game_id(game_id): 
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                query = '''SELECT DISTINCT u.class, u.group_id
                        FROM user_ u
                        JOIN plays p ON u.user_id = p.user_id
                        WHERE p.game_id = %(param1)s
                        ORDER BY u.class, u.group_id;''' 

                cur.execute(query, {
                    'param1': game_id})
                
                group_ids = cur.fetchall()
                return group_ids

    except Exception as e:
        print(f"Error in get_group_ids_from_game_id: {e}")
        return False

# Function to check user credentials
def authenticate_user(email, password_hash):
    DB_CONNECTION_STRING = get_db_connection_string()
    print(f"Authenticating user with email: {email} and password hash: {password_hash}")
    print(f"DB_CONNECTION_STRING: {DB_CONNECTION_STRING}")
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            print("Connected to the database")
            with conn.cursor() as cur:
                query = "SELECT 1 FROM user_ WHERE email = %(param1)s AND password = %(param2)s;"
                print(f"Executing query: {query} with params: {email}, {password_hash}")
                cur.execute(query, {'param1': email, 'param2': password_hash})
                print("Query executed successfully")
                result = cur.fetchone()
                if result is None:
                    print("No matching user found")
                    return False
                exists = result[0]
                print(f"Authentication result: {exists}")
                return exists
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return False

# Function to validate if an email belongs to a professor
def is_valid_professor_email(email):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query = "SELECT EXISTS(SELECT 1 FROM user_ WHERE email = %(param1)s);"

                cur.execute(query, {'param1': email})
                
                # Fetch the result
                exists = cur.fetchone()[0]
                
                return exists
            
    except Exception:
        return False

# Function to validate if the user that logged in is a Professor
def is_professor(email):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query = """
                    SELECT EXISTS(
                                  SELECT 1 
                                  FROM professor AS p JOIN user_ AS u
                                    ON p.user_id = u.user_id
                                  WHERE email = %(param1)s);
                """

                cur.execute(query, {'param1': email})
                
                # Fetch the result
                is_prof = cur.fetchone()[0]
                
                return is_prof
            
    except Exception:
        return False

# Function to see if exists the user
def exists_user(email):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query = """
                    SELECT EXISTS(
                                  SELECT 1 
                                  FROM user_ 
                                  WHERE email = %(param1)s);
                """

                cur.execute(query, {'param1': email})
                
                # Fetch the result
                exists = cur.fetchone()[0]
                
                return exists
            
    except Exception:
        return False
    
# Function to update the user's password
def update_password(email, new_password):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query = """
                    UPDATE user_
                    SET password = %(param1)s
                    WHERE email = %(param2)s;
                """
                cur.execute(query, {'param1': new_password, 'param2': email})
                
                return True
            
    except Exception:
        return False
    
# Function to get user_id by email
def get_user_id_by_email(email):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query = "SELECT user_id FROM user_ WHERE email = %(param1)s;"

                cur.execute(query, {'param1': email})
                
                # Fetch the result
                user_id = cur.fetchone()[0]
                
                return user_id
            
    except Exception:
        return False
        
# Function to update the number of rounds of a game
def update_num_rounds_game(num_rounds, game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query1 = """
                    UPDATE game
                    SET number_of_rounds = %(param1)s
                    WHERE game_id = %(param2)s;
                """

                cur.execute(query1, {'param1': num_rounds, 'param2': game_id})

                query2 = """
                    SELECT * 
                    FROM game
                    ORDER BY game_id;
                """

                cur.execute(query2)        

                return True
            
    except Exception:
        return False
    
# Function to extract from the 'round' table all the rows of a specific game where the chats were not successful 
def get_error_matchups(game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query1 = """
                    SELECT round_number, group1_class, group1_id, group2_class, group2_id, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1
                    FROM round
                    WHERE game_id = %(param1)s AND (score_team1_role1=-1 OR score_team1_role2=-1);
                """

                cur.execute(query1, {'param1': game_id})
                error_matchups = cur.fetchall()

                error_matchups_final = []
                for i in error_matchups:
                    aux_1 = [i[0]]
                    aux_2 = [list(i[1:3])]
                    aux_3 = [list(i[3:5])]
                    aux_4 = [1] if i[5]==-1 else [0]
                    aux_5 = [1] if i[7]==-1 else [0]
                    error_matchups_final.append(aux_1+aux_2+aux_3+aux_4+aux_5)

                return error_matchups_final
            
    except Exception:
        return False
    
# Function to update the scores of a specific row in the 'round' table
def update_round_data(game_id, round_number, group1_class, group1_id, group2_class, group2_id, score_team1, score_team2, order):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                if order == 'same':

                    query1 = """
                        UPDATE round
                        SET score_team1_role1 = %(param7)s, score_team2_role2 = %(param8)s
                        WHERE game_id = %(param1)s AND round_number = %(param2)s AND group1_class = %(param3)s AND group1_id = %(param4)s AND group2_class = %(param5)s AND group2_id = %(param6)s;
                    """

                    cur.execute(query1, {
                        'param1': game_id, 
                        'param2': round_number, 
                        'param3': group1_class, 
                        'param4': group1_id,
                        'param5': group2_class,
                        'param6': group2_id,
                        'param7': score_team1, 
                        'param8': score_team2
                    })

                    return True
                
                if order == 'opposite':

                    query1 = """
                        UPDATE round
                        SET score_team1_role2 = %(param7)s, score_team2_role1 = %(param8)s
                        WHERE game_id = %(param1)s AND round_number = %(param2)s AND group1_class = %(param3)s AND group1_id = %(param4)s AND group2_class = %(param5)s AND group2_id = %(param6)s;
                    """

                    cur.execute(query1, {
                        'param1': game_id, 
                        'param2': round_number, 
                        'param3': group1_class, 
                        'param4': group1_id,
                        'param5': group2_class,
                        'param6': group2_id,
                        'param7': score_team1, 
                        'param8': score_team2
                    })     

                    return True
            
    except Exception:
        return False
    
# Function to delete all the rows in the 'round' table that belong to a specific game_id
def delete_from_round(game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                
                query1 = """
                    DELETE FROM round 
                    WHERE game_id = %(param1)s;
                """

                cur.execute(query1, {'param1': game_id}) 

                return True
            
    except Exception:
        return False 
    
# The next four functions enable the Professor to view the Play section exactly as it appears to a student in a specific group
# Function to get all the different academic years of students
def get_academic_years_of_students():
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    SELECT DISTINCT u.academic_year
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL
                    ORDER BY u.academic_year DESC;
                """

                cur.execute(query)
                academic_years_of_students = cur.fetchall()

                academic_years_of_students_final = []
                for i in academic_years_of_students: 
                    academic_years_of_students_final.append(i[0])

                return academic_years_of_students_final
    
    except Exception:
        return False
    
# Function to get all the different classes of students from a specfic academic year
def get_classes_of_students(academic_year):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    SELECT DISTINCT u.class
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL AND u.academic_year = %(param1)s
                    ORDER BY u.class ASC;
                """

                cur.execute(query, {'param1': academic_year})
                classes_of_students = cur.fetchall()

                classes_of_students_final = []
                for i in classes_of_students: 
                    classes_of_students_final.append(i[0])

                return classes_of_students_final
    
    except Exception:
        return False
    
# Function to get all the different groups of students from a specfic class of a specific academic year
def get_groups_of_students(academic_year, class_):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    SELECT DISTINCT u.group_id
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL AND u.academic_year = %(param1)s AND u.class = %(param2)s
                    ORDER BY u.group_id ASC;
                """

                cur.execute(query, {'param1': academic_year, 'param2': class_})
                groups_of_students = cur.fetchall()

                groups_of_students_final = []
                for i in groups_of_students: 
                    groups_of_students_final.append(i[0])

                return groups_of_students_final
    
    except Exception:
        return False
    
# Function to get the user_id of a student from a specific group of a specific class of a specific academic year
def get_user_id_of_student(academic_year, class_, group_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                query = """
                    SELECT u.user_id
                    FROM user_ AS u LEFT JOIN professor AS p 
                        ON u.user_id = p.user_id
                    WHERE p.user_id IS NULL AND u.academic_year = %(param1)s AND u.class = %(param2)s AND u.group_id = %(param3)s
                    ORDER BY u.group_id ASC;
                """

                cur.execute(query, {'param1': academic_year, 'param2': class_, 'param3': group_id})
                user_id = cur.fetchone()[0]
                return user_id

    except Exception:
        return False

# Function to get and compute leaderboard scores for a given academic year
def fetch_and_compute_scores_for_year(selected_year, student = False):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                # SQL Query to compute the leaderboard
                query = """
                    WITH computed_scores_only_year_roles AS (
                        SELECT
                            r.game_id,
                            r.round_number,
                            r.group1_class AS team_class,
                            r.group1_id AS team_id,
                            ((r.score_team1_role1 + r.score_team1_role2) / 2) AS score_team,
                            r.score_team1_role1 AS score_role1,
                            r.score_team1_role2 AS score_role2
                        FROM round AS r
                        JOIN game AS g ON r.game_id = g.game_id
                        WHERE g.game_academic_year = %(param1)s AND g.available IN %(param2)s

                        UNION ALL

                        SELECT
                            r.game_id,
                            r.round_number,
                            r.group2_class AS team_class,
                            r.group2_id AS team_id,
                            ((r.score_team2_role1 + r.score_team2_role2) / 2) AS score_team,
                            r.score_team2_role1 AS score_role1,
                            r.score_team2_role2 AS score_role2
                        FROM round AS r
                        JOIN game AS g ON r.game_id = g.game_id
                        WHERE g.game_academic_year = %(param1)s AND g.available IN %(param2)s
                    ),
                    leaderboard_only_year AS (
                        SELECT
                            team_class,
                            team_id,
                            AVG(score_team) * 100 AS average_score
                        FROM computed_scores_only_year_roles
                        GROUP BY team_class, team_id
                    ),
                    aggregated_scores_roles AS (
                        SELECT
                            team_class,
                            team_id,
                            AVG(score_role1) * 100 AS average_score_role1,
                            AVG(score_role2) * 100 AS average_score_role2
                        FROM computed_scores_only_year_roles
                        GROUP BY team_class, team_id
                    ),
                    leaderboard_roles AS (
                        SELECT
                            team_class,
                            team_id,
                            RANK() OVER (ORDER BY average_score_role1 DESC) AS position_name_roles_1,
                            average_score_role1 AS score_name_roles_1,
                            RANK() OVER (ORDER BY average_score_role2 DESC) AS position_name_roles_2,
                            average_score_role2 AS score_name_roles_2
                        FROM aggregated_scores_roles
                    )
                    SELECT
                        ly.team_class,
                        ly.team_id,
                        ly.average_score AS team_average_score,
                        lr.position_name_roles_1,
                        lr.score_name_roles_1,
                        lr.position_name_roles_2,
                        lr.score_name_roles_2
                    FROM leaderboard_only_year AS ly
                    JOIN leaderboard_roles AS lr
                    ON ly.team_class = lr.team_class AND ly.team_id = lr.team_id
                    ORDER BY ly.average_score DESC;
                """

                # Execute the query with the selected year
                cur.execute(query, {'param1': selected_year, 'param2': (0, 1) if not student else (1,)})

                # Fetch results
                leaderboard = cur.fetchall()

                # Format the results into a list of dictionaries
                return [
                    {
                        "team_class": row[0],
                        "team_id": row[1],
                        "average_score": row[2],
                        "position_name_roles_1": row[3],
                        "score_name_roles_1": row[4],
                        "position_name_roles_2": row[5],
                        "score_name_roles_2": row[6],
                    }
                    for row in leaderboard
                ]

    except Exception:
        return False
    
# Function to get and compute leaderboard scores for a given game_id
def fetch_and_compute_scores_for_year_game(game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:

                # SQL Query to compute the leaderboard
                query = """
                    WITH computed_scores_year_game_roles AS (
                        SELECT
                            r.game_id,
                            r.round_number,
                            r.group1_class AS team_class,
                            r.group1_id AS team_id,
                            ((r.score_team1_role1 + r.score_team1_role2) / 2) AS score_team,
                            r.score_team1_role1 AS score_role1,
                            r.score_team1_role2 AS score_role2
                        FROM round AS r
                        WHERE r.game_id = %(param1)s
                       
                        UNION ALL

                        SELECT
                            r.game_id,
                            r.round_number,
                            r.group2_class AS team_class,
                            r.group2_id AS team_id,
                            ((r.score_team2_role1 + r.score_team2_role2) / 2) AS score_team,
                            r.score_team2_role1 AS score_role1,
                            r.score_team2_role2 AS score_role2
                        FROM round AS r
                        WHERE r.game_id = %(param1)s
                    ),
                    leaderboard_year_game AS (
                        SELECT
                            team_class,
                            team_id,
                            AVG(score_team) * 100 AS average_score
                        FROM computed_scores_year_game_roles
                        GROUP BY team_class, team_id
                    ),
                    aggregated_scores_roles AS (
                        SELECT
                            team_class,
                            team_id,
                            AVG(score_role1) * 100 AS average_score_role1,
                            AVG(score_role2) * 100 AS average_score_role2
                        FROM computed_scores_year_game_roles
                        GROUP BY team_class, team_id
                    ),
                    leaderboard_roles AS (
                        SELECT
                            team_class,
                            team_id,
                            RANK() OVER (ORDER BY average_score_role1 DESC) AS position_name_roles_1,
                            average_score_role1 AS score_name_roles_1,
                            RANK() OVER (ORDER BY average_score_role2 DESC) AS position_name_roles_2,
                            average_score_role2 AS score_name_roles_2
                        FROM aggregated_scores_roles
                    )
                    SELECT
                        lyg.team_class,
                        lyg.team_id,
                        lyg.average_score AS team_average_score,
                        lr.position_name_roles_1,
                        lr.score_name_roles_1,
                        lr.position_name_roles_2,
                        lr.score_name_roles_2
                    FROM leaderboard_year_game AS lyg
                    JOIN leaderboard_roles AS lr
                    ON lyg.team_class = lr.team_class AND lyg.team_id = lr.team_id
                    ORDER BY lyg.average_score DESC;
                """

                # Execute the query with the selected year
                cur.execute(query, {'param1': game_id})
                
                # Fetch results
                leaderboard = cur.fetchall()

                # Format the results into a list of dictionaries
                return [
                    {
                        "team_class": row[0],
                        "team_id": row[1],
                        "average_score": row[2],
                        "position_name_roles_1": row[3],
                        "score_name_roles_1": row[4],
                        "position_name_roles_2": row[5],
                        "score_name_roles_2": row[6],
                    }
                    for row in leaderboard
                ]

    except Exception:
        return False

# Function to store group values in the database
def store_group_values(game_id, class_, group_id, minimizer_value, maximizer_value):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS group_values (
                        game_id INT NOT NULL,
                        class VARCHAR(10) NOT NULL,
                        group_id INT NOT NULL,
                        minimizer_value FLOAT NOT NULL,
                        maximizer_value FLOAT NOT NULL,
                        PRIMARY KEY (game_id, class, group_id),
                        FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
                    );
                """)
                
                # This query inserts a new row. 
                # If a row with the same game_id, class, and group_id already exists (ON CONFLICT),
                # it updates the existing row instead (DO UPDATE SET).
                query = """
                    INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
                    VALUES (%(param1)s, %(param2)s, %(param3)s, %(param4)s, %(param5)s)
                    ON CONFLICT (game_id, class, group_id) 
                    DO UPDATE SET minimizer_value = %(param4)s, maximizer_value = %(param5)s;
                """
                
                cur.execute(query, {
                    'param1': game_id,
                    'param2': class_,
                    'param3': group_id,
                    'param4': minimizer_value,
                    'param5': maximizer_value
                })
                
                return True
    except Exception as e:
        print(f"Error in store_group_values: {e}")
        return False

# Function to store game parameters (bounds)
def store_game_parameters(game_id, min_minimizer, max_minimizer, min_maximizer, max_maximizer):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS group_values (
                        game_id INT NOT NULL,
                        class VARCHAR(10) NOT NULL,
                        group_id INT NOT NULL,
                        minimizer_value FLOAT NOT NULL,
                        maximizer_value FLOAT NOT NULL,
                        PRIMARY KEY (game_id, class, group_id),
                        FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
                    );
                """)
                
                # Store min values in one row using 'params' as class and 0 as group_id
                query = """
                    INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
                    VALUES (%(param1)s, 'params', 0, %(param2)s, %(param3)s)
                    ON CONFLICT (game_id, class, group_id) 
                    DO UPDATE SET minimizer_value = %(param2)s, maximizer_value = %(param3)s;
                """
                
                cur.execute(query, {
                    'param1': game_id,
                    'param2': min_minimizer,
                    'param3': min_maximizer
                })
                
                # Store max values in another row using 'params' as class and 1 as group_id
                query = """
                    INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
                    VALUES (%(param1)s, 'params', 1, %(param2)s, %(param3)s)
                    ON CONFLICT (game_id, class, group_id) 
                    DO UPDATE SET minimizer_value = %(param2)s, maximizer_value = %(param3)s;
                """
                
                cur.execute(query, {
                    'param1': game_id,
                    'param2': max_minimizer,
                    'param3': max_maximizer
                })
                
                return True
    except Exception as e:
        print(f"Error in store_game_parameters: {e}")
        return False

# Function to get group values from database
def get_group_values(game_id, class_, group_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT minimizer_value, maximizer_value
                    FROM group_values
                    WHERE game_id = %(param1)s AND class = %(param2)s AND group_id = %(param3)s;
                """
                
                cur.execute(query, {
                    'param1': game_id,
                    'param2': class_,
                    'param3': group_id
                })
                
                result = cur.fetchone()
                if result:
                    return {
                        "minimizer_value": result[0],
                        "maximizer_value": result[1]
                    }
                return None
    except Exception:
        return None

# Function to get game parameters (bounds)
def get_game_parameters(game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # Retrieve the two rows stored for parameters, ordered by group_id (0 then 1)
                query = """
                    SELECT minimizer_value, maximizer_value
                    FROM group_values
                    WHERE game_id = %(param1)s AND class = 'params'
                    ORDER BY group_id;
                """
                
                cur.execute(query, {'param1': game_id})
                
                results = cur.fetchall()
                # Expecting two rows: one for min values (group_id=0), one for max values (group_id=1)
                if len(results) == 2:
                    return {
                        "min_minimizer": results[0][0], # Min minimizer from row 0
                        "max_minimizer": results[1][0], # Max minimizer from row 1
                        "min_maximizer": results[0][1], # Min maximizer from row 0
                        "max_maximizer": results[1][1]  # Max maximizer from row 1
                    }
                return None
    except Exception as e:
        print(f"Error in get_game_parameters: {e}")
        return None

# Function to get all group values for a game (excluding parameters)
def get_all_group_values(game_id):
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT class, group_id, minimizer_value, maximizer_value
                    FROM group_values
                    WHERE game_id = %(param1)s AND class != 'params'
                    ORDER BY class, group_id;
                """
                
                cur.execute(query, {'param1': game_id})
                
                results = cur.fetchall()
                values = []
                for row in results:
                    values.append({
                        "class": row[0],
                        "group_id": row[1],
                        "minimizer_value": row[2],
                        "maximizer_value": row[3]
                    })
                return values
    except Exception as e:
        print(f"Error in get_all_group_values: {e}")
        return []
