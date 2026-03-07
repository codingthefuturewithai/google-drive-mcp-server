"""Google OAuth2 authentication for Google Drive API.

Handles credential loading, token refresh, and OAuth flow for accessing
the Google Drive API. Supports multiple authenticated accounts with
per-account token files stored in {config_dir}/tokens/<email>.json.

Authentication (running the OAuth browser flow) is intentionally NOT done
from the MCP server. The server passes allow_interactive=False so that
missing tokens produce a clear, actionable error message instead of trying
to open a browser inside a container or server process.

To add a new Google account, run:
    python scripts/add_account.py --email user@gmail.com
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]


# ---------------------------------------------------------------------------
# Account management helpers
# ---------------------------------------------------------------------------

def get_default_account(config_dir: str | Path) -> str:
    """Return the default account email, or '' if not set.

    Reads from 'default_account' file. Falls back to legacy 'current_account'
    file for users migrating from older versions.
    """
    config_dir = Path(config_dir)
    path = config_dir / "default_account"
    if path.exists():
        return path.read_text().strip()
    # Migration fallback for users with the older current_account file
    legacy = config_dir / "current_account"
    if legacy.exists():
        return legacy.read_text().strip()
    return ""


def set_default_account(config_dir: str | Path, email: str) -> None:
    """Persist the default account email to disk."""
    (Path(config_dir) / "default_account").write_text(email)


def list_authenticated_accounts(config_dir: str | Path) -> list[str]:
    """Return sorted list of authenticated account emails.

    Each email corresponds to a token file at {config_dir}/tokens/<email>.json.
    """
    tokens_dir = Path(config_dir) / "tokens"
    if not tokens_dir.exists():
        return []
    return sorted(p.stem for p in tokens_dir.glob("*.json"))


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def get_credentials(
    config_dir: str | Path,
    client_secret_path: str = "",
    account_email: str = "",
    allow_interactive: bool = True,
) -> Credentials:
    """Load or refresh Google OAuth2 credentials.

    Token file resolution order:
      1. If account_email is given: {config_dir}/tokens/<email>.json
      2. If current_account file exists: {config_dir}/tokens/<current>.json
      3. Legacy fallback: {config_dir}/token.json

    When allow_interactive=False (the MCP server's mode), a missing or invalid
    token raises PermissionError with an actionable message instead of trying
    to open a browser. The server is never the right place to run OAuth flows.

    When allow_interactive=True (scripts/add_account.py, scripts/setup.py),
    the OAuth browser flow runs normally via run_local_server().

    Args:
        config_dir: Directory for credential storage.
        client_secret_path: Override path to client_secret.json.
        account_email: Email of the specific account to load. Empty means
            use current_account file or legacy token.json.
        allow_interactive: If False, raise instead of running OAuth flow.

    Returns:
        Valid Google OAuth2 Credentials.

    Raises:
        PermissionError: If allow_interactive=False and no valid token exists.
        FileNotFoundError: If client_secret.json is missing (interactive mode).
    """
    config_dir = Path(config_dir)

    # Determine which token file to use
    if account_email:
        tokens_dir = config_dir / "tokens"
        tokens_dir.mkdir(parents=True, exist_ok=True)
        token_path = tokens_dir / f"{account_email}.json"
    else:
        # Legacy single-account fallback
        token_path = config_dir / "token.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # If still invalid, either run OAuth or raise a clear, actionable error
    if not creds or not creds.valid:
        if not allow_interactive:
            if account_email:
                raise PermissionError(
                    f"Google account '{account_email}' has not been authenticated "
                    f"with this MCP server.\n\n"
                    f"To fix this, run the following command in your terminal:\n"
                    f"  python scripts/add_account.py --email {account_email}\n\n"
                    f"A browser will open for sign-in. After clicking Allow, "
                    f"tell me and I will switch to this account."
                )
            else:
                raise PermissionError(
                    "No Google account is authenticated with this MCP server.\n\n"
                    "To fix this, run the following command in your terminal:\n"
                    "  python scripts/add_account.py\n\n"
                    "A browser will open for sign-in. After clicking Allow, "
                    "tell me and I will activate the account."
                )

        # Interactive mode: run the OAuth browser flow
        secret_path = (
            Path(client_secret_path)
            if client_secret_path
            else config_dir / "client_secret.json"
        )
        if not secret_path.exists():
            raise FileNotFoundError(
                f"client_secret.json not found at {secret_path}. "
                "Download it from the Google Cloud Console and place it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
        creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json())
    return creds


# ---------------------------------------------------------------------------
# Service builder
# ---------------------------------------------------------------------------

def build_drive_service(
    config_dir: str | Path,
    client_secret_path: str = "",
    account_email: str = "",
    allow_interactive: bool = True,
):
    """Build a Google Drive API v3 service instance.

    Args:
        config_dir: Directory for credential storage.
        client_secret_path: Override path to client_secret.json.
        account_email: Email of the account to use.
        allow_interactive: Passed through to get_credentials(). The MCP
            server always passes False — only scripts pass True.

    Returns:
        Google Drive API service resource.
    """
    creds = get_credentials(config_dir, client_secret_path, account_email, allow_interactive)
    return build("drive", "v3", credentials=creds)


def get_authenticated_email(drive_service) -> str:
    """Return the email address of the authenticated user via the Drive API."""
    about = drive_service.about().get(fields="user").execute()
    return about["user"]["emailAddress"]
