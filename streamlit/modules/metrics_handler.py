import streamlit as st
import psycopg2
import time
from datetime import datetime

# Helper to get the database connection string at runtime

def get_db_connection_string():
    try:
        return st.secrets["database"]["url"]
    except (KeyError, AttributeError) as e:
        print(f"Error accessing database connection string: {str(e)}")
        return None

# --------- Helper Functions ---------

def ensure_user_exists(user_id):
    """
    Ensures a user exists in the user_ table
    
    Args:
        user_id (str): The ID of the user
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    if not DB_CONNECTION_STRING:
        return
        
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First create the user_ table if it doesn't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_ (
                        user_id VARCHAR(50) PRIMARY KEY,
                        email VARCHAR(100) NOT NULL,
                        password VARCHAR(100) NOT NULL,
                        group_id INTEGER,
                        academic_year INTEGER,
                        class VARCHAR(10),
                        timestamp_user TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Check if the user exists
                cur.execute("""
                    SELECT 1 FROM user_ WHERE user_id = %s
                """, (user_id,))
                
                if cur.fetchone() is None:
                    # Create a test user if it doesn't exist
                    cur.execute("""
                        INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id) DO NOTHING
                    """, (user_id, f"{user_id}@placeholder.com", "placeholder_pwd", 1, 2023, 'A'))
    except Exception as e:
        print(f"Error ensuring user exists: {e}")

# --------- Page Time Tracking Functions ---------

def record_page_entry(user_id, page_name):
    """
    Record when a user enters a page
    
    Args:
        user_id (str): The ID of the user
        page_name (str): The name of the page
    
    Returns:
        bool: True if successful, False otherwise
        
    Raises:
        ValueError: If user_id or page_name is None or empty
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    if not page_name or not isinstance(page_name, str):
        raise ValueError("page_name must be a non-empty string")
        
    try:
        # First ensure the user exists
        ensure_user_exists(user_id)
            
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS page_visit (
                        visit_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        page_name VARCHAR(100) NOT NULL,
                        entry_timestamp TIMESTAMP NOT NULL,
                        exit_timestamp TIMESTAMP,
                        duration_seconds FLOAT,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id)
                    );
                """)
                
                # Insert the page entry record
                query = """
                    INSERT INTO page_visit (user_id, page_name, entry_timestamp)
                    VALUES (%s, %s, %s)
                    RETURNING visit_id;
                """
                cur.execute(query, (user_id, page_name, timestamp))
                visit_id = cur.fetchone()[0]
                
                # Store the visit_id in session state for later update
                if 'current_visit_id' not in st.session_state:
                    st.session_state.current_visit_id = {}
                st.session_state.current_visit_id[page_name] = visit_id
                
                return True
    except Exception as e:
        print(f"Error recording page entry: {e}")
        return False

def record_page_exit(page_name, duration=None):
    """
    Record when a user exits a page and calculate the duration
    
    Args:
        page_name (str): The name of the page
        duration (float, optional): The duration in seconds (if already calculated)
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        # Get the visit_id from session state
        if 'current_visit_id' not in st.session_state or page_name not in st.session_state.current_visit_id:
            print(f"No visit_id found for page {page_name}")
            return False
            
        visit_id = st.session_state.current_visit_id[page_name]
        timestamp = datetime.now()
        
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # Get the entry timestamp if we need to calculate duration
                if duration is None:
                    cur.execute("""
                        SELECT entry_timestamp FROM page_visit WHERE visit_id = %s
                    """, (visit_id,))
                    
                    result = cur.fetchone()
                    if result:
                        entry_timestamp = result[0]
                        duration = (timestamp - entry_timestamp).total_seconds()
                    else:
                        duration = 0
                
                # Update the page visit record with exit timestamp and duration
                query = """
                    UPDATE page_visit 
                    SET exit_timestamp = %s, duration_seconds = %s
                    WHERE visit_id = %s
                """
                cur.execute(query, (timestamp, duration, visit_id))
                
                # Clear the visit_id from session state
                del st.session_state.current_visit_id[page_name]
                
                return True
    except Exception as e:
        print(f"Error recording page exit: {e}")
        return False

