#!/usr/bin/env python3
"""Google Drive MCP — Interactive Docker Setup

Run once to go from a downloaded client_secret.json to a running MCP server.
Re-run with --force to reconfigure.

Usage:
    python scripts/setup.py           # First-time setup
    python scripts/setup.py --force   # Reconfigure existing setup
"""

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import platformdirs


# ── Constants ────────────────────────────────────────────────────────────────

CONTAINER_NAME = "google-drive-mcp"
IMAGE_NAME = "google-drive-mcp"
BASE_PORT = 19001
CONFIG_DIR = Path(platformdirs.user_config_dir("google_drive"))
STATE_FILE = CONFIG_DIR / "docker.json"

PROJECT_ROOT = Path(__file__).parent.parent


# ── Terminal formatting ──────────────────────────────────────────────────────

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}  ✓ {text}{Colors.RESET}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}  ⚠ {text}{Colors.RESET}")


def print_error(text: str):
    print(f"{Colors.RED}  ✗ {text}{Colors.RESET}")


def print_info(text: str):
    print(f"{Colors.BLUE}  {text}{Colors.RESET}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def run_command(cmd: list, capture: bool = True, timeout: int = None) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)
        return result.returncode, result.stdout if capture else "", result.stderr if capture else ""
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def is_port_available(port: int) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result != 0
    except Exception:
        return True


def find_available_port() -> int:
    env_port = os.getenv("GOOGLE_DRIVE_PORT")
    if env_port:
        port = int(env_port)
        if is_port_available(port):
            return port
        print_error(f"GOOGLE_DRIVE_PORT={port} is already in use.")
        sys.exit(1)

    for offset in range(11):
        candidate = BASE_PORT + offset
        if is_port_available(candidate):
            return candidate

    print_error(f"No available port found in range {BASE_PORT}-{BASE_PORT + 10}")
    sys.exit(1)


def convert_path_for_docker(path: str) -> str:
    if platform.system() == "Windows" and len(path) >= 2 and path[1] == ":":
        drive = path[0].lower()
        rest = path[2:].replace("\\", "/")
        return f"/{drive}{rest}"
    return path


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def prompt_yes_no(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"  {question} {suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please enter y or n.")


def prompt_path(question: str, default: str = "") -> str:
    display = f" [{default}]" if default else ""
    answer = input(f"  {question}{display}: ").strip()
    return answer if answer else default


# ── Setup steps ──────────────────────────────────────────────────────────────

def check_docker_running() -> bool:
    print_info("Checking Docker daemon...")
    code, _, _ = run_command(["docker", "ps"])
    if code == 0:
        print_success("Docker is running")
        return True
    print_error("Docker is not running. Start Docker Desktop and try again.")
    return False


def find_client_secret_candidates() -> list:
    """Search common download locations for client_secret JSON files."""
    search_dirs = [
        CONFIG_DIR,                      # Pre-created config dir — shown to user as save target
        PROJECT_ROOT,                    # Repo root — common for developers
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home(),
    ]
    candidates = []
    seen = set()
    for d in search_dirs:
        if d.is_dir():
            for f in d.glob("client_secret*.json"):
                if f not in seen:
                    candidates.append(f)
                    seen.add(f)
    return candidates


def copy_client_secret() -> bool:
    """Find the downloaded client_secret.json and copy it into the config directory."""
    dest = CONFIG_DIR / "client_secret.json"
    candidates = find_client_secret_candidates()

    if candidates:
        print_info("Found the following client secret file(s):")
        print()
        for i, f in enumerate(candidates, 1):
            print(f"  {Colors.CYAN}[{i}]{Colors.RESET} {f}")
        if len(candidates) > 1:
            print(f"  {Colors.CYAN}[{len(candidates)+1}]{Colors.RESET} Enter a different path")
        print()

        while True:
            choice = input(f"  Select a file [1]: ").strip()
            if not choice:
                choice = "1"
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(candidates):
                    src = candidates[idx - 1]
                    break
                if idx == len(candidates) + 1:
                    src = None
                    break
            print_warning("Invalid choice. Enter a number from the list.")

        if src is None:
            # Fall through to manual entry
            candidates = []

    if not candidates:
        print_info("Enter the full path to your downloaded client secret file.")
        print_info("It will be named something like: client_secret_XXXX.apps.googleusercontent.com.json")
        print()
        while True:
            raw = input("  Path: ").strip()
            if not raw:
                print_warning("No path entered.")
                continue
            src = Path(raw).expanduser().resolve()
            if not src.exists():
                print_error(f"File not found: {src}")
                continue
            if not src.is_file():
                print_error(f"That is a directory, not a file.")
                continue
            break

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dest)
        print_success(f"Credentials copied to {dest}")
        return True
    except Exception as e:
        print_error(f"Could not copy file: {e}")
        return False


