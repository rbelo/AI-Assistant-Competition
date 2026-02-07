"""
Unit tests for email_service.py password reset flow.

Covers: set_password, generate_set_password_link, send_set_password_email, get_base_url.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)


class MockSecrets(dict):
    def __getattr__(self, key):
        try:
            value = self[key]
            if isinstance(value, dict):
                return MockSecrets(value)
            return value
        except KeyError as err:
            raise AttributeError(f"Secrets has no key '{key}'") from err


@pytest.fixture
def email_mod():
    """Import email_service with mocked dependencies."""
    mock_secrets = MockSecrets(
        {
            "database": {"url": "postgresql://test:test@localhost:5432/test_db"},
            "mail": {"email": "sender@example.com", "api_key": "api_key_123"},
            "app": {"link": "https://myapp.streamlit.app"},
        }
    )

    mock_db = MagicMock()
    mock_db.exists_user = MagicMock(return_value=True)
    sys.modules["modules.database_handler"] = mock_db

    from modules import email_service

    email_service.st = MagicMock()
    email_service.st.secrets = mock_secrets
    # Make st.context unavailable so get_app_link falls back to secrets
    email_service.st.context.headers.get.side_effect = AttributeError

    return email_service


# ---------------------------------------------------------------------------
# get_base_url
# ---------------------------------------------------------------------------
class TestGetBaseUrl:
    @pytest.mark.unit
    def test_returns_app_link(self, email_mod):
        result = email_mod.get_base_url()
        assert result == "https://myapp.streamlit.app"


# ---------------------------------------------------------------------------
# generate_set_password_link
# ---------------------------------------------------------------------------
class TestGenerateSetPasswordLink:
    @pytest.mark.unit
    def test_returns_url_with_token(self, email_mod):
        email_mod.SECRET_KEY = "test-secret-key"
        link = email_mod.generate_set_password_link("user@example.com")
        assert link.startswith("https://myapp.streamlit.app?set_password=")
        # Token should be a non-empty JWT string
        token = link.split("set_password=")[1]
        assert len(token) > 10

    @pytest.mark.unit
    def test_token_contains_email(self, email_mod):
        import jwt

        email_mod.SECRET_KEY = "test-secret-key"
        link = email_mod.generate_set_password_link("user@example.com")
        token = link.split("set_password=")[1]
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["email"] == "user@example.com"
        assert "exp" in payload


# ---------------------------------------------------------------------------
# send_set_password_email
# ---------------------------------------------------------------------------
class TestSendSetPasswordEmail:
    @pytest.mark.unit
    def test_sends_email_successfully(self, email_mod):
        with patch("modules.email_service.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = email_mod.send_set_password_email("user@example.com", "https://app.com?set_password=token123")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("sender@example.com", "api_key_123")
        mock_server.sendmail.assert_called_once()
        # Verify recipient
        sendmail_args = mock_server.sendmail.call_args[0]
        assert sendmail_args[1] == "user@example.com"

    @pytest.mark.unit
    def test_returns_false_on_smtp_error(self, email_mod):
        with patch("modules.email_service.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__ = MagicMock(side_effect=Exception("SMTP connection failed"))
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = email_mod.send_set_password_email("user@example.com", "https://link")

        assert result is False


# ---------------------------------------------------------------------------
# set_password
# ---------------------------------------------------------------------------
class TestSetPassword:
    @pytest.mark.unit
    def test_sends_email_when_user_exists(self, email_mod):
        with patch.object(email_mod, "exists_user", return_value=True):
            with patch.object(email_mod, "generate_set_password_link", return_value="https://link") as mock_gen:
                with patch.object(email_mod, "send_set_password_email", return_value=True) as mock_send:
                    result = email_mod.set_password("user@example.com")

        assert result is True
        mock_gen.assert_called_once_with("user@example.com")
        mock_send.assert_called_once_with("user@example.com", "https://link")

    @pytest.mark.unit
    def test_returns_none_when_user_not_found(self, email_mod):
        with patch.object(email_mod, "exists_user", return_value=False):
            result = email_mod.set_password("nobody@example.com")
        assert result is None

    @pytest.mark.unit
    def test_returns_false_when_email_fails(self, email_mod):
        with patch.object(email_mod, "exists_user", return_value=True):
            with patch.object(email_mod, "generate_set_password_link", return_value="https://link"):
                with patch.object(email_mod, "send_set_password_email", return_value=False):
                    result = email_mod.set_password("user@example.com")
        assert result is False