# --------- Game Interaction Tracking Functions ---------

def record_game_start(user_id, game_id):
    """
    Record when a user starts a game
    
    Args:
        user_id (str): The ID of the user
        game_id (int): The ID of the game
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS game_interaction (
                        interaction_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        game_id INT NOT NULL,
                        start_timestamp TIMESTAMP NOT NULL,
                        end_timestamp TIMESTAMP,
                        duration_seconds FLOAT,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id),
                        FOREIGN KEY(game_id) REFERENCES game(game_id)
                    );
                """)
                
                # Insert the game start record
                query = """
                    INSERT INTO game_interaction (user_id, game_id, start_timestamp)
                    VALUES (%s, %s, %s)
                    RETURNING interaction_id;
                """
                cur.execute(query, (user_id, game_id, timestamp))
                interaction_id = cur.fetchone()[0]
                
                # Store the interaction_id in session state for later update
                if 'current_game_interaction' not in st.session_state:
                    st.session_state.current_game_interaction = {}
                st.session_state.current_game_interaction[game_id] = interaction_id
                
                return True
    except Exception as e:
        print(f"Error recording game start: {e}")
        return False

def record_game_end(user_id, game_id):
    """
    Record when a user finishes a game and calculate duration
    
    Args:
        user_id (str): The ID of the user
        game_id (int): The ID of the game
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # Check if we have a stored interaction_id for this game
                if 'current_game_interaction' in st.session_state and game_id in st.session_state.current_game_interaction:
                    interaction_id = st.session_state.current_game_interaction[game_id]
                    
                    # Get the start timestamp to calculate duration
                    cur.execute("""
                        SELECT start_timestamp FROM game_interaction 
                        WHERE interaction_id = %s
                    """, (interaction_id,))
                    start_timestamp = cur.fetchone()[0]
                    
                    # Calculate duration in seconds
                    duration = (timestamp - start_timestamp).total_seconds()
                    
                    # Update the record with end timestamp and duration
                    query = """
                        UPDATE game_interaction 
                        SET end_timestamp = %s, duration_seconds = %s
                        WHERE interaction_id = %s
                    """
                    cur.execute(query, (timestamp, duration, interaction_id))
                    
                    # Remove the interaction_id from session state
                    del st.session_state.current_game_interaction[game_id]
                    
                    return True
                return False
    except Exception as e:
        print(f"Error recording game end: {e}")
        return False

# --------- Page Visit Frequency Tracking Functions ---------

def increment_page_visit_count(user_id, page_name):
    """
    Increment the visit count for a user on a specific page
    
    Args:
        user_id (str): The ID of the user
        page_name (str): The name of the page
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        # First ensure the user exists
        ensure_user_exists(user_id)
        
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS page_visit_count (
                        user_id VARCHAR(50) NOT NULL,
                        page_name VARCHAR(100) NOT NULL,
                        visit_count INT NOT NULL DEFAULT 1,
                        last_visit TIMESTAMP NOT NULL,
                        PRIMARY KEY(user_id, page_name),
                        FOREIGN KEY(user_id) REFERENCES user_(user_id)
                    );
                """)
                
                # Check if the user already has a record for this page
                cur.execute("""
                    SELECT visit_count FROM page_visit_count
                    WHERE user_id = %s AND page_name = %s
                """, (user_id, page_name))
                
                result = cur.fetchone()
                timestamp = datetime.now()
                
                if result:
                    # Update the existing record
                    cur.execute("""
                        UPDATE page_visit_count
                        SET visit_count = visit_count + 1, last_visit = %s
                        WHERE user_id = %s AND page_name = %s
                    """, (timestamp, user_id, page_name))
                else:
                    # Insert a new record
                    cur.execute("""
                        INSERT INTO page_visit_count (user_id, page_name, visit_count, last_visit)
                        VALUES (%s, %s, 1, %s)
                    """, (user_id, page_name, timestamp))
                
                return True
    except Exception as e:
        print(f"Error incrementing page visit count: {e}")
        return False

# --------- Prompt Submission Tracking Functions ---------

def record_prompt_submission(user_id, game_id, prompt_length_role1, prompt_length_role2, prompt_edits=0):
    """
    Record metrics about a prompt submission
    
    Args:
        user_id (str): The ID of the user
        game_id (int): The ID of the game
        prompt_length_role1 (int): Length of the first role prompt
        prompt_length_role2 (int): Length of the second role prompt
        prompt_edits (int, optional): Number of edits before submission. Defaults to 0.
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_metrics (
                        submission_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        game_id INT NOT NULL,
                        submission_timestamp TIMESTAMP NOT NULL,
                        prompt_length_role1 INT NOT NULL,
                        prompt_length_role2 INT NOT NULL,
                        prompt_edits INT NOT NULL DEFAULT 0,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id),
                        FOREIGN KEY(game_id) REFERENCES game(game_id)
                    );
                """)
                
                # Insert the prompt submission record
                query = """
                    INSERT INTO prompt_metrics 
                    (user_id, game_id, submission_timestamp, prompt_length_role1, prompt_length_role2, prompt_edits)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """
                cur.execute(query, (user_id, game_id, timestamp, prompt_length_role1, prompt_length_role2, prompt_edits))
                
                return True
    except Exception as e:
        print(f"Error recording prompt submission: {e}")
        return False

# --------- First Login Tracking Functions ---------

def record_first_login(user_id):
    """
    Record the first time a user logs into the app
    
    Args:
        user_id (str): The ID of the user
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        # First ensure the user exists
        ensure_user_exists(user_id)
        
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_login (
                        user_id VARCHAR(50) UNIQUE NOT NULL,
                        first_login_timestamp TIMESTAMP NOT NULL,
                        last_login_timestamp TIMESTAMP NOT NULL,
                        login_count INT NOT NULL DEFAULT 1,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id)
                    );
                """)
                
                # Check if this is the first login for the user
                cur.execute("""
                    SELECT user_id FROM user_login
                    WHERE user_id = %s
                """, (user_id,))
                
                if cur.fetchone() is None:
                    # This is the first login, insert a new record
                    cur.execute("""
                        INSERT INTO user_login 
                        (user_id, first_login_timestamp, last_login_timestamp)
                        VALUES (%s, %s, %s);
                    """, (user_id, timestamp, timestamp))
                else:
                    # This is not the first login, update the last login time and increment count
                    cur.execute("""
                        UPDATE user_login
                        SET last_login_timestamp = %s, login_count = login_count + 1
                        WHERE user_id = %s;
                    """, (timestamp, user_id))
                
                return True
    except Exception as e:
        print(f"Error recording login: {e}")
        return False

# --------- Conversation Processing Time Tracking ---------

def record_conversation_processing(game_id, processing_time_seconds, error_occurred=False):
    """
    Record metrics about conversation processing time and errors
    
    Args:
        game_id (int): The ID of the game
        processing_time_seconds (float): Time taken to process the conversation
        error_occurred (bool, optional): Whether an error occurred. Defaults to False.
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_metrics (
                        processing_id SERIAL PRIMARY KEY,
                        game_id INT NOT NULL,
                        processing_timestamp TIMESTAMP NOT NULL,
                        processing_time_seconds FLOAT NOT NULL,
                        error_occurred BOOLEAN NOT NULL DEFAULT FALSE,
                        FOREIGN KEY(game_id) REFERENCES game(game_id)
                    );
                """)
                
                # Insert the conversation processing record
                query = """
                    INSERT INTO conversation_metrics 
                    (game_id, processing_timestamp, processing_time_seconds, error_occurred)
                    VALUES (%s, %s, %s, %s);
                """
                cur.execute(query, (game_id, timestamp, processing_time_seconds, error_occurred))
                
                return True
    except Exception as e:
        print(f"Error recording conversation processing: {e}")
        return False

# --------- Deal Analysis Tracking ---------

def record_deal_analysis(game_id, round_number, group1_id, group2_id, deal_score_role1, deal_score_role2):
    """
    Record metrics about deals and their scores
    
    Args:
        game_id (int): The ID of the game
        round_number (int): The round number
        group1_id (int): ID of first group
        group2_id (int): ID of second group
        deal_score_role1 (float): Score achieved by role 1
        deal_score_role2 (float): Score achieved by role 2
    
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS deal_metrics (
                        deal_id SERIAL PRIMARY KEY,
                        game_id INT NOT NULL,
                        round_number INT NOT NULL,
                        group1_id INT NOT NULL,
                        group2_id INT NOT NULL,
                        deal_timestamp TIMESTAMP NOT NULL,
                        deal_score_role1 FLOAT NOT NULL,
                        deal_score_role2 FLOAT NOT NULL,
                        FOREIGN KEY(game_id) REFERENCES game(game_id)
                    );
                """)
                
                # Insert the deal analysis record
                query = """
                    INSERT INTO deal_metrics 
                    (game_id, round_number, group1_id, group2_id, deal_timestamp, deal_score_role1, deal_score_role2)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
                cur.execute(query, (game_id, round_number, group1_id, group2_id, timestamp, deal_score_role1, deal_score_role2))
                
                return True
    except Exception as e:
        print(f"Error recording deal analysis: {e}")
        return False

