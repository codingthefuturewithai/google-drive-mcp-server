#!/usr/bin/env python3
"""Add a Google account to the MCP server.

Opens a browser for OAuth sign-in, saves the token, and (if the Docker container
is running) automatically copies it into the container volume so the MCP server
can use it immediately without a restart.

Usage:
    python scripts/add_account.py
    python scripts/add_account.py --email user@example.com
"""

import argparse
import subprocess
import sys
from pathlib import Path

import platformdirs

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Import only the auth module directly — avoids loading the full server package
_auth_module = Path(__file__).parent.parent / "google_drive" / "auth" / "google_auth.py"
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("google_auth", _auth_module)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SCOPES = _mod.SCOPES
set_default_account = _mod.set_default_account

CONTAINER_NAME = "google-drive-mcp"
CONFIG_DIR = Path(platformdirs.user_config_dir("google_drive"))


def is_container_running() -> bool:
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name=^{CONTAINER_NAME}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return CONTAINER_NAME in result.stdout


def copy_token_to_volume(email: str) -> bool:
    """Copy a newly-authenticated token into the running Docker container's volume."""
    token_path = CONFIG_DIR / "tokens" / f"{email}.json"
    current_account_path = CONFIG_DIR / "current_account"

    script = (
        f"mkdir -p /dest/tokens && "
        f"chown 1000:1000 /dest/tokens && "
        f"cp /src_token/{email}.json /dest/tokens/{email}.json && "
        f"chown 1000:1000 /dest/tokens/{email}.json"
    )

    cmd = [
        "docker", "run", "--rm",
        "-v", "google_drive_config:/dest",
        "-v", f"{token_path}:/src_token/{email}.json:ro",
    ]

    if current_account_path.exists():
        script += (
            " && cp /src_account/current_account /dest/current_account"
            " && chown 1000:1000 /dest/current_account"
        )
        cmd += ["-v", f"{current_account_path}:/src_account/current_account:ro"]

    cmd += ["python:3.12-slim", "bash", "-c", script]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Add a Google account to the MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "After sign-in completes, the MCP server will have access to this account.\n"
            "Use the switch_account tool to activate it in an ongoing session."
        ),
    )
    parser.add_argument(
        "--email",
        metavar="EMAIL",
        help="Email hint shown before the browser opens (optional — auto-detected after sign-in)",
    )
    args = parser.parse_args()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tokens_dir = CONFIG_DIR / "tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)

    secret_path = CONFIG_DIR / "client_secret.json"
    if not secret_path.exists():
        print(f"Error: client_secret.json not found at {secret_path}")
        print(
            "Download it from Google Cloud Console:\n"
            "  1. https://console.cloud.google.com/\n"
            "  2. APIs & Services → Credentials → OAuth client ID → Desktop app\n"
            "  3. Download JSON and place it at the path shown above"
        )
        sys.exit(1)

    if args.email:
        print(f"Opening browser — sign in as: {args.email}")
    else:
        print("Opening browser for Google sign-in.")
        print("Sign in with the Google account you want to add.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
    creds = flow.run_local_server(port=0)

    # Discover the actual signed-in email
    service = build("drive", "v3", credentials=creds)
    email = service.about().get(fields="user").execute()["user"]["emailAddress"]

    if args.email and args.email.lower() != email.lower():
        print(f"Note: signed in as {email} (not {args.email})")

    # Save token to per-account path
    token_path = tokens_dir / f"{email}.json"
    token_path.write_text(creds.to_json())

    # Set as the default account (first-time setup or explicit choice)
    set_default_account(CONFIG_DIR, email)

    print(f"Authenticated: {email}")

    # Copy into running Docker container if applicable
    if is_container_running():
        print("Copying token into Docker container volume...")
        if copy_token_to_volume(email):
            print("Done. The MCP server can now access this account.")
            print(f"Ask your AI assistant to call switch_account with email '{email}'.")
        else:
            print("Warning: could not copy token to Docker volume.")
            print("Restart the container to apply: python scripts/docker.py restart")
    else:
        print("Token saved. Start or restart the MCP server to use this account.")

    # Print a parseable marker for callers (e.g. setup.py)
    print(f"\nACCOUNT:{email}")


if __name__ == "__main__":
    main()
