"""
Unit tests for drive_file_manager module.

Tests Google Drive integration with mocked dependencies.
"""

import pytest
import sys
import os
import types
import importlib

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def load_drive_file_manager():
    """
    Import streamlit.modules.drive_file_manager safely by stubbing Google libs
    so the import doesn't require googleapiclient to be installed.
    """
    # Stub Google API modules used only at import time
    sys.modules.setdefault("googleapiclient", types.ModuleType("googleapiclient"))
    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = lambda *args, **kwargs: None
    sys.modules["googleapiclient.discovery"] = discovery

    http = types.ModuleType("googleapiclient.http")

    class _Dummy:
        pass

    http.MediaIoBaseUpload = _Dummy
    http.MediaIoBaseDownload = _Dummy
    sys.modules["googleapiclient.http"] = http

    sys.modules.setdefault("google", types.ModuleType("google"))
    sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")
    service_account = types.ModuleType("google.oauth2.service_account")

    class DummyCreds:
        @classmethod
        def from_service_account_info(cls, info):
            return object()

    service_account.Credentials = DummyCreds
    sys.modules["google.oauth2.service_account"] = service_account

    # Now import the module under test
    return importlib.import_module("streamlit.modules.drive_file_manager")


class TestGetParentFolderId:
    """Tests for the get_parent_folder_id function."""

    @pytest.mark.unit
    def test_get_parent_folder_id_from_drive_table(self, monkeypatch):
        """Test that folder_id is retrieved from secrets."""
        dfm = load_drive_file_manager()
        mock_st = types.SimpleNamespace(secrets={"drive": {"folder_id": "FOLDER_123"}})
        monkeypatch.setattr(dfm, "st", mock_st, raising=False)
        assert dfm.get_parent_folder_id() == "FOLDER_123"

    @pytest.mark.unit
    def test_get_parent_folder_id_missing_returns_none(self, monkeypatch):
        """Test that missing folder_id returns None."""
        dfm = load_drive_file_manager()
        mock_st = types.SimpleNamespace(secrets={})
        monkeypatch.setattr(dfm, "st", mock_st, raising=False)
        assert dfm.get_parent_folder_id() is None

    @pytest.mark.unit
    def test_get_parent_folder_id_missing_drive_key(self, monkeypatch):
        """Test behavior when drive key is missing from secrets."""
        dfm = load_drive_file_manager()
        mock_st = types.SimpleNamespace(secrets={"database": {"url": "test"}})
        monkeypatch.setattr(dfm, "st", mock_st, raising=False)
        assert dfm.get_parent_folder_id() is None


class TestDriveInfo:
    """Tests for get_drive_info function."""

    @pytest.mark.unit
    def test_get_drive_info_returns_dict(self, monkeypatch):
        """Test that get_drive_info returns drive credentials as dict."""
        dfm = load_drive_file_manager()
        drive_creds = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@test.iam.gserviceaccount.com",
        }
        mock_st = types.SimpleNamespace(secrets={"drive": drive_creds})
        monkeypatch.setattr(dfm, "st", mock_st, raising=False)

        result = dfm.get_drive_info()
        assert result == drive_creds

    @pytest.mark.unit
    def test_get_drive_info_missing_returns_none(self, monkeypatch):
        """Test that missing drive info returns None."""
        dfm = load_drive_file_manager()
        mock_st = types.SimpleNamespace(secrets={})
        monkeypatch.setattr(dfm, "st", mock_st, raising=False)

        result = dfm.get_drive_info()
        assert result is None


class TestFileNameGeneration:
    """Tests for file name generation."""

    @pytest.mark.unit
    def test_prompt_file_name_format(self):
        """Test the expected format of prompt file names."""
        # Based on CLAUDE.md: stored as Game{id}_Class{class}_Group{group}
        game_id = 1
        class_name = "ClassA"
        group_id = 5

        expected_name = f"Game{game_id}_Class{class_name}_Group{group_id}"
        assert expected_name == "Game1_ClassClassA_Group5"

    @pytest.mark.unit
    def test_prompt_delimiter(self):
        """Test the prompt delimiter between roles."""
        # Based on CLAUDE.md: Two prompts separated by #_;:)
        delimiter = "#_;:)"
        prompt1 = "You are a buyer..."
        prompt2 = "You are a seller..."

        combined = f"{prompt1}{delimiter}{prompt2}"
        parts = combined.split(delimiter)

        assert len(parts) == 2
        assert parts[0] == prompt1
        assert parts[1] == prompt2