# --------- Testing Functions ---------

def test_database_tables():
    """
    Test if all the metric tables have been correctly created
    
    Returns:
        dict: A dictionary with table names as keys and boolean values indicating if they exist
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    tables = [
        'page_visit', 
        'game_interaction', 
        'page_visit_count', 
        'prompt_metrics', 
        'user_login', 
        'conversation_metrics', 
        'deal_metrics'
    ]
    
    results = {}
    
    try:
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                for table in tables:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = %s
                        );
                    """, (table,))
                    
                    results[table] = cur.fetchone()[0]
                
        return results
    except Exception as e:
        print(f"Error testing database tables: {e}")
        return {table: False for table in tables}

# --------- Game Interaction Metrics ---------

def record_game_interaction(user_id, game_type, game_id, completion_time, score):
    """
    Record a game interaction
    
    Args:
        user_id (str): The ID of the user
        game_type (str): The type of game played (decision_game, negotiation_game, etc.)
        game_id (str): The unique ID of the game session
        completion_time (int): Time in seconds to complete the game
        score (int): The score achieved in the game
        
    Returns:
        bool: True if successful, False otherwise
    Raises:
        ValueError: If any argument is None or invalid
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    if not game_type or not isinstance(game_type, str):
        raise ValueError("game_type must be a non-empty string")
    if not game_id or not isinstance(game_id, str):
        raise ValueError("game_id must be a non-empty string")
    if not isinstance(completion_time, int) or completion_time < 0:
        raise ValueError("completion_time must be a non-negative integer")
    if not isinstance(score, int) or not (0 <= score <= 100):
        raise ValueError("score must be an integer between 0 and 100")
    try:
        # Ensure test user exists if this is a test
        if user_id == "test_user":
            ensure_user_exists(user_id)
            
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS game_interaction (
                        interaction_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        game_type VARCHAR(50) NOT NULL,
                        game_id VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        completion_time INTEGER NOT NULL,
                        score INTEGER NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id)
                    );
                """)
                
                # Insert the game interaction record
                query = """
                    INSERT INTO game_interaction 
                    (user_id, game_type, game_id, timestamp, completion_time, score)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cur.execute(query, (user_id, game_type, game_id, timestamp, completion_time, score))
                return True
    except Exception as e:
        print(f"Error recording game interaction: {e}")
        return False

# --------- Prompt Statistics Tracking ---------

def record_prompt_metrics(user_id, prompt_text, response_time):
    """
    Record detailed metrics about an AI prompt
    
    Args:
        user_id (str): The ID of the user
        prompt_text (str): The text of the prompt
        response_time (float): Time in seconds for the AI to respond
        
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        # First ensure the user exists
        ensure_user_exists(user_id)
        
        # Calculate word and character counts
        word_count = len(prompt_text.split())
        char_count = len(prompt_text)
        timestamp = datetime.now()
            
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_metrics (
                        prompt_id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        prompt_text TEXT NOT NULL,
                        word_count INTEGER NOT NULL,
                        character_count INTEGER NOT NULL,
                        response_time FLOAT NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id)
                    );
                """)
                
                # Insert the prompt metrics record
                query = """
                    INSERT INTO prompt_metrics 
                    (user_id, timestamp, prompt_text, word_count, character_count, response_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cur.execute(query, (user_id, timestamp, prompt_text, word_count, char_count, response_time))
                return True
    except Exception as e:
        print(f"Error recording prompt metrics: {e}")
        return False

# --------- Conversation Metrics ---------

def record_conversation_metrics(user_id, conversation_id, total_exchanges, conversation_duration):
    """
    Record metrics about a conversation
    
    Args:
        user_id (str): The ID of the user
        conversation_id (str): Unique identifier for the conversation
        total_exchanges (int): Total number of back-and-forth exchanges
        conversation_duration (int): Duration of conversation in seconds
        
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        # First ensure the user exists
        ensure_user_exists(user_id)
            
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_metrics (
                        conversation_id VARCHAR(50) PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        total_exchanges INTEGER NOT NULL,
                        conversation_duration INTEGER NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id)
                    );
                """)
                
                # Insert the conversation metrics record
                query = """
                    INSERT INTO conversation_metrics 
                    (conversation_id, user_id, timestamp, total_exchanges, conversation_duration)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (conversation_id) DO UPDATE SET
                        total_exchanges = EXCLUDED.total_exchanges,
                        conversation_duration = EXCLUDED.conversation_duration
                """
                cur.execute(query, (
                    conversation_id, 
                    user_id, 
                    timestamp, 
                    total_exchanges, 
                    conversation_duration
                ))
                return True
    except Exception as e:
        print(f"Error recording conversation metrics: {e}")
        return False

