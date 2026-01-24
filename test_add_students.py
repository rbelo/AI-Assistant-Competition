import sys
import os
import csv
import psycopg2
from unittest.mock import MagicMock

# Mock streamlit before importing module
sys.modules["streamlit"] = MagicMock()
import streamlit as st

# Set secrets
st.secrets = {
    "database": {
        "url": "postgresql://postgres:pVUCvwMJibuSdsjsCZKgvpinhpMvmCbu@mainline.proxy.rlwy.net:40688/railway"
    }
}

# Add streamlit directory to path
sys.path.append(os.path.join(os.getcwd(), "streamlit"))

from modules.database_handler import insert_student_data

def test_add_students():
    csv_file = "/Users/rbelo/.gemini/antigravity/brain/9beff2ff-3ffa-4680-8211-bb6fee217df1/test_students.csv"
    
    print(f"Reading students from {csv_file}...")
    
    students_to_add = []
    with open(csv_file, 'r') as f:
        reader = csv.reader(f, delimiter=';')
        for row in reader:
            if len(row) >= 5:
                students_to_add.append(row)
    
    print(f"Found {len(students_to_add)} students to add.")
    
    for student in students_to_add:
        user_id, email, group_id, academic_year, class_ = student
        # Generate a temp password (logic from 2_Control_Panel.py usually does this, we'll just use 'temp123')
        temp_password = "temp123" 
        
        print(f"Adding student: {user_id}")
        success = insert_student_data(user_id, email, temp_password, group_id, academic_year, class_)
        
        if success:
            print(f"Successfully added {user_id}")
        else:
            print(f"Failed to add {user_id}")

    # Verify in DB
    print("\nVerifying in database...")
    conn_str = st.secrets["database"]["url"]
    with psycopg2.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, email, class FROM user_ WHERE user_id IN ('test_user_1', 'test_user_2')")
            rows = cur.fetchall()
            print(f"Found {len(rows)} students in DB:")
            for row in rows:
                print(row)

if __name__ == "__main__":
    test_add_students()
