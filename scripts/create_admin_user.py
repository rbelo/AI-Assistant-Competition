#!/usr/bin/env python3
import hashlib
import os
import sys
from pathlib import Path

import psycopg2

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib


DEFAULT_EMAIL = "admin@rodrigobelo.com"
DEFAULT_PASSWORD = "admin123"
DEFAULT_USER_ID = "admin"
DEFAULT_GROUP_ID = 0
DEFAULT_ACADEMIC_YEAR = 0
DEFAULT_CLASS = "_"
DEFAULT_PERMISSION_LEVEL = "admin"


def load_database_url():
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    secrets_path = Path(__file__).resolve().parents[1] / "streamlit" / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return None
    with secrets_path.open("rb") as handle:
        data = tomllib.load(handle)
    return data.get("database", {}).get("url")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def ensure_admin_user(conn, email, password, user_id):
    hashed_password = hash_password(password)
    with conn.cursor() as cur:
        cur.execute("SELECT user_id FROM user_ WHERE email = %(email)s;", {"email": email})
        row = cur.fetchone()

        if row:
            existing_user_id = row[0]
            cur.execute(
                "UPDATE user_ SET password = %(password)s WHERE email = %(email)s;",
                {"password": hashed_password, "email": email},
            )
            user_id = existing_user_id
        else:
            cur.execute(
                """
                INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
                VALUES (%(user_id)s, %(email)s, %(password)s, %(group_id)s, %(academic_year)s, %(class)s);
                """,
                {
                    "user_id": user_id,
                    "email": email,
                    "password": hashed_password,
                    "group_id": DEFAULT_GROUP_ID,
                    "academic_year": DEFAULT_ACADEMIC_YEAR,
                    "class": DEFAULT_CLASS,
                },
            )

        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM instructor WHERE user_id = %(user_id)s);",
            {"user_id": user_id},
        )
        if not cur.fetchone()[0]:
            cur.execute(
                "INSERT INTO instructor (user_id, permission_level) VALUES (%(user_id)s, %(permission_level)s);",
                {"user_id": user_id, "permission_level": DEFAULT_PERMISSION_LEVEL},
            )


def main():
    db_url = load_database_url()
    if not db_url:
        print("Database URL not found. Set DATABASE_URL or fill streamlit/.streamlit/secrets.toml.")
        return 1

    email = os.getenv("ADMIN_EMAIL", DEFAULT_EMAIL)
    password = os.getenv("ADMIN_PASSWORD", DEFAULT_PASSWORD)
    user_id = os.getenv("ADMIN_USER_ID", DEFAULT_USER_ID)

    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        print(f"Failed to connect to database: {exc}")
        return 1

    try:
        ensure_admin_user(conn, email, password, user_id)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"Failed to create/update admin user: {exc}")
        return 1
    finally:
        conn.close()

    print(f"Admin user ready: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
