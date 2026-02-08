"""Tests for Google OAuth2 authentication module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from google_drive.auth.google_auth import get_credentials, build_drive_service, SCOPES


class TestGetCredentials:
    """Test get_credentials function."""

    def test_loads_valid_cached_token(self, tmp_path):
        """Valid cached token is loaded and returned without OAuth flow."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.to_json.return_value = '{"token": "cached"}'

        with patch(
            "google_drive.auth.google_auth.Credentials.from_authorized_user_file",
            return_value=mock_creds,
        ) as mock_load:
            # Create a dummy token file
            token_path = tmp_path / "token.json"
            token_path.write_text("{}")

            creds = get_credentials(tmp_path)
            assert creds is mock_creds
            mock_load.assert_called_once_with(str(token_path), SCOPES)

    def test_refreshes_expired_token(self, tmp_path):
        """Expired token with refresh_token is refreshed."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_tok"
        mock_creds.to_json.return_value = '{"token": "new"}'

        token_path = tmp_path / "token.json"
        token_path.write_text("{}")

        with patch(
            "google_drive.auth.google_auth.Credentials.from_authorized_user_file",
            return_value=mock_creds,
        ):
            with patch("google_drive.auth.google_auth.Request") as mock_request:
                creds = get_credentials(tmp_path)
                mock_creds.refresh.assert_called_once_with(mock_request.return_value)

    def test_runs_oauth_flow_when_no_token(self, tmp_path):
        """OAuth flow is triggered when no cached token exists."""
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "new"}'

        # Create client_secret.json
        secret_path = tmp_path / "client_secret.json"
        secret_path.write_text('{"installed": {}}')

        with patch(
            "google_drive.auth.google_auth.InstalledAppFlow.from_client_secrets_file"
        ) as mock_flow_cls:
            mock_flow = MagicMock()
            mock_flow.run_local_server.return_value = mock_creds
            mock_flow_cls.return_value = mock_flow

            creds = get_credentials(tmp_path)

            mock_flow_cls.assert_called_once_with(str(secret_path), SCOPES)
            mock_flow.run_local_server.assert_called_once_with(port=0)
            assert creds is mock_creds

    def test_missing_client_secret_raises(self, tmp_path):
        """FileNotFoundError when client_secret.json is missing and no token."""
        with pytest.raises(FileNotFoundError, match="client_secret.json not found"):
            get_credentials(tmp_path)

    def test_custom_client_secret_path(self, tmp_path):
        """Custom client_secret_path is used instead of default."""
        custom_secret = tmp_path / "custom" / "secret.json"
        custom_secret.parent.mkdir(parents=True)
        custom_secret.write_text('{"installed": {}}')

        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "new"}'

        with patch(
            "google_drive.auth.google_auth.InstalledAppFlow.from_client_secrets_file"
        ) as mock_flow_cls:
            mock_flow = MagicMock()
            mock_flow.run_local_server.return_value = mock_creds
            mock_flow_cls.return_value = mock_flow

            get_credentials(tmp_path, client_secret_path=str(custom_secret))
            mock_flow_cls.assert_called_once_with(str(custom_secret), SCOPES)

    def test_token_persisted_after_creation(self, tmp_path):
        """Token is written to token.json after OAuth flow."""
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "persisted"}'

        secret_path = tmp_path / "client_secret.json"
        secret_path.write_text('{"installed": {}}')

        with patch(
            "google_drive.auth.google_auth.InstalledAppFlow.from_client_secrets_file"
        ) as mock_flow_cls:
            mock_flow = MagicMock()
            mock_flow.run_local_server.return_value = mock_creds
            mock_flow_cls.return_value = mock_flow

            get_credentials(tmp_path)

            token_path = tmp_path / "token.json"
            assert token_path.exists()
            assert token_path.read_text() == '{"token": "persisted"}'


class TestBuildDriveService:
    """Test build_drive_service function."""

    def test_builds_service_with_credentials(self, tmp_path):
        """Service is built using get_credentials output."""
        mock_creds = MagicMock()

        with patch("google_drive.auth.google_auth.get_credentials", return_value=mock_creds):
            with patch("google_drive.auth.google_auth.build") as mock_build:
                mock_build.return_value = MagicMock()
                service = build_drive_service(tmp_path)
                mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)
