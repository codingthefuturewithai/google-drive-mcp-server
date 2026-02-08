"""Google OAuth2 authentication for Google Drive API.

Handles credential loading, token refresh, and OAuth flow for accessing
the Google Drive API.
"""

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_credentials(config_dir: str | Path, client_secret_path: str = "") -> Credentials:
    """Load or create Google OAuth2 credentials.

    Checks for a cached token at {config_dir}/token.json. If the token is
    expired, it is refreshed. If no token exists, the OAuth consent flow is
    launched using the client_secret.json file.

    Args:
        config_dir: Directory containing token.json (and optionally client_secret.json).
        client_secret_path: Override path to client_secret.json. If empty,
            defaults to {config_dir}/client_secret.json.

    Returns:
        Valid Google OAuth2 Credentials.

    Raises:
        FileNotFoundError: If client_secret.json cannot be found.
    """
    config_dir = Path(config_dir)
    token_path = config_dir / "token.json"

    creds = None

    # Load cached token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh or run OAuth flow
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        secret_path = Path(client_secret_path) if client_secret_path else config_dir / "client_secret.json"
        if not secret_path.exists():
            raise FileNotFoundError(
                f"Google client_secret.json not found at {secret_path}. "
                "Download it from the Google Cloud Console and place it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
        creds = flow.run_local_server(port=0)

    # Persist token for next run
    token_path.write_text(creds.to_json())

    return creds


def build_drive_service(config_dir: str | Path, client_secret_path: str = ""):
    """Build a Google Drive API v3 service instance.

    Args:
        config_dir: Directory for credential storage.
        client_secret_path: Override path to client_secret.json.

    Returns:
        Google Drive API service resource.
    """
    creds = get_credentials(config_dir, client_secret_path)
    return build("drive", "v3", credentials=creds)
