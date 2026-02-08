"""
Integration tests for CSV processing.

Tests the full flow of CSV import including database interactions (mocked).
"""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock

import pytest

# Add streamlit directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit")))


@pytest.fixture
def csv_file():
    """Factory fixture to create mock CSV file objects."""

    def _create_csv(content):
        file = StringIO(content)
        file.name = "test.csv"
        return file

    return _create_csv


@pytest.fixture
def student_utils_with_mocks():
    """Import student_utils with all dependencies mocked."""
    # Create fresh mock database handler with insert function
    mock_db = MagicMock()
    mock_db.insert_student_data = MagicMock(return_value=True)
    sys.modules["modules.database_handler"] = mock_db

    # Force reimport to pick up fresh mock
    if "modules.student_utils" in sys.modules:
        del sys.modules["modules.student_utils"]

    from modules import student_utils

    # Ensure the module uses our mock
    student_utils.insert_student_data = mock_db.insert_student_data

    return student_utils, mock_db


class TestProcessStudentCSV:
    """Integration tests for process_student_csv function."""

    @pytest.mark.integration
    def test_successful_csv_processing(self, student_utils_with_mocks, csv_file):
        """Test successful processing of a valid CSV file."""
        student_utils, mock_db = student_utils_with_mocks

        content = "user_id;email;group_id;academic_year;class\n"
        content += "student1;student1@test.com;1;2024-2025;ClassA\n"
        content += "student2;student2@test.com;1;2024-2025;ClassA\n"

        file = csv_file(content)
        success, message = student_utils.process_student_csv(file)

        assert success is True
        assert "successfully" in message.lower() or "added" in message.lower()
        assert mock_db.insert_student_data.call_count == 2

    @pytest.mark.integration
    def test_missing_required_columns(self, student_utils_with_mocks, csv_file):
        """Test error handling when required columns are missing."""
        student_utils, mock_db = student_utils_with_mocks

        content = "user_id;email;group_id\n"  # Missing academic_year and class
        content += "student1;student1@test.com;1\n"

        file = csv_file(content)
        success, message = student_utils.process_student_csv(file)

        assert success is False
        assert "missing" in message.lower()
        assert mock_db.insert_student_data.call_count == 0

    @pytest.mark.integration
    def test_partial_insert_failure(self, student_utils_with_mocks, csv_file):
        """Test handling when some inserts fail (e.g., duplicates)."""
        student_utils, mock_db = student_utils_with_mocks

        # First call succeeds, second fails
        mock_db.insert_student_data.side_effect = [True, False, True]

        content = "user_id;email;group_id;academic_year;class\n"
        content += "student1;student1@test.com;1;2024-2025;ClassA\n"
        content += "student2;student2@test.com;1;2024-2025;ClassA\n"
        content += "student3;student3@test.com;2;2024-2025;ClassA\n"

        file = csv_file(content)
        success, message = student_utils.process_student_csv(file)

        assert success is True
        assert "2" in message  # 2 successful
        assert "1" in message  # 1 failed

    @pytest.mark.integration
    def test_all_rows_fail_returns_error(self, student_utils_with_mocks, csv_file):
        """If nothing is inserted, return an error outcome."""
        student_utils, mock_db = student_utils_with_mocks

        mock_db.insert_student_data.side_effect = [False, False]

        content = "user_id;email;group_id;academic_year;class\n"
        content += "student1;student1@test.com;1;2024-2025;ClassA\n"
        content += "student2;student2@test.com;1;2024-2025;ClassA\n"

        file = csv_file(content)
        success, message = student_utils.process_student_csv(file)

        assert success is False
        assert "no students were added" in message.lower()

    @pytest.mark.integration
    def test_comma_separated_fallback(self, student_utils_with_mocks, csv_file):
        """Test that comma-separated CSV works when semicolon fails."""
        student_utils, mock_db = student_utils_with_mocks

        content = "user_id,email,group_id,academic_year,class\n"
        content += "student1,student1@test.com,1,2024-2025,ClassA\n"

        file = csv_file(content)
        success, message = student_utils.process_student_csv(file)

        assert success is True
        assert mock_db.insert_student_data.call_count == 1

    @pytest.mark.integration
    def test_normalized_column_headers(self, student_utils_with_mocks, csv_file):
        """Test that various column name formats are normalized."""
        student_utils, mock_db = student_utils_with_mocks

        # Using alternative column names that match the normalization mapping
        # 'id' -> user_id, 'e-mail' -> email, 'group' -> group_id, 'year' -> academic_year, 'class_name' -> class
        content = "id;e-mail;group;year;class_name\n"
        content += "student1;student1@test.com;1;2024-2025;ClassA\n"

        file = csv_file(content)
        success, message = student_utils.process_student_csv(file)

        assert success is True
        assert mock_db.insert_student_data.call_count == 1

    @pytest.mark.integration
    def test_empty_csv_file(self, student_utils_with_mocks, csv_file):
        """Test handling of empty CSV (headers only)."""
        student_utils, mock_db = student_utils_with_mocks

        content = "user_id;email;group_id;academic_year;class\n"

        file = csv_file(content)
        success, message = student_utils.process_student_csv(file)

        assert success is True
        assert mock_db.insert_student_data.call_count == 0

    @pytest.mark.integration
    def test_insert_data_format(self, student_utils_with_mocks, csv_file):
        """Test that insert_student_data is called with correct arguments."""
        student_utils, mock_db = student_utils_with_mocks

        content = "user_id;email;group_id;academic_year;class\n"
        content += "test123;test@nova.edu;5;2024-2025;SectionB\n"

        file = csv_file(content)
        student_utils.process_student_csv(file)

        # Verify the call arguments
        mock_db.insert_student_data.assert_called_once()
        call_args = mock_db.insert_student_data.call_args[0]

        assert call_args[0] == "test123"  # user_id
        assert call_args[1] == "test@nova.edu"  # email
        assert call_args[2] == "Not defined"  # password placeholder
        assert call_args[3] == 5  # group_id
        assert call_args[4] == "2024-2025"  # academic_year
        assert call_args[5] == "SectionB"  # class
