import sys
import types
import importlib
import os

# Add the project root to the Python path so imports from streamlit work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


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
    class _Dummy:  # Minimal placeholders
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


def test_get_parent_folder_id_from_drive_table(monkeypatch):
    dfm = load_drive_file_manager()
    # Mock st.secrets as if secrets.toml contains [drive] with folder_id
    mock_st = types.SimpleNamespace(secrets={"drive": {"folder_id": "FOLDER_123"}})
    monkeypatch.setattr(dfm, "st", mock_st, raising=False)
    assert dfm.get_parent_folder_id() == "FOLDER_123"


def test_get_parent_folder_id_missing_returns_none(monkeypatch):
    dfm = load_drive_file_manager()
    # Mock st.secrets without drive table
    mock_st = types.SimpleNamespace(secrets={})
    monkeypatch.setattr(dfm, "st", mock_st, raising=False)
    assert dfm.get_parent_folder_id() is None
