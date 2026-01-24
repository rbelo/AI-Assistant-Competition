"""
Unit tests for email_service module.

Tests email validation and utility functions.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
import importlib

# Add streamlit directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit")))


class MockSecrets(dict):
    """Mock for st.secrets that supports both dict and attribute access."""

    def __getattr__(self, key):
        try:
            value = self[key]
            if isinstance(value, dict):
                return MockSecrets(value)
            return value
        except KeyError:
            raise AttributeError(f"Secrets has no key '{key}'")


@pytest.fixture
def email_service():
    """Import email_service with mocked Streamlit dependencies."""
    # Create mock secrets
    mock_secrets = MockSecrets({
        "database": {"url": "postgresql://test:test@localhost:5432/test_db"},
        "drive": {"folder_id": "test_folder_id"},
        "mail": {"email": "test@example.com", "api_key": "test_api_key"},
        "app": {"link": "https://test-app.streamlit.app"},
    })

    # Mock database handler
    mock_db = MagicMock()
    mock_db.exists_user = MagicMock(return_value=True)
    sys.modules["modules.database_handler"] = mock_db

    # Import the module
    from modules import email_service

    # Patch st.secrets in the module
    email_service.st = MagicMock()
    email_service.st.secrets = mock_secrets

    return email_service


class TestValidEmail:
    """Tests for the valid_email function."""

    @pytest.mark.unit
    def test_valid_lowercase_email(self, email_service):
        """Test that valid lowercase emails pass validation."""
        assert email_service.valid_email("test@example.com") is True
        assert email_service.valid_email("user.name@domain.org") is True
        assert email_service.valid_email("user+tag@example.co.uk") is True

    @pytest.mark.unit
    def test_invalid_uppercase_email(self, email_service):
        """Test that emails with uppercase characters fail validation."""
        assert email_service.valid_email("Test@example.com") is False
        assert email_service.valid_email("test@Example.com") is False
        assert email_service.valid_email("TEST@EXAMPLE.COM") is False

    @pytest.mark.unit
    def test_invalid_format_missing_at(self, email_service):
        """Test that emails without @ symbol fail validation."""
        assert email_service.valid_email("testexample.com") is False
        assert email_service.valid_email("test") is False

    @pytest.mark.unit
    def test_invalid_format_missing_domain(self, email_service):
        """Test that emails without proper domain fail validation."""
        assert email_service.valid_email("test@") is False
        assert email_service.valid_email("test@.com") is False

    @pytest.mark.unit
    def test_invalid_format_missing_tld(self, email_service):
        """Test that emails without TLD fail validation."""
        assert email_service.valid_email("test@example") is False

    @pytest.mark.unit
    def test_valid_email_with_numbers(self, email_service):
        """Test that emails with numbers are valid."""
        assert email_service.valid_email("test123@example.com") is True
        assert email_service.valid_email("123test@example.com") is True

    @pytest.mark.unit
    def test_valid_email_with_special_chars(self, email_service):
        """Test that emails with allowed special characters are valid."""
        assert email_service.valid_email("test.user@example.com") is True
        assert email_service.valid_email("test_user@example.com") is True
        assert email_service.valid_email("test+user@example.com") is True
        assert email_service.valid_email("test-user@example.com") is True

    @pytest.mark.unit
    def test_valid_email_with_subdomain(self, email_service):
        """Test that emails with subdomains are valid."""
        assert email_service.valid_email("test@mail.example.com") is True
        assert email_service.valid_email("test@sub.domain.example.org") is True

    @pytest.mark.unit
    def test_empty_string(self, email_service):
        """Test that empty string fails validation."""
        assert email_service.valid_email("") is False

    @pytest.mark.unit
    def test_whitespace_only(self, email_service):
        """Test that whitespace-only strings fail validation."""
        assert email_service.valid_email("   ") is False


class TestSecretAccessors:
    """Tests for secret accessor functions."""

    @pytest.mark.unit
    def test_get_mail_returns_email(self, email_service):
        """Test get_mail returns the configured email."""
        result = email_service.get_mail()
        assert result == "test@example.com"

    @pytest.mark.unit
    def test_get_mail_api_pass_returns_key(self, email_service):
        """Test get_mail_api_pass returns the API key."""
        result = email_service.get_mail_api_pass()
        assert result == "test_api_key"

    @pytest.mark.unit
    def test_get_app_link_returns_url(self, email_service):
        """Test get_app_link returns the app URL when not on localhost."""
        # Mock st.context.headers to simulate production environment
        email_service.st.context.headers.get.return_value = "test-app.streamlit.app"
        result = email_service.get_app_link()
        assert result == "https://test-app.streamlit.app"

    @pytest.mark.unit
    def test_get_app_link_detects_localhost(self, email_service):
        """Test get_app_link returns localhost URL when running locally."""
        email_service.st.context.headers.get.return_value = "localhost:8501"
        result = email_service.get_app_link()
        assert result == "http://localhost:8501"

    @pytest.mark.unit
    def test_get_app_link_detects_127_0_0_1(self, email_service):
        """Test get_app_link returns localhost URL for 127.0.0.1."""
        email_service.st.context.headers.get.return_value = "127.0.0.1:8501"
        result = email_service.get_app_link()
        assert result == "http://127.0.0.1:8501"

    @pytest.mark.unit
    def test_get_app_link_falls_back_when_context_unavailable(self, email_service):
        """Test get_app_link falls back to secrets when st.context is unavailable."""
        # Simulate st.context not being available (raises exception)
        email_service.st.context.headers.get.side_effect = AttributeError("No context")
        result = email_service.get_app_link()
        assert result == "https://test-app.streamlit.app"

    @pytest.mark.unit
    def test_get_mail_missing_secret(self, email_service):
        """Test get_mail returns None when secret is missing."""
        with patch.object(email_service, "st") as mock_st:
            mock_st.secrets = {}
            # The function catches KeyError and returns None
            result = email_service.get_mail()
            assert result is None

    @pytest.mark.unit
    def test_get_mail_api_pass_missing_secret(self, email_service):
        """Test get_mail_api_pass returns None when secret is missing."""
        with patch.object(email_service, "st") as mock_st:
            mock_st.secrets = {}
            result = email_service.get_mail_api_pass()
            assert result is None
