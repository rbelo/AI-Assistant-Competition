"""
Unit tests for student_utils module.

Tests CSV processing and column normalization logic.
"""

import pytest
import pandas as pd
from io import StringIO
import sys
import os
from unittest.mock import MagicMock

# Add streamlit directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit")))


@pytest.fixture
def normalize_column_names():
    """Import normalize_column_names function with mocked dependencies."""
    # Mock database handler before importing
    mock_db = MagicMock()
    mock_db.insert_student_data = MagicMock(return_value=True)
    sys.modules["modules.database_handler"] = mock_db

    from modules.student_utils import normalize_column_names

    return normalize_column_names


class TestNormalizeColumnNames:
    """Tests for the normalize_column_names function."""

    @pytest.mark.unit
    def test_standard_column_names(self, normalize_column_names):
        """Test that standard column names are preserved."""
        df = pd.DataFrame(columns=["user_id", "email", "group_id", "academic_year", "class"])
        result = normalize_column_names(df)
        assert list(result.columns) == ["user_id", "email", "group_id", "academic_year", "class"]

    @pytest.mark.unit
    def test_uppercase_variations(self, normalize_column_names):
        """Test that uppercase variations are normalized."""
        df = pd.DataFrame(columns=["UserID", "Email", "GroupID", "Academic_Year", "Class"])
        result = normalize_column_names(df)
        assert "user_id" in result.columns
        assert "email" in result.columns
        assert "group_id" in result.columns
        assert "academic_year" in result.columns
        assert "class" in result.columns

    @pytest.mark.unit
    def test_alternative_column_names(self, normalize_column_names):
        """Test that alternative column names are normalized."""
        df = pd.DataFrame(columns=["id", "e-mail", "group", "year", "class_name"])
        result = normalize_column_names(df)
        assert "user_id" in result.columns
        assert "email" in result.columns
        assert "group_id" in result.columns
        assert "academic_year" in result.columns
        assert "class" in result.columns

    @pytest.mark.unit
    def test_mixed_case_with_spaces(self, normalize_column_names):
        """Test that mixed case with spaces are handled."""
        df = pd.DataFrame(columns=["User ID", "E-Mail", "Group ID", "Academic Year", "Class"])
        result = normalize_column_names(df)
        assert "user_id" in result.columns
        assert "email" in result.columns
        assert "group_id" in result.columns
        assert "academic_year" in result.columns
        assert "class" in result.columns

    @pytest.mark.unit
    def test_preserves_unknown_columns(self, normalize_column_names):
        """Test that unknown column names are preserved as-is."""
        df = pd.DataFrame(columns=["user_id", "email", "extra_column", "another_column"])
        result = normalize_column_names(df)
        assert "extra_column" in result.columns
        assert "another_column" in result.columns

    @pytest.mark.unit
    def test_whitespace_trimming(self, normalize_column_names):
        """Test that leading/trailing whitespace is trimmed."""
        df = pd.DataFrame(columns=["  user_id  ", "email ", " group_id"])
        result = normalize_column_names(df)
        assert "user_id" in result.columns
        assert "email" in result.columns
        assert "group_id" in result.columns


class TestCSVParsing:
    """Tests for CSV parsing with different formats."""

    @pytest.mark.unit
    def test_semicolon_delimiter(self, csv_file):
        """Test parsing CSV with semicolon delimiter."""
        content = "user_id;email;group_id;academic_year;class\n"
        content += "test1;test1@test.com;1;2024-2025;ClassA\n"
        file = csv_file(content)
        df = pd.read_csv(file, sep=";")
        assert len(df) == 1
        assert df.iloc[0]["user_id"] == "test1"

    @pytest.mark.unit
    def test_comma_delimiter(self, csv_file):
        """Test parsing CSV with comma delimiter."""
        content = "user_id,email,group_id,academic_year,class\n"
        content += "test1,test1@test.com,1,2024-2025,ClassA\n"
        file = csv_file(content)
        df = pd.read_csv(file, sep=",")
        assert len(df) == 1
        assert df.iloc[0]["user_id"] == "test1"

    @pytest.mark.unit
    def test_academic_year_as_string(self, csv_file):
        """Test that academic_year is parsed as string, not date."""
        content = "user_id;email;group_id;academic_year;class\n"
        content += "test1;test1@test.com;1;2024-2025;ClassA\n"
        file = csv_file(content)
        df = pd.read_csv(file, sep=";", dtype={"academic_year": str})
        assert df.iloc[0]["academic_year"] == "2024-2025"
        assert isinstance(df.iloc[0]["academic_year"], str)

    @pytest.mark.unit
    def test_empty_csv(self, csv_file):
        """Test handling of empty CSV (headers only)."""
        content = "user_id;email;group_id;academic_year;class\n"
        file = csv_file(content)
        df = pd.read_csv(file, sep=";")
        assert len(df) == 0
        assert list(df.columns) == ["user_id", "email", "group_id", "academic_year", "class"]

    @pytest.mark.unit
    def test_multiple_rows(self, csv_file):
        """Test parsing CSV with multiple rows."""
        content = "user_id;email;group_id;academic_year;class\n"
        content += "test1;test1@test.com;1;2024-2025;ClassA\n"
        content += "test2;test2@test.com;1;2024-2025;ClassA\n"
        content += "test3;test3@test.com;2;2024-2025;ClassB\n"
        file = csv_file(content)
        df = pd.read_csv(file, sep=";")
        assert len(df) == 3
        assert df.iloc[2]["class"] == "ClassB"
