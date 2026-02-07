import logging
import os

import pandas as pd
import psycopg2
from cryptography.fernet import Fernet, InvalidToken
from flask import Flask

import streamlit as st

app = Flask(__name__)
app.secret_key = "key"
logger = logging.getLogger(__name__)


# Helper to get the database connection string at runtime
def get_db_connection_string():
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    try:
        return st.secrets["database"]["url"]
    except (KeyError, AttributeError) as e:
        print(f"Error accessing database connection string: {str(e)}")
        return None


def _get_api_key_cipher():
    key = os.getenv("API_KEY_ENCRYPTION_KEY") or st.secrets.get("app", {}).get("api_key_encryption_key")
    if not key:
        print("API_KEY_ENCRYPTION_KEY not set. Unable to encrypt/decrypt instructor API keys.")
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        print(f"Invalid API_KEY_ENCRYPTION_KEY: {exc}")
        return None


# Try to use st.cache_resource if available, otherwise use identity decorator
def _identity_decorator(func):
    """Identity decorator for non-Streamlit contexts."""
    return func


_cache_decorator = getattr(st, "cache_resource", _identity_decorator)


@_cache_decorator
def _get_cached_connection():
    """Get a cached database connection. Cached via st.cache_resource when available."""
    url = get_db_connection_string()
    if not url:
        return None
    return psycopg2.connect(url)


def get_connection():
    """
    Get a database connection.

    Uses cached connection in Streamlit context, fresh connection otherwise.
    This function is the single point to mock in tests.
    """
    try:
        # Try to use cached connection
        conn = _get_cached_connection()
        # Verify connection is still alive
        if conn and not conn.closed:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                # Connection died, clear cache and get new one
                if hasattr(st, "cache_resource"):
                    st.cache_resource.clear()
                return _get_cached_connection()

        # Force a reconnection when cached connection exists but is closed
        if conn and conn.closed and hasattr(st, "cache_resource"):
            st.cache_resource.clear()
            return _get_cached_connection()

        return conn
    except Exception:
        # Fallback for non-Streamlit context (tests, scripts)
        url = get_db_connection_string()
        return psycopg2.connect(url) if url else None


# Function to populate the 'plays' table with students who match the academic year and class of the created game
def populate_plays_table(game_id, game_academic_year, game_class):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            if game_class == "_":
                query = """
                SELECT u.user_id
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL AND u.academic_year = %(param1)s;

            """
                cur.execute(query, {"param1": game_academic_year})

            else:
                query = """
                SELECT u.user_id
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL AND u.academic_year = %(param1)s AND u.class = %(param2)s;
            """
                cur.execute(query, {"param1": game_academic_year, "param2": game_class})

            students = cur.fetchall()

            # Always clear previous assignments first so game edits cannot retain stale players.
            query = """
                DELETE FROM plays
                WHERE game_id = %s;
            """
            cur.execute(query, (game_id,))

            if not students:
                logger.warning(
                    "No students found for game %s (year=%s, class=%s)",
                    game_id,
                    game_academic_year,
                    game_class,
                )
                conn.commit()
                return False

            # Insert eligible students into 'plays' table
            query = """
                INSERT INTO plays (user_id, game_id)
                VALUES (%(param1)s, %(param2)s);
            """
            for student in students:
                cur.execute(query, {"param1": student[0], "param2": game_id})

            conn.commit()
            return True

    except Exception:
        logger.exception("populate_plays_table failed for game %s", game_id)
        conn.rollback()
        return False


# Function to retrieve academic year and class combinations
def get_academic_year_class_combinations():
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT DISTINCT u.academic_year, u.class
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL
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
    conn = get_connection()
    if not conn:
        return False
    try:
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
                    "explanation": result[10],
                }
            return False

    except Exception:
        return False


# Function to get all unique academic years or games linked with a specific academic year
def fetch_games_data(academic_year=None, get_academic_years=False):
    conn = get_connection()
    if not conn:
        return []
    try:
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

            cur.execute(query2, {"param1": academic_year})

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
                    "explanation": row[11] if len(row) > 11 else None,
                }
                for row in games_data
            ]

    except Exception:
        return []


# Function to fetch current (or past) games data by user_id
def fetch_current_games_data_by_user_id(sign, user_id):
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            operator_by_sign = {
                "<": "<",
                ">": ">",
            }
            operator = operator_by_sign.get(sign)
            if not operator:
                logger.warning("Invalid sign passed to fetch_current_games_data_by_user_id: %s", sign)
                return []

            query = f"""
                SELECT *
                FROM game g JOIN plays p
                    ON g.game_id = p.game_id
                WHERE (p.user_id =  %(param1)s
                AND CURRENT_TIMESTAMP {operator} g.timestamp_submission_deadline)
                ORDER BY g.game_id DESC; """

            cur.execute(query, {"param1": user_id})

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
                        "explanation": row[11] if len(row) > 11 else None,
                    }
                    games.append(game)

                return games
            return []

    except Exception:
        return []


# Function to retrieve the last gameID from the database and increment it
def get_next_game_id():
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            cur.execute("SELECT MAX(game_id) FROM game;")

            # Fetch the result
            last_game_id = cur.fetchone()[0]

            # Increment the last game ID or start at 1 if none exists
            return (last_game_id + 1) if last_game_id is not None else 1

    except Exception:
        return False


# Function to update game details in the database
def update_game_in_db(
    game_id,
    created_by,
    game_name,
    number_of_rounds,
    name_roles,
    game_academic_year,
    game_class,
    password,
    timestamp_game_creation,
    submission_deadline,
    explanation,
):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query1 = """
                UPDATE game
                SET created_by = %(param1)s, game_name = %(param2)s, number_of_rounds = %(param3)s, name_roles = %(param4)s,
                    game_academic_year = %(param5)s, game_class = %(param6)s, password = %(param7)s, timestamp_game_creation = %(param8)s,
                    timestamp_submission_deadline = %(param9)s, explanation = %(param10)s
                WHERE game_id = %(param11)s;
            """

            cur.execute(
                query1,
                {
                    "param1": created_by,
                    "param2": game_name,
                    "param3": number_of_rounds,
                    "param4": name_roles,
                    "param5": game_academic_year,
                    "param6": game_class,
                    "param7": password,
                    "param8": timestamp_game_creation,
                    "param9": submission_deadline,
                    "param10": explanation,
                    "param11": game_id,
                },
            )

            query2 = """
                SELECT *
                FROM game
                ORDER BY game_id;
            """

            cur.execute(query2)

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


