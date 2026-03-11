"""Tests for the auth client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lifescript.auth.auth import AuthClient, AuthSession


@pytest.fixture()
def auth():
    """Provide a fresh AuthClient (no real Supabase connection)."""
    client = AuthClient()
    return client


class TestAuthClient:
    def test_initial_state(self, auth):
        assert auth.is_authenticated is False
        assert auth.session is None

    def test_ensure_client_missing_env(self, auth):
        """Should raise when SUPABASE_URL / SUPABASE_ANON_KEY are not set."""
        with patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""}):
            with pytest.raises(RuntimeError, match="SUPABASE_URL"):
                auth._ensure_client()

    def test_sign_in_success(self, auth):
        """sign_in should set session on success."""
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_session = MagicMock()
        mock_session.access_token = "token-abc"
        mock_session.refresh_token = "refresh-xyz"
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_response.session = mock_session

        mock_client = MagicMock()
        mock_client.auth.sign_in_with_password.return_value = mock_response

        auth._client = mock_client
        session = auth.sign_in("test@example.com", "password123")

        assert isinstance(session, AuthSession)
        assert session.user_id == "user-123"
        assert session.email == "test@example.com"
        assert session.access_token == "token-abc"
        assert auth.is_authenticated is True

    def test_sign_in_failure(self, auth):
        """sign_in should raise on failed auth."""
        mock_response = MagicMock()
        mock_response.user = None
        mock_response.session = None

        mock_client = MagicMock()
        mock_client.auth.sign_in_with_password.return_value = mock_response

        auth._client = mock_client
        with pytest.raises(RuntimeError, match="ログインに失敗"):
            auth.sign_in("bad@example.com", "wrong")
        assert auth.is_authenticated is False

    def test_sign_up_success(self, auth):
        """sign_up should set session on success."""
        mock_user = MagicMock()
        mock_user.id = "user-456"
        mock_session = MagicMock()
        mock_session.access_token = "token-new"
        mock_session.refresh_token = "refresh-new"
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_response.session = mock_session

        mock_client = MagicMock()
        mock_client.auth.sign_up.return_value = mock_response

        auth._client = mock_client
        session = auth.sign_up("new@example.com", "newpass123")

        assert isinstance(session, AuthSession)
        assert session.user_id == "user-456"
        assert auth.is_authenticated is True

    def test_sign_up_email_confirmation_needed(self, auth):
        """sign_up should raise when email confirmation is required."""
        mock_user = MagicMock()
        mock_user.id = "user-789"
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_response.session = None  # No session = confirmation needed

        mock_client = MagicMock()
        mock_client.auth.sign_up.return_value = mock_response

        auth._client = mock_client
        with pytest.raises(RuntimeError, match="確認メール"):
            auth.sign_up("confirm@example.com", "pass123")

    def test_sign_out(self, auth):
        """sign_out should clear the session."""
        # Pre-set a session
        auth._session = AuthSession(
            access_token="t", refresh_token="r", user_id="u", email="e@e.com"
        )
        auth._client = MagicMock()
        assert auth.is_authenticated is True

        auth.sign_out()
        assert auth.is_authenticated is False
        assert auth.session is None

    def test_sign_out_no_client(self, auth):
        """sign_out should work even if client was never initialised."""
        auth._session = AuthSession(
            access_token="t", refresh_token="r", user_id="u", email="e@e.com"
        )
        auth.sign_out()
        assert auth.is_authenticated is False