def has_authenticated_accounts() -> bool:
    """Return True if at least one account token exists (legacy or per-account)."""
    tokens_dir = CONFIG_DIR / "tokens"
    if tokens_dir.is_dir() and any(tokens_dir.glob("*.json")):
        return True
    return (CONFIG_DIR / "token.json").exists()


def run_add_account(email: str = "") -> str:
    """Run scripts/add_account.py and return the authenticated email, or '' on failure."""
    cmd = ["uv", "run", "python", "scripts/add_account.py"]
    if email:
        cmd += ["--email", email]

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        return ""

    # add_account.py prints "ACCOUNT:<email>" on success — but we ran without capture,
    # so output already went to the terminal. Just check if any tokens were saved.
    tokens_dir = CONFIG_DIR / "tokens"
    if tokens_dir.is_dir():
        saved = sorted(tokens_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if saved:
            return saved[-1].stem  # stem is the email
    if (CONFIG_DIR / "token.json").exists():
        return "(legacy token)"
    return ""


def setup_google_accounts() -> bool:
    """Ensure at least one Google account is authenticated, then offer to add more."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # ── client_secret.json ────────────────────────────────────────────────────
    if not (CONFIG_DIR / "client_secret.json").exists():
        print_warning("Google client credentials not found.")
        print()
        print_info("Before continuing, download your OAuth client credentials")
        print_info("from the Google Cloud Console:")
        print()
        print("    1. Go to https://console.cloud.google.com/")
        print("    2. Select your project (or create one)")
        print("    3. Enable the Google Drive API")
        print("    4. Go to Credentials → Create Credentials → OAuth client ID")
        print("    5. Choose Desktop app → download the JSON file")
        print()

        if not prompt_yes_no("Do you have the downloaded file ready?"):
            print_warning("Download the file from Google Cloud Console, then run setup again.")
            return False

        if not copy_client_secret():
            return False
    else:
        print_success("client_secret.json found")

    # ── First account ─────────────────────────────────────────────────────────
    if not has_authenticated_accounts():
        print()
        print_info("Next, sign in with your first Google account.")
        print_info("A browser will open — sign in and click Allow.")
        print()
        email = run_add_account()
        if not email:
            print_error("Authentication did not complete. Run setup again.")
            return False
        print_success(f"Authenticated: {email}")
    else:
        # Show which accounts are already set up
        tokens_dir = CONFIG_DIR / "tokens"
        existing = sorted(p.stem for p in tokens_dir.glob("*.json")) if tokens_dir.is_dir() else []
        if existing:
            print_success(f"Google accounts already authenticated: {', '.join(existing)}")
        else:
            print_success("Google authentication token found (legacy)")

    # ── Additional accounts ───────────────────────────────────────────────────
    print()
    print_info("You can connect multiple Google accounts so the server can access all of them.")
    while True:
        if not prompt_yes_no("Add another Google account now?", default=False):
            break
        email_hint = input("  Email address to sign in with (shown as a reminder before the browser opens, press Enter to skip): ").strip()
        email = run_add_account(email_hint)
        if email:
            print_success(f"Authenticated: {email}")
        else:
            print_warning("Authentication did not complete.")

    return True


def configure_port(existing_port: int = None) -> int:
    if existing_port and is_port_available(existing_port):
        print_success(f"Reusing previously configured port: {existing_port}")
        return existing_port
    if existing_port:
        print_warning(f"Previously configured port {existing_port} is in use")
    port = find_available_port()
    print_success(f"Using port {port}")
    return port


def configure_download_directory() -> str:
    default = str(Path.home() / "Downloads" / "google_drive")
    print_info("Files downloaded from Google Drive will go here.")
    print()
    path_str = prompt_path("Download directory", default)
    path = Path(path_str).expanduser().resolve()

    if not path.exists():
        if prompt_yes_no(f"Directory does not exist. Create {path}?"):
            path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {path}")
        else:
            print_error("Download directory must exist.")
            sys.exit(1)

    print_success(f"Download directory: {path}")
    return str(path)


def configure_directory_mounts() -> list:
    mounts = []

    print_info("The server can only access files in directories you mount into it.")
    print_info("To upload files to Drive, they must be in a mounted directory.")
    print()

    home_dir = str(Path.home())
    if prompt_yes_no(f"Mount your home directory ({home_dir}) for file access?"):
        mounts.append({
            "host_path": home_dir,
            "container_path": convert_path_for_docker(home_dir),
            "read_only": True,
        })
        print_success(f"Added: {home_dir} (read-only)")

    while True:
        print()
        if not prompt_yes_no("Add another directory?", default=False):
            break

        dir_path = prompt_path("Directory path")
        if not dir_path:
            continue

        resolved = str(Path(dir_path).expanduser().resolve())
        if not Path(resolved).is_dir():
            print_warning(f"Not a directory: {resolved}")
            if not prompt_yes_no("Add anyway?"):
                continue

        read_only = prompt_yes_no("Mount as read-only?")
        mounts.append({
            "host_path": resolved,
            "container_path": convert_path_for_docker(resolved),
            "read_only": read_only,
        })
        label = "read-only" if read_only else "read-write"
        print_success(f"Added: {resolved} ({label})")

    return mounts


def show_config_summary(port: int, download_dir: str, mounts: list):
    print_header("Configuration Summary")
    print(f"  Port:           {Colors.CYAN}{port}{Colors.RESET}")
    print(f"  Download dir:   {Colors.CYAN}{download_dir}{Colors.RESET} (read-write)")
    print(f"  Directory mounts:")
    if mounts:
        for m in mounts:
            label = "read-only" if m["read_only"] else "read-write"
            print(f"    - {Colors.CYAN}{m['host_path']}{Colors.RESET} ({label})")
    else:
        print(f"    {Colors.YELLOW}(none — only the download directory will be accessible){Colors.RESET}")
    print()


def save_docker_config(port: int, download_dir: str, mounts: list):
    config = {"port": port, "download_dir": download_dir, "mounts": mounts}
    save_state(config)
    print_success(f"Configuration saved")


def build_volume_args(config: dict) -> list:
    args = []
    args += ["-v", "google_drive_config:/home/appuser/.config/google_drive"]
    args += ["-v", "google_drive_data:/home/appuser/.local/share/google_drive"]
    args += ["-v", "google_drive_logs:/home/appuser/.local/state/google_drive"]

    download_dir = config["download_dir"]
    docker_path = convert_path_for_docker(download_dir)
    args += ["-v", f"{docker_path}:{docker_path}:rw"]

    for mount in config.get("mounts", []):
        host_path = mount["host_path"]
        container_path = mount.get("container_path", convert_path_for_docker(host_path))
        mode = "ro" if mount.get("read_only", True) else "rw"
        args += ["-v", f"{host_path}:{container_path}:{mode}"]

    return args


def copy_credentials_to_volume() -> bool:
    """Copy OAuth credentials from host config dir into the Docker volume.

    Copies client_secret.json, all per-account token files from tokens/,
    the default_account marker, and the legacy token.json if present.
    """
    print_info("Copying credentials into container volume...")

    if not (CONFIG_DIR / "client_secret.json").exists():
        print_error(f"client_secret.json not found: {CONFIG_DIR / 'client_secret.json'}")
        return False

    if not has_authenticated_accounts():
        print_error("No authentication tokens found. Run setup first.")
        return False

    # One container invocation copies everything
    script = (
        "chown 1000:1000 /dest && "
        "cp /src/client_secret.json /dest/client_secret.json && "
        "chown 1000:1000 /dest/client_secret.json && "
        "{ [ -f /src/token.json ] && "
        "  cp /src/token.json /dest/token.json && "
        "  chown 1000:1000 /dest/token.json || true; } && "
        "{ [ -d /src/tokens ] && "
        "  mkdir -p /dest/tokens && chown 1000:1000 /dest/tokens && "
        "  cp /src/tokens/*.json /dest/tokens/ 2>/dev/null && "
        "  chown 1000:1000 /dest/tokens/*.json 2>/dev/null || true; } && "
        "{ [ -f /src/default_account ] && "
        "  cp /src/default_account /dest/default_account && "
        "  chown 1000:1000 /dest/default_account || true; }"
    )

    code, _, stderr = run_command([
        "docker", "run", "--rm",
        "-v", "google_drive_config:/dest",
        "-v", f"{CONFIG_DIR}:/src:ro",
        "python:3.12-slim",
        "bash", "-c", script,
    ])

    if code != 0:
        print_error(f"Failed to copy credentials: {stderr}")
        return False

    print_success("Credentials copied")
    return True


def build_image() -> bool:
    print_info("Building Docker image (this takes a minute the first time)...")
    code, _, _ = run_command(
        ["docker", "build", "-t", IMAGE_NAME, str(PROJECT_ROOT)],
        capture=False,
        timeout=600,
    )
    if code != 0:
        print_error("Docker image build failed.")
        return False
    print_success("Docker image built")
    return True


def start_container(config: dict) -> bool:
    port = config["port"]
    print_info(f"Starting container on port {port}...")

    mounts_json = json.dumps({
        "download_dir": config["download_dir"],
        "mounts": config.get("mounts", []),
    })

    cmd = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{port}:3001",
        "-e", "PORT=3001",
        "-e", f"LOG_LEVEL={os.getenv('LOG_LEVEL', 'INFO')}",
        "-e", "GOOGLE_DRIVE_DOCKER=1",
        "-e", f"GOOGLE_DRIVE_MOUNTS={mounts_json}",
    ]
    cmd += build_volume_args(config)
    cmd += ["--restart", "unless-stopped", IMAGE_NAME]

    code, _, stderr = run_command(cmd)
    if code != 0:
        print_error(f"Failed to start container: {stderr}")
        return False

    print_success(f"Container started")
    return True


def verify_health(timeout_seconds: int = 60) -> bool:
    print_info(f"Waiting for server to be ready...")
    import time
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        code, stdout, _ = run_command(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER_NAME]
        )
        if code == 0 and stdout.strip() == "healthy":
            print_success("Server is ready")
            return True
        time.sleep(2)
    print_warning("Server is taking longer than expected to start.")
    print_info(f"Check logs with: python scripts/docker.py logs")
    return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Set up and launch the Google Drive MCP server"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reconfigure even if already set up"
    )
    args = parser.parse_args()

    print_header("Google Drive MCP — Setup")

    # Pre-create the config directory so the user has a real, existing path
    # to save their downloaded client_secret.json to.
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Credentials folder: {Colors.CYAN}{CONFIG_DIR}{Colors.RESET}")
    print(f"  Save your downloaded client_secret JSON file there.")
    print()

    existing = load_state()
    has_config = "mounts" in existing and "download_dir" in existing

    if has_config and not args.force:
        print_warning("Already configured.")
        print_info(f"To reconfigure: {Colors.CYAN}python scripts/setup.py --force{Colors.RESET}")
        print_info(f"To start:       {Colors.CYAN}python scripts/docker.py start{Colors.RESET}")
        return

    if existing and not has_config:
        print_warning("Found old configuration — migrating...")
        print()

    # Step 1: Docker
    print_header("Step 1: Docker")
    if not check_docker_running():
        sys.exit(1)

    # Step 2: Google credentials
    print_header("Step 2: Google Credentials")
    if not setup_google_accounts():
        sys.exit(1)

    # Step 3: Port
    print_header("Step 3: Port")
    port = configure_port(existing.get("port"))

    # Step 4: Download directory
    print_header("Step 4: Download Directory")
    download_dir = configure_download_directory()

    # Step 5: Directory mounts
    print_header("Step 5: Directory Access")
    mounts = configure_directory_mounts()

    # Confirm and save
    show_config_summary(port, download_dir, mounts)
    if not prompt_yes_no("Save this configuration and start the server?"):
        print_warning("Setup cancelled.")
        sys.exit(0)

    save_docker_config(port, download_dir, mounts)
    config = {"port": port, "download_dir": download_dir, "mounts": mounts}

    # Step 6: Build and launch
    print_header("Step 6: Launching Server")

    if not build_image():
        sys.exit(1)

    if not copy_credentials_to_volume():
        sys.exit(1)

    if not start_container(config):
        sys.exit(1)

    verify_health(timeout_seconds=60)

    # Done
    print_header("Setup Complete")
    print_success("Google Drive MCP server is running!")
    print()
    print_info("Connect it to Claude Code by running this command:")
    print()
    print(f"  {Colors.CYAN}claude mcp add google-drive --transport http http://localhost:{port}/mcp{Colors.RESET}")
    print()
    print_info("Useful commands going forward:")
    print(f"  {Colors.CYAN}python scripts/docker.py status{Colors.RESET}   — check if the server is running")
    print(f"  {Colors.CYAN}python scripts/docker.py logs{Colors.RESET}     — view server logs")
    print(f"  {Colors.CYAN}python scripts/docker.py stop{Colors.RESET}     — stop the server")
    print(f"  {Colors.CYAN}python scripts/docker.py update{Colors.RESET}   — rebuild after code changes")
    print()


if __name__ == "__main__":
    main()