# Function to update access of negotiation chats to students
def update_access_to_chats(access, game_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query1 = """
                UPDATE game
                SET available = %(param1)s
                WHERE game_id = %(param2)s;
            """

            cur.execute(query1, {"param1": access, "param2": game_id})

            query2 = """
                SELECT *
                FROM game
                ORDER BY game_id;
            """

            cur.execute(query2)

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


# Function to store game details in the database
def store_game_in_db(
    game_id,
    available,
    created_by,
    game_name,
    number_of_rounds,
    name_roles,
    game_academic_year,
    game_class,
    password,
    timestamp_game_creation,
    submission_deadline,
    explanation,
    game_type="zero_sum",
):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            # First, get the mode_id for the game type
            query_mode = """
                SELECT mode_id FROM game_modes WHERE mode_name = %(mode)s;
            """
            cur.execute(query_mode, {"mode": game_type})
            mode_result = cur.fetchone()

            if not mode_result:
                # If mode doesn't exist, create it
                query_insert_mode = """
                    INSERT INTO game_modes (mode_name, description)
                    VALUES (%(mode)s, %(desc)s)
                    RETURNING mode_id;
                """
                cur.execute(query_insert_mode, {"mode": game_type, "desc": f"Configuration for {game_type} games"})
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

            cur.execute(
                query,
                {
                    "param1": game_id,
                    "param2": available,
                    "param3": created_by,
                    "param4": game_name,
                    "param5": number_of_rounds,
                    "param6": name_roles,
                    "param7": game_academic_year,
                    "param8": game_class,
                    "param9": password,
                    "param10": timestamp_game_creation,
                    "param11": submission_deadline,
                    "param12": explanation,
                    "param13": mode_id,
                },
            )

            conn.commit()
            return True

    except Exception as e:
        conn.rollback()
        print(f"Error in store_game_in_db: {str(e)}")
        return False


# Function to get the group id of the user_id
def get_group_id_from_user_id(user_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = "SELECT group_id FROM user_ WHERE user_id = %(param1)s;"

            cur.execute(query, {"param1": user_id})
            group_id = cur.fetchone()[0]

            return group_id

    except Exception:
        return False


# Function to get the academic_year of the user_id
def get_academic_year_from_user_id(user_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = "SELECT academic_year FROM user_ WHERE user_id = %(param1)s;"

            cur.execute(query, {"param1": user_id})
            academic_year = cur.fetchone()[0]

            return academic_year

    except Exception:
        return False


# Function to get the class of the user_id
def get_class_from_user_id(user_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = "SELECT class FROM user_ WHERE user_id = %(param1)s;"

            cur.execute(query, {"param1": user_id})
            group_id = cur.fetchone()[0]

            return group_id

    except Exception:
        return False


# Function to remove a student from the database
def remove_student(user_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = "DELETE FROM plays WHERE user_id = %(param1)s;"
            cur.execute(query, {"param1": user_id})

            query = "DELETE FROM user_ WHERE user_id = %(param1)s;"
            cur.execute(query, {"param1": user_id})

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


# Function to fetch student data from the database
def get_students_from_db():
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT u.user_id, u.email, u.group_id, u.academic_year, u.class, u.timestamp_user
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL;
            """
            cur.execute(query)

            # Fetch all results from the query
            rows = cur.fetchall()

            # If data exists, create a DataFrame
            if rows:
                # Convert the result set into a pandas DataFrame
                df = pd.DataFrame(
                    rows, columns=["user_id", "email", "group_id", "academic_year", "class", "timestamp_user"]
                )
                return df
            else:
                return pd.DataFrame(
                    columns=["user_id", "email", "group_id", "academic_year", "class", "timestamp_user"]
                )

    except Exception:
        return False


# Function to insert email and into the user table
def insert_student_data(user_id, email, temp_password, group_id, academic_year, class_):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            print(
                f"User ID: {user_id}, Email: {email}, Temp Password: {temp_password}, Group ID: {group_id}, Academic Year: {academic_year}, Class: {class_}"
            )

            # Check if user already exists
            query = "SELECT EXISTS(SELECT 1 FROM user_ WHERE user_id = %(param1)s);"

            cur.execute(query, {"param1": user_id})

            exists = cur.fetchone()[0]

            # If exists, we do not add to the table user_
            if exists:
                return True

            query = """
                INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
                VALUES (%(param1)s, %(param2)s, %(param3)s, %(param4)s, %(param5)s, %(param6)s);
            """

            cur.execute(
                query,
                {
                    "param1": user_id,
                    "param2": email,
                    "param3": temp_password,
                    "param4": group_id,
                    "param5": academic_year,
                    "param6": class_,
                },
            )

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


# Function to insert round data into the 'round' table
def insert_round_data(
    game_id,
    round_number,
    group1_class,
    group1_id,
    group2_class,
    group2_id,
    score_team1_role1,
    score_team2_role2,
    score_team1_role2,
    score_team2_role1,
):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                INSERT INTO round (game_id, round_number, group1_class, group1_id, group2_class, group2_id, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1)
                VALUES (%(param1)s, %(param2)s, %(param3)s, %(param4)s, %(param5)s, %(param6)s, %(param7)s, %(param8)s, %(param9)s, %(param10)s);
            """

            cur.execute(
                query,
                {
                    "param1": game_id,
                    "param2": round_number,
                    "param3": group1_class,
                    "param4": group1_id,
                    "param5": group2_class,
                    "param6": group2_id,
                    "param7": score_team1_role1,
                    "param8": score_team2_role2,
                    "param9": score_team1_role2,
                    "param10": score_team2_role1,
                },
            )

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


# Function to get the round information of a specific game from a specific game
def get_round_data(game_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """SELECT round_number, group1_class, group1_id, group2_class, group2_id, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1
                       FROM round WHERE game_id=%(param1)s;"""

            cur.execute(query, {"param1": game_id})

            round_data = cur.fetchall()

            return round_data

    except Exception:
        return False


# Function to store a negotiation chat transcript
def insert_negotiation_chat(
    game_id,
    round_number,
    group1_class,
    group1_id,
    group2_class,
    group2_id,
    transcript,
    summary=None,
    deal_value=None,
):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'negotiation_chat';
                """)
            columns = {row[0] for row in cur.fetchall()}

            insert_cols = [
                "game_id",
                "round_number",
                "group1_class",
                "group1_id",
                "group2_class",
                "group2_id",
                "transcript",
            ]
            values = {
                "game_id": game_id,
                "round_number": round_number,
                "group1_class": group1_class,
                "group1_id": group1_id,
                "group2_class": group2_class,
                "group2_id": group2_id,
                "transcript": transcript,
            }

            update_cols = ["transcript = EXCLUDED.transcript"]
            if "summary" in columns:
                insert_cols.append("summary")
                values["summary"] = summary
                update_cols.append("summary = EXCLUDED.summary")
            if "deal_value" in columns:
                insert_cols.append("deal_value")
                values["deal_value"] = deal_value
                update_cols.append("deal_value = EXCLUDED.deal_value")

            cols_sql = ", ".join(insert_cols)
            params_sql = ", ".join(f"%({col})s" for col in insert_cols)
            update_sql = ", ".join(update_cols + ["updated_at = CURRENT_TIMESTAMP"])
            query = f"""
                INSERT INTO negotiation_chat (
                    {cols_sql}
                )
                VALUES ({params_sql})
                ON CONFLICT (game_id, round_number, group1_class, group1_id, group2_class, group2_id)
                DO UPDATE SET {update_sql};
            """

            cur.execute(query, values)

            conn.commit()
            return True
    except Exception:
        conn.rollback()
        return False


# Function to retrieve a negotiation chat transcript
def get_negotiation_chat(game_id, round_number, group1_class, group1_id, group2_class, group2_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            query = """
                SELECT transcript
                FROM negotiation_chat
                WHERE game_id = %(param1)s AND round_number = %(param2)s
                AND group1_class = %(param3)s AND group1_id = %(param4)s
                AND group2_class = %(param5)s AND group2_id = %(param6)s;
            """
            cur.execute(
                query,
                {
                    "param1": game_id,
                    "param2": round_number,
                    "param3": group1_class,
                    "param4": group1_id,
                    "param5": group2_class,
                    "param6": group2_id,
                },
            )

            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def get_negotiation_chat_details(game_id, round_number, group1_class, group1_id, group2_class, group2_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'negotiation_chat';
                """)
            columns = {row[0] for row in cur.fetchall()}
            select_cols = ["transcript"]
            if "summary" in columns:
                select_cols.append("summary")
            if "deal_value" in columns:
                select_cols.append("deal_value")
            cols_sql = ", ".join(select_cols)
            query = f"""
                SELECT {cols_sql}
                FROM negotiation_chat
                WHERE game_id = %(param1)s AND round_number = %(param2)s
                AND group1_class = %(param3)s AND group1_id = %(param4)s
                AND group2_class = %(param5)s AND group2_id = %(param6)s;
            """
            cur.execute(
                query,
                {
                    "param1": game_id,
                    "param2": round_number,
                    "param3": group1_class,
                    "param4": group1_id,
                    "param5": group2_class,
                    "param6": group2_id,
                },
            )
            row = cur.fetchone()
            if not row:
                return None
            row_data = dict(zip(select_cols, row))
            return {
                "transcript": row_data.get("transcript"),
                "summary": row_data.get("summary"),
                "deal_value": row_data.get("deal_value"),
            }
    except Exception:
        return None


def upsert_game_simulation_params(
    game_id,
    model,
    conversation_order,
    starting_message,
    num_turns,
    negotiation_termination_message,
    summary_prompt,
    summary_termination_message,
):
    """Insert or update simulation parameters for a game."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_simulation_params (
                    game_id INT PRIMARY KEY,
                    model TEXT NOT NULL,
                    conversation_order TEXT NOT NULL,
                    starting_message TEXT NOT NULL,
                    num_turns INT NOT NULL,
                    negotiation_termination_message TEXT NOT NULL,
                    summary_prompt TEXT NOT NULL,
                    summary_termination_message TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
                );
                """)
            query = """
                INSERT INTO game_simulation_params (
                    game_id,
                    model,
                    conversation_order,
                    starting_message,
                    num_turns,
                    negotiation_termination_message,
                    summary_prompt,
                    summary_termination_message,
                    updated_at
                )
                VALUES (
                    %(game_id)s,
                    %(model)s,
                    %(conversation_order)s,
                    %(starting_message)s,
                    %(num_turns)s,
                    %(negotiation_termination_message)s,
                    %(summary_prompt)s,
                    %(summary_termination_message)s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (game_id)
                DO UPDATE SET
                    model = EXCLUDED.model,
                    conversation_order = EXCLUDED.conversation_order,
                    starting_message = EXCLUDED.starting_message,
                    num_turns = EXCLUDED.num_turns,
                    negotiation_termination_message = EXCLUDED.negotiation_termination_message,
                    summary_prompt = EXCLUDED.summary_prompt,
                    summary_termination_message = EXCLUDED.summary_termination_message,
                    updated_at = CURRENT_TIMESTAMP;
            """
            cur.execute(
                query,
                {
                    "game_id": game_id,
                    "model": model,
                    "conversation_order": conversation_order,
                    "starting_message": starting_message,
                    "num_turns": num_turns,
                    "negotiation_termination_message": negotiation_termination_message,
                    "summary_prompt": summary_prompt,
                    "summary_termination_message": summary_termination_message,
                },
            )
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error in upsert_game_simulation_params: {e}")
        return False


def get_game_simulation_params(game_id):
    """Fetch simulation parameters for a game."""
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_simulation_params (
                    game_id INT PRIMARY KEY,
                    model TEXT NOT NULL,
                    conversation_order TEXT NOT NULL,
                    starting_message TEXT NOT NULL,
                    num_turns INT NOT NULL,
                    negotiation_termination_message TEXT NOT NULL,
                    summary_prompt TEXT NOT NULL,
                    summary_termination_message TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
                );
                """)
            query = """
                SELECT model, conversation_order, starting_message, num_turns,
                       negotiation_termination_message, summary_prompt, summary_termination_message
                FROM game_simulation_params
                WHERE game_id = %(game_id)s;
            """
            cur.execute(query, {"game_id": game_id})
            row = cur.fetchone()
            if not row:
                return None
            return {
                "model": row[0],
                "conversation_order": row[1],
                "starting_message": row[2],
                "num_turns": row[3],
                "negotiation_termination_message": row[4],
                "summary_prompt": row[5],
                "summary_termination_message": row[6],
            }
    except Exception as e:
        print(f"Error in get_game_simulation_params: {e}")
        return None


def delete_negotiation_chats(game_id):
    """Delete negotiation chats for a game."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            query = """
                DELETE FROM negotiation_chat
                WHERE game_id = %(game_id)s;
            """
            cur.execute(query, {"game_id": game_id})
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error in delete_negotiation_chats: {e}")
        return False


def insert_playground_result(
    user_id,
    class_,
    group_id,
    role1_name,
    role2_name,
    transcript,
    summary=None,
    deal_value=None,
    score_role1=None,
    score_role2=None,
    model=None,
):
    """Store a playground negotiation transcript."""
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS playground_result (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    class VARCHAR(10) NOT NULL,
                    group_id INT NOT NULL,
                    role1_name TEXT,
                    role2_name TEXT,
                    transcript TEXT NOT NULL,
                    model TEXT,
                    summary TEXT,
                    deal_value FLOAT,
                    score_role1 FLOAT,
                    score_role2 FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'playground_result';
                """)
            columns = {row[0] for row in cur.fetchall()}
            if "model" not in columns:
                cur.execute("""
                    ALTER TABLE playground_result
                    ADD COLUMN model TEXT;
                    """)
                columns.add("model")

            insert_cols = ["user_id", "class", "group_id", "role1_name", "role2_name", "transcript"]
            values = {
                "user_id": user_id,
                "class": class_,
                "group_id": group_id,
                "role1_name": role1_name,
                "role2_name": role2_name,
                "transcript": transcript,
            }

            if "summary" in columns:
                insert_cols.append("summary")
                values["summary"] = summary
            if "deal_value" in columns:
                insert_cols.append("deal_value")
                values["deal_value"] = deal_value
            if "score_role1" in columns:
                insert_cols.append("score_role1")
                values["score_role1"] = score_role1
            if "score_role2" in columns:
                insert_cols.append("score_role2")
                values["score_role2"] = score_role2
            if "model" in columns:
                insert_cols.append("model")
                values["model"] = model

            cols_sql = ", ".join(insert_cols)
            params_sql = ", ".join(f"%({col})s" for col in insert_cols)
            query = f"""
                INSERT INTO playground_result (
                    {cols_sql}
                )
                VALUES (
                    {params_sql}
                )
                RETURNING id;
            """
            cur.execute(query, values)
            result_id = cur.fetchone()[0]
            cur.execute(
                """
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (ORDER BY created_at DESC) AS rn
                    FROM playground_result
                    WHERE user_id = %(user_id)s
                      AND class = %(class)s
                      AND group_id = %(group_id)s
                )
                DELETE FROM playground_result
                WHERE id IN (SELECT id FROM ranked WHERE rn > 20);
                """,
                {
                    "user_id": user_id,
                    "class": class_,
                    "group_id": group_id,
                },
            )
            conn.commit()
            return result_id
    except Exception as e:
        conn.rollback()
        print(f"Error in insert_playground_result: {e}")
        return None


def get_playground_results(user_id, class_, group_id, limit=20):
    """Fetch playground results for a user/group."""
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS playground_result (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    class VARCHAR(10) NOT NULL,
                    group_id INT NOT NULL,
                    role1_name TEXT,
                    role2_name TEXT,
                    transcript TEXT NOT NULL,
                    summary TEXT,
                    deal_value FLOAT,
                    score_role1 FLOAT,
                    score_role2 FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'playground_result';
                """)
            columns = {row[0] for row in cur.fetchall()}
            select_cols = ["id", "role1_name", "role2_name", "transcript"]
            if "summary" in columns:
                select_cols.append("summary")
            if "deal_value" in columns:
                select_cols.append("deal_value")
            if "score_role1" in columns:
                select_cols.append("score_role1")
            if "score_role2" in columns:
                select_cols.append("score_role2")
            if "model" in columns:
                select_cols.append("model")
            select_cols.append("created_at")
            cols_sql = ", ".join(select_cols)
            query = f"""
                SELECT {cols_sql}
                FROM playground_result
                WHERE user_id = %(user_id)s
                  AND class = %(class)s
                  AND group_id = %(group_id)s
                ORDER BY created_at DESC
                LIMIT %(limit)s;
            """
            cur.execute(
                query,
                {
                    "user_id": user_id,
                    "class": class_,
                    "group_id": group_id,
                    "limit": limit,
                },
            )
            rows = cur.fetchall()
            results = []
            for row in rows:
                row_data = dict(zip(select_cols, row))
                results.append(
                    {
                        "id": row_data.get("id"),
                        "role1_name": row_data.get("role1_name"),
                        "role2_name": row_data.get("role2_name"),
                        "transcript": row_data.get("transcript"),
                        "summary": row_data.get("summary"),
                        "deal_value": row_data.get("deal_value"),
                        "score_role1": row_data.get("score_role1"),
                        "score_role2": row_data.get("score_role2"),
                        "model": row_data.get("model"),
                        "created_at": row_data.get("created_at"),
                    }
                )
            return results
    except Exception as e:
        print(f"Error in get_playground_results: {e}")
        return []


def delete_playground_result(result_id, user_id, class_, group_id):
    """Delete a single playground result."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            query = """
                DELETE FROM playground_result
                WHERE id = %(result_id)s
                  AND user_id = %(user_id)s
                  AND class = %(class)s
                  AND group_id = %(group_id)s;
            """
            cur.execute(
                query,
                {
                    "result_id": result_id,
                    "user_id": user_id,
                    "class": class_,
                    "group_id": group_id,
                },
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error in delete_playground_result: {e}")
        return False


def delete_all_playground_results(user_id, class_, group_id):
    """Delete all playground results for a user/group."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            query = """
                DELETE FROM playground_result
                WHERE user_id = %(user_id)s
                  AND class = %(class)s
                  AND group_id = %(group_id)s;
            """
            cur.execute(
                query,
                {
                    "user_id": user_id,
                    "class": class_,
                    "group_id": group_id,
                },
            )
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error in delete_all_playground_results: {e}")
        return False


# Function to get the round information of a specific group from a specific game
def get_round_data_by_class_group_id(game_id, class_, group_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """SELECT round_number, group1_class, group1_id, group2_class, group2_id
                       FROM round
                       WHERE ((group1_class = %(param2)s AND group1_id = %(param3)s) OR (group2_class = %(param2)s AND group2_id = %(param3)s)) AND game_id=%(param1)s;"""

            cur.execute(
                query,
                {
                    "param1": game_id,
                    "param2": class_,
                    "param3": group_id,
                },
            )
            round_data = cur.fetchall()

            return round_data

    except Exception:
        return False


# Function to get the ids of the groups that played a specific game
def get_group_ids_from_game_id(game_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            query = """SELECT DISTINCT u.class, u.group_id
                    FROM user_ u
                    JOIN plays p ON u.user_id = p.user_id
                    WHERE p.game_id = %(param1)s
                    ORDER BY u.class, u.group_id;"""

            cur.execute(query, {"param1": game_id})

            group_ids = cur.fetchall()
            return group_ids

    except Exception as e:
        print(f"Error in get_group_ids_from_game_id: {e}")
        return False


# Function to check user credentials
def authenticate_user(email, password_hash):
    conn = get_connection()
    print(f"Authenticating user with email: {email} and password hash: {password_hash}")
    if not conn:
        print("Failed to get database connection")
        return False
    try:
        print("Connected to the database")
        with conn.cursor() as cur:
            query = "SELECT 1 FROM user_ WHERE email = %(param1)s AND password = %(param2)s;"
            print(f"Executing query: {query} with params: {email}, {password_hash}")
            cur.execute(query, {"param1": email, "param2": password_hash})
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


# Function to validate if an email belongs to an instructor
def is_valid_instructor_email(email):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = "SELECT EXISTS(SELECT 1 FROM user_ WHERE email = %(param1)s);"

            cur.execute(query, {"param1": email})

            # Fetch the result
            exists = cur.fetchone()[0]

            return exists

    except Exception:
        return False


# Function to validate if the user that logged in is an Instructor
def is_instructor(email):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT EXISTS(
                              SELECT 1
                              FROM instructor AS i JOIN user_ AS u
                                ON i.user_id = u.user_id
                              WHERE email = %(param1)s);
            """

            cur.execute(query, {"param1": email})

            # Fetch the result
            is_instr = cur.fetchone()[0]

            return is_instr

    except Exception:
        return False


# Function to see if exists the user
def exists_user(email):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT EXISTS(
                              SELECT 1
                              FROM user_
                              WHERE email = %(param1)s);
            """

            cur.execute(query, {"param1": email})

            # Fetch the result
            exists = cur.fetchone()[0]

            return exists

    except Exception:
        return False


# Function to update the user's password
def update_password(email, new_password):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                UPDATE user_
                SET password = %(param1)s
                WHERE email = %(param2)s;
            """
            cur.execute(query, {"param1": new_password, "param2": email})

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


def _ensure_user_api_key_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_api_key (
            key_id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            key_name VARCHAR(100) NOT NULL,
            encrypted_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_(user_id) ON DELETE CASCADE,
            UNIQUE (user_id, key_name)
        );
        """)


def list_user_api_keys(user_id):
    """List saved API keys (metadata only) for a user."""
    cipher = _get_api_key_cipher()
    if not cipher:
        return []
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            _ensure_user_api_key_table(cur)
            cur.execute(
                """
                SELECT key_id, key_name, updated_at
                FROM user_api_key
                WHERE user_id = %(user_id)s
                ORDER BY updated_at DESC;
                """,
                {"user_id": user_id},
            )
            rows = cur.fetchall()
            return [{"key_id": row[0], "key_name": row[1], "updated_at": row[2]} for row in rows]
    except Exception as e:
        print(f"Error in list_user_api_keys: {e}")
        return []


def add_user_api_key(user_id, key_name, api_key):
    """Add or update a named API key for a user."""
    cipher = _get_api_key_cipher()
    if not cipher:
        return False
    conn = get_connection()
    if not conn:
        return False
    try:
        encrypted_key = cipher.encrypt(api_key.encode()).decode()
        with conn.cursor() as cur:
            _ensure_user_api_key_table(cur)
            cur.execute(
                """
                INSERT INTO user_api_key (user_id, key_name, encrypted_key, created_at, updated_at)
                VALUES (%(user_id)s, %(key_name)s, %(encrypted_key)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, key_name)
                DO UPDATE SET encrypted_key = EXCLUDED.encrypted_key,
                              updated_at = CURRENT_TIMESTAMP;
                """,
                {"user_id": user_id, "key_name": key_name, "encrypted_key": encrypted_key},
            )
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error in add_user_api_key: {e}")
        return False


def update_user_api_key_name(user_id, key_id, new_name):
    """Rename a saved API key."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            _ensure_user_api_key_table(cur)
            cur.execute(
                """
                UPDATE user_api_key
                SET key_name = %(key_name)s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %(user_id)s AND key_id = %(key_id)s;
                """,
                {"user_id": user_id, "key_id": key_id, "key_name": new_name},
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error in update_user_api_key_name: {e}")
        return False


def update_user_api_key(user_id, key_id, new_name, api_key):
    """Update the name and value of a saved API key."""
    cipher = _get_api_key_cipher()
    if not cipher:
        return False
    conn = get_connection()
    if not conn:
        return False
    try:
        encrypted_key = cipher.encrypt(api_key.encode()).decode()
        with conn.cursor() as cur:
            _ensure_user_api_key_table(cur)
            cur.execute(
                """
                UPDATE user_api_key
                SET key_name = %(key_name)s,
                    encrypted_key = %(encrypted_key)s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %(user_id)s AND key_id = %(key_id)s;
                """,
                {
                    "user_id": user_id,
                    "key_id": key_id,
                    "key_name": new_name,
                    "encrypted_key": encrypted_key,
                },
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error in update_user_api_key: {e}")
        return False


def delete_user_api_key(user_id, key_id):
    """Delete a saved API key."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            _ensure_user_api_key_table(cur)
            cur.execute(
                """
                DELETE FROM user_api_key
                WHERE user_id = %(user_id)s AND key_id = %(key_id)s;
                """,
                {"user_id": user_id, "key_id": key_id},
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error in delete_user_api_key: {e}")
        return False


def get_user_api_key(user_id, key_id):
    """Retrieve and decrypt a user's API key."""
    cipher = _get_api_key_cipher()
    if not cipher:
        return None
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            _ensure_user_api_key_table(cur)
            cur.execute(
                """
                SELECT encrypted_key
                FROM user_api_key
                WHERE user_id = %(user_id)s AND key_id = %(key_id)s;
                """,
                {"user_id": user_id, "key_id": key_id},
            )
            row = cur.fetchone()
            if not row:
                return None
            try:
                return cipher.decrypt(row[0].encode()).decode()
            except InvalidToken:
                print("Failed to decrypt user API key. Invalid encryption key.")
                return None
    except Exception as e:
        print(f"Error in get_user_api_key: {e}")
        return None


# Function to get user_id by email
def get_user_id_by_email(email):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = "SELECT user_id FROM user_ WHERE email = %(param1)s;"

            cur.execute(query, {"param1": email})

            # Fetch the result
            user_id = cur.fetchone()[0]

            return user_id

    except Exception:
        return False


# Function to update the number of rounds of a game
def update_num_rounds_game(num_rounds, game_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query1 = """
                UPDATE game
                SET number_of_rounds = %(param1)s
                WHERE game_id = %(param2)s;
            """

            cur.execute(query1, {"param1": num_rounds, "param2": game_id})

            query2 = """
                SELECT *
                FROM game
                ORDER BY game_id;
            """

            cur.execute(query2)

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


# Function to extract from the 'round' table all the rows of a specific game where the chats were not successful
def get_error_matchups(game_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query1 = """
                SELECT round_number, group1_class, group1_id, group2_class, group2_id, score_team1_role1, score_team2_role2, score_team1_role2, score_team2_role1
                FROM round
                WHERE game_id = %(param1)s AND (score_team1_role1 IS NULL OR score_team1_role2 IS NULL);
            """

            cur.execute(query1, {"param1": game_id})
            error_matchups = cur.fetchall()

            error_matchups_final = []
            for i in error_matchups:
                aux_1 = [i[0]]
                aux_2 = [list(i[1:3])]
                aux_3 = [list(i[3:5])]
                aux_4 = [1] if i[5] is None else [0]
                aux_5 = [1] if i[7] is None else [0]
                error_matchups_final.append(aux_1 + aux_2 + aux_3 + aux_4 + aux_5)

            return error_matchups_final

    except Exception:
        return False


# Function to update the scores of a specific row in the 'round' table
def update_round_data(
    game_id,
    round_number,
    group1_class,
    group1_id,
    group2_class,
    group2_id,
    score_team1,
    score_team2,
    team1_role_index,
    team2_role_index,
):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            if (team1_role_index, team2_role_index) == (1, 2):

                query1 = """
                    UPDATE round
                    SET score_team1_role1 = %(param7)s, score_team2_role2 = %(param8)s
                    WHERE game_id = %(param1)s AND round_number = %(param2)s AND group1_class = %(param3)s AND group1_id = %(param4)s AND group2_class = %(param5)s AND group2_id = %(param6)s;
                """

                cur.execute(
                    query1,
                    {
                        "param1": game_id,
                        "param2": round_number,
                        "param3": group1_class,
                        "param4": group1_id,
                        "param5": group2_class,
                        "param6": group2_id,
                        "param7": score_team1,
                        "param8": score_team2,
                    },
                )

                conn.commit()
                return True

            if (team1_role_index, team2_role_index) == (2, 1):

                query1 = """
                    UPDATE round
                    SET score_team1_role2 = %(param7)s, score_team2_role1 = %(param8)s
                    WHERE game_id = %(param1)s AND round_number = %(param2)s AND group1_class = %(param3)s AND group1_id = %(param4)s AND group2_class = %(param5)s AND group2_id = %(param6)s;
                """

                cur.execute(
                    query1,
                    {
                        "param1": game_id,
                        "param2": round_number,
                        "param3": group1_class,
                        "param4": group1_id,
                        "param5": group2_class,
                        "param6": group2_id,
                        "param7": score_team1,
                        "param8": score_team2,
                    },
                )

                conn.commit()
                return True

            return False

    except Exception:
        conn.rollback()
        return False


# Function to delete all the rows in the 'round' table that belong to a specific game_id
def delete_from_round(game_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query1 = """
                DELETE FROM round
                WHERE game_id = %(param1)s;
            """

            cur.execute(query1, {"param1": game_id})

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False


# The next four functions enable the Instructor to view the Play section exactly as it appears to a student in a specific group
# Function to get all the different academic years of students
def get_academic_years_of_students():
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT DISTINCT u.academic_year
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL
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
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT DISTINCT u.class
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL AND u.academic_year = %(param1)s
                ORDER BY u.class ASC;
            """

            cur.execute(query, {"param1": academic_year})
            classes_of_students = cur.fetchall()

            classes_of_students_final = []
            for i in classes_of_students:
                classes_of_students_final.append(i[0])

            return classes_of_students_final

    except Exception:
        return False


# Function to get all the different groups of students from a specfic class of a specific academic year
def get_groups_of_students(academic_year, class_):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT DISTINCT u.group_id
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL AND u.academic_year = %(param1)s AND u.class = %(param2)s
                ORDER BY u.group_id ASC;
            """

            cur.execute(query, {"param1": academic_year, "param2": class_})
            groups_of_students = cur.fetchall()

            groups_of_students_final = []
            for i in groups_of_students:
                groups_of_students_final.append(i[0])

            return groups_of_students_final

    except Exception:
        return False


# Function to get the user_id of a student from a specific group of a specific class of a specific academic year
def get_user_id_of_student(academic_year, class_, group_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            query = """
                SELECT u.user_id
                FROM user_ AS u LEFT JOIN instructor AS i
                    ON u.user_id = i.user_id
                WHERE i.user_id IS NULL AND u.academic_year = %(param1)s AND u.class = %(param2)s AND u.group_id = %(param3)s
                ORDER BY u.group_id ASC;
            """

            cur.execute(query, {"param1": academic_year, "param2": class_, "param3": group_id})
            user_id = cur.fetchone()[0]
            return user_id

    except Exception:
        return False


# Function to get and compute leaderboard scores for a given academic year
def fetch_and_compute_scores_for_year(selected_year, student=False):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            # SQL Query to compute the leaderboard
            query = """
                WITH computed_scores_only_year_roles AS (
                    SELECT
                        r.game_id,
                        r.round_number,
                        r.group1_class AS team_class,
                        r.group1_id AS team_id,
                        ((CASE WHEN r.score_team1_role1 = -1 THEN 0 ELSE r.score_team1_role1 END +
                          CASE WHEN r.score_team1_role2 = -1 THEN 0 ELSE r.score_team1_role2 END) / 2) AS score_team,
                        CASE WHEN r.score_team1_role1 = -1 THEN 0 ELSE r.score_team1_role1 END AS score_role1,
                        CASE WHEN r.score_team1_role2 = -1 THEN 0 ELSE r.score_team1_role2 END AS score_role2
                    FROM round AS r
                    JOIN game AS g ON r.game_id = g.game_id
                    WHERE g.game_academic_year = %(param1)s
                      AND g.available IN %(param2)s

                    UNION ALL

                    SELECT
                        r.game_id,
                        r.round_number,
                        r.group2_class AS team_class,
                        r.group2_id AS team_id,
                        ((CASE WHEN r.score_team2_role1 = -1 THEN 0 ELSE r.score_team2_role1 END +
                          CASE WHEN r.score_team2_role2 = -1 THEN 0 ELSE r.score_team2_role2 END) / 2) AS score_team,
                        CASE WHEN r.score_team2_role1 = -1 THEN 0 ELSE r.score_team2_role1 END AS score_role1,
                        CASE WHEN r.score_team2_role2 = -1 THEN 0 ELSE r.score_team2_role2 END AS score_role2
                    FROM round AS r
                    JOIN game AS g ON r.game_id = g.game_id
                    WHERE g.game_academic_year = %(param1)s
                      AND g.available IN %(param2)s
                ),
                leaderboard_only_year AS (
                    SELECT
                        team_class,
                        team_id,
                        AVG(score_team) * 100 AS average_score
                    FROM computed_scores_only_year_roles
                    GROUP BY team_class, team_id
                ),
                team_game_rounds AS (
                    SELECT
                        r.game_id,
                        r.round_number,
                        r.group1_class AS team_class,
                        r.group1_id AS team_id
                    FROM round AS r
                    JOIN game AS g ON r.game_id = g.game_id
                    WHERE g.game_academic_year = %(param1)s AND g.available IN %(param2)s

                    UNION ALL

                    SELECT
                        r.game_id,
                        r.round_number,
                        r.group2_class AS team_class,
                        r.group2_id AS team_id
                    FROM round AS r
                    JOIN game AS g ON r.game_id = g.game_id
                    WHERE g.game_academic_year = %(param1)s AND g.available IN %(param2)s
                ),
                rounds_per_game AS (
                    SELECT
                        team_class,
                        team_id,
                        game_id,
                        COUNT(DISTINCT round_number) AS rounds_in_game
                    FROM team_game_rounds
                    GROUP BY team_class, team_id, game_id
                ),
                games_summary AS (
                    SELECT
                        team_class,
                        team_id,
                        COUNT(DISTINCT game_id) AS total_games,
                        AVG(rounds_in_game) AS avg_rounds_per_game
                    FROM rounds_per_game
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
                    gs.total_games,
                    gs.avg_rounds_per_game,
                    lr.position_name_roles_1,
                    lr.score_name_roles_1,
                    lr.position_name_roles_2,
                    lr.score_name_roles_2
                FROM leaderboard_only_year AS ly
                JOIN games_summary AS gs
                ON ly.team_class = gs.team_class AND ly.team_id = gs.team_id
                JOIN leaderboard_roles AS lr
                ON ly.team_class = lr.team_class AND ly.team_id = lr.team_id
                ORDER BY ly.average_score DESC;
            """

            # Execute the query with the selected year
            cur.execute(query, {"param1": selected_year, "param2": (0, 1) if not student else (1,)})

            # Fetch results
            leaderboard = cur.fetchall()

            # Format the results into a list of dictionaries
            return [
                {
                    "team_class": row[0],
                    "team_id": row[1],
                    "average_score": row[2],
                    "total_games": row[3],
                    "avg_rounds_per_game": row[4],
                    "position_name_roles_1": row[5],
                    "score_name_roles_1": row[6],
                    "position_name_roles_2": row[7],
                    "score_name_roles_2": row[8],
                }
                for row in leaderboard
            ]

    except Exception:
        return False


# Function to get and compute leaderboard scores for a given game_id
def fetch_and_compute_scores_for_year_game(game_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:

            # SQL Query to compute the leaderboard
            query = """
                WITH computed_scores_year_game_roles AS (
                    SELECT
                        r.game_id,
                        r.round_number,
                        r.group1_class AS team_class,
                        r.group1_id AS team_id,
                        ((CASE WHEN r.score_team1_role1 = -1 THEN 0 ELSE r.score_team1_role1 END +
                          CASE WHEN r.score_team1_role2 = -1 THEN 0 ELSE r.score_team1_role2 END) / 2) AS score_team,
                        CASE WHEN r.score_team1_role1 = -1 THEN 0 ELSE r.score_team1_role1 END AS score_role1,
                        CASE WHEN r.score_team1_role2 = -1 THEN 0 ELSE r.score_team1_role2 END AS score_role2
                    FROM round AS r
                    WHERE r.game_id = %(param1)s

                    UNION ALL

                    SELECT
                        r.game_id,
                        r.round_number,
                        r.group2_class AS team_class,
                        r.group2_id AS team_id,
                        ((CASE WHEN r.score_team2_role1 = -1 THEN 0 ELSE r.score_team2_role1 END +
                          CASE WHEN r.score_team2_role2 = -1 THEN 0 ELSE r.score_team2_role2 END) / 2) AS score_team,
                        CASE WHEN r.score_team2_role1 = -1 THEN 0 ELSE r.score_team2_role1 END AS score_role1,
                        CASE WHEN r.score_team2_role2 = -1 THEN 0 ELSE r.score_team2_role2 END AS score_role2
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
                rounds_per_game AS (
                    SELECT
                        team_class,
                        team_id,
                        COUNT(DISTINCT round_number) AS rounds_in_game
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
                    1 AS total_games,
                    rpg.rounds_in_game AS avg_rounds_per_game,
                    lr.position_name_roles_1,
                    lr.score_name_roles_1,
                    lr.position_name_roles_2,
                    lr.score_name_roles_2
                FROM leaderboard_year_game AS lyg
                JOIN rounds_per_game AS rpg
                ON lyg.team_class = rpg.team_class AND lyg.team_id = rpg.team_id
                JOIN leaderboard_roles AS lr
                ON lyg.team_class = lr.team_class AND lyg.team_id = lr.team_id
                ORDER BY lyg.average_score DESC;
            """

            # Execute the query with the selected year
            cur.execute(query, {"param1": game_id})

            # Fetch results
            leaderboard = cur.fetchall()

            # Format the results into a list of dictionaries
            return [
                {
                    "team_class": row[0],
                    "team_id": row[1],
                    "average_score": row[2],
                    "total_games": row[3],
                    "avg_rounds_per_game": row[4],
                    "position_name_roles_1": row[5],
                    "score_name_roles_1": row[6],
                    "position_name_roles_2": row[7],
                    "score_name_roles_2": row[8],
                }
                for row in leaderboard
            ]

    except Exception:
        return False


# Function to store group values in the database
def store_group_values(game_id, class_, group_id, minimizer_value, maximizer_value):
    conn = get_connection()
    if not conn:
        return False
    try:
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

            cur.execute(
                query,
                {
                    "param1": game_id,
                    "param2": class_,
                    "param3": group_id,
                    "param4": minimizer_value,
                    "param5": maximizer_value,
                },
            )

            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error in store_group_values: {e}")
        return False


# Function to store game parameters (bounds)
def store_game_parameters(game_id, min_minimizer, max_minimizer, min_maximizer, max_maximizer):
    conn = get_connection()
    if not conn:
        return False
    try:
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

            cur.execute(query, {"param1": game_id, "param2": min_minimizer, "param3": min_maximizer})

            # Store max values in another row using 'params' as class and 1 as group_id
            query = """
                INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
                VALUES (%(param1)s, 'params', 1, %(param2)s, %(param3)s)
                ON CONFLICT (game_id, class, group_id)
                DO UPDATE SET minimizer_value = %(param2)s, maximizer_value = %(param3)s;
            """

            cur.execute(query, {"param1": game_id, "param2": max_minimizer, "param3": max_maximizer})

            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error in store_game_parameters: {e}")
        return False


# Function to get group values from database
def get_group_values(game_id, class_, group_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            query = """
                SELECT minimizer_value, maximizer_value
                FROM group_values
                WHERE game_id = %(param1)s AND class = %(param2)s AND group_id = %(param3)s;
            """

            cur.execute(query, {"param1": game_id, "param2": class_, "param3": group_id})

            result = cur.fetchone()
            if result:
                return {"minimizer_value": result[0], "maximizer_value": result[1]}
            return None
    except Exception:
        return None


# Function to get game parameters (bounds)
def get_game_parameters(game_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            # Retrieve the two rows stored for parameters, ordered by group_id (0 then 1)
            query = """
                SELECT minimizer_value, maximizer_value
                FROM group_values
                WHERE game_id = %(param1)s AND class = 'params'
                ORDER BY group_id;
            """

            cur.execute(query, {"param1": game_id})

            results = cur.fetchall()
            # Expecting two rows: one for min values (group_id=0), one for max values (group_id=1)
            if len(results) == 2:
                return {
                    "min_minimizer": results[0][0],  # Min minimizer from row 0
                    "max_minimizer": results[1][0],  # Max minimizer from row 1
                    "min_maximizer": results[0][1],  # Min maximizer from row 0
                    "max_maximizer": results[1][1],  # Max maximizer from row 1
                }
            return None
    except Exception as e:
        print(f"Error in get_game_parameters: {e}")
        return None


# Function to get all group values for a game (excluding parameters)
def get_all_group_values(game_id):
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            query = """
                SELECT class, group_id, minimizer_value, maximizer_value
                FROM group_values
                WHERE game_id = %(param1)s AND class != 'params'
                ORDER BY class, group_id;
            """

            cur.execute(query, {"param1": game_id})

            results = cur.fetchall()
            values = []
            for row in results:
                values.append(
                    {"class": row[0], "group_id": row[1], "minimizer_value": row[2], "maximizer_value": row[3]}
                )
            return values
    except Exception as e:
        print(f"Error in get_all_group_values: {e}")
        return []


# Function to insert or update a student prompt
def insert_student_prompt(game_id, class_, group_id, prompt, submitted_by=None):
    """Insert or update a student prompt (upsert).

    Args:
        game_id: The game ID
        class_: The class identifier
        group_id: The group ID
        prompt: The prompt text (combined format with #_;:) delimiter)
        submitted_by: Optional user_id of the submitter

    Returns:
        True on success, False on failure
    """
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO student_prompt (game_id, class, group_id, prompt, submitted_by)
                VALUES (%(game_id)s, %(class)s, %(group_id)s, %(prompt)s, %(submitted_by)s)
                ON CONFLICT (game_id, class, group_id)
                DO UPDATE SET prompt = EXCLUDED.prompt,
                              submitted_by = EXCLUDED.submitted_by,
                              updated_at = CURRENT_TIMESTAMP;
            """
            cur.execute(
                query,
                {
                    "game_id": game_id,
                    "class": class_,
                    "group_id": group_id,
                    "prompt": prompt,
                    "submitted_by": submitted_by,
                },
            )
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error in insert_student_prompt: {e}")
        return False


# Function to retrieve a student prompt
def get_student_prompt(game_id, class_, group_id):
    """Retrieve a student prompt from the database.

    Args:
        game_id: The game ID
        class_: The class identifier
        group_id: The group ID

    Returns:
        The prompt text or None if not found
    """
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            query = """
                SELECT prompt
                FROM student_prompt
                WHERE game_id = %(game_id)s AND class = %(class)s AND group_id = %(group_id)s;
            """
            cur.execute(query, {"game_id": game_id, "class": class_, "group_id": group_id})
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        return None


# Function to retrieve a student prompt and last update timestamp
def get_student_prompt_with_timestamp(game_id, class_, group_id):
    """Retrieve a student prompt and last update timestamp from the database."""
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            query = """
                SELECT prompt, updated_at
                FROM student_prompt
                WHERE game_id = %(game_id)s AND class = %(class)s AND group_id = %(group_id)s;
            """
            cur.execute(query, {"game_id": game_id, "class": class_, "group_id": group_id})
            row = cur.fetchone()
            if row:
                return {"prompt": row[0], "updated_at": row[1]}
            return None
    except Exception:
        return None