# --------- Deal Metrics ---------

def record_deal_metrics(user_id, deal_id, negotiation_rounds, deal_success, deal_value=None):
    """
    Record metrics about a deal (should be called when a structured deal form is submitted)
    
    Args:
        user_id (str): The ID of the user
        deal_id (str): Unique identifier for the deal
        negotiation_rounds (int): Number of negotiation rounds
        deal_success (bool): Whether the deal was successful
        deal_value (float, optional): Value of the deal if explicitly provided
        
    Returns:
        bool: True if successful, False otherwise
    """
    DB_CONNECTION_STRING = get_db_connection_string()
    try:
        # First ensure the user exists
        ensure_user_exists(user_id)
            
        timestamp = datetime.now()
        with psycopg2.connect(DB_CONNECTION_STRING) as conn:
            with conn.cursor() as cur:
                # First check if the table exists, if not create it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS deal_metrics (
                        deal_id VARCHAR(50) PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        deal_value FLOAT,
                        negotiation_rounds INTEGER NOT NULL,
                        deal_success BOOLEAN NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES user_(user_id)
                    );
                """)
                
                # Insert the deal metrics record
                query = """
                    INSERT INTO deal_metrics 
                    (deal_id, user_id, timestamp, deal_value, negotiation_rounds, deal_success)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (deal_id) DO UPDATE SET
                        deal_value = EXCLUDED.deal_value,
                        negotiation_rounds = EXCLUDED.negotiation_rounds,
                        deal_success = EXCLUDED.deal_success
                """
                cur.execute(query, (
                    deal_id, 
                    user_id, 
                    timestamp, 
                    deal_value, 
                    negotiation_rounds, 
                    deal_success
                ))
                return True
    except Exception as e:
        print(f"Error recording deal metrics: {e}")
        return False 