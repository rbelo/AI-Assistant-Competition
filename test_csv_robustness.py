import sys
import os
import pandas as pd
from io import StringIO
from unittest.mock import MagicMock, patch

# Mock streamlit and database_handler
sys.modules["streamlit"] = MagicMock()
import streamlit as st

# Add streamlit directory to path
sys.path.append(os.path.join(os.getcwd(), "streamlit"))

# Mock insert_student_data to avoid DB calls
with patch("modules.student_utils.insert_student_data") as mock_insert:
    mock_insert.return_value = True
    from modules.student_utils import process_student_csv

    def test_csv_robustness():
        print("Testing CSV Robustness...\n")

        # Case 1: Standard format (semicolon)
        print("1. Testing Standard Format (semicolon)...")
        csv_content = "userID;email;groupID;academic year;class\nu1;e1;g1;2024;A"
        success, msg = process_student_csv(StringIO(csv_content))
        print(f"Result: {success}, Message: {msg}")
        assert success == True
        print("PASS\n")

        # Case 2: Alternative headers (comma)
        print("2. Testing Alternative Headers (comma)...")
        csv_content = "user_id,email,group_id,year,class_name\nu2,e2,g1,2024,B"
        success, msg = process_student_csv(StringIO(csv_content))
        print(f"Result: {success}, Message: {msg}")
        assert success == True
        print("PASS\n")

        # Case 3: Mixed case and order
        print("3. Testing Mixed Case and Order...")
        csv_content = "Class,User ID,Group,Email,AcademicYear\nC,u3,g2,e3,2025"
        success, msg = process_student_csv(StringIO(csv_content))
        print(f"Result: {success}, Message: {msg}")
        assert success == True
        print("PASS\n")

        # Case 4: Missing column
        print("4. Testing Missing Column...")
        csv_content = "user_id,email,group_id,year\nu4,e4,g3,2024" # Missing class
        success, msg = process_student_csv(StringIO(csv_content))
        print(f"Result: {success}, Message: {msg}")
        assert success == False
        assert "Missing required columns: class" in msg
        print("PASS\n")

        print("All robustness tests passed!")

if __name__ == "__main__":
    test_csv_robustness()
