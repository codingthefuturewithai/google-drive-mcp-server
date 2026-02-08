#!/usr/bin/env python3
"""Google Drive MCP — Interactive Docker Setup

Run once to configure Docker deployment. Re-run with --force to reconfigure.

Usage:
    python scripts/setup.py           # First-time setup
    python scripts/setup.py --force   # Reconfigure existing setup
"""

import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import platformdirs


# ── Constants ────────────────────────────────────────────────────────────────

CONTAINER_NAME = "google-drive-mcp"
BASE_PORT = 19001
CONFIG_DIR = Path(platformdirs.user_config_dir("google_drive"))
STATE_FILE = CONFIG_DIR / "docker.json"
REQUIRED_CREDS = ["client_secret.json", "token.json"]


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
    print(f"{Colors.GREEN}  {text}{Colors.RESET}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}  {text}{Colors.RESET}")


def print_error(text: str):
    print(f"{Colors.RED}  {text}{Colors.RESET}")


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
    """Find an available port, respecting GOOGLE_DRIVE_PORT env var."""
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
    print_info(f"Set an explicit port: {Colors.CYAN}GOOGLE_DRIVE_PORT=19020 python scripts/setup.py{Colors.RESET}")
    sys.exit(1)


def convert_path_for_docker(path: str) -> str:
    """Convert host path for Docker volume mounts.

    On Windows, converts 'C:\\Users\\tim' to '/c/Users/tim' for Docker Desktop.
    macOS and Linux paths pass through unchanged.
    """
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
        print_success("Docker daemon is running")
        return True
    print_error("Docker daemon is not running")
    print_info("Start Docker Desktop and try again")
    return False


def check_oauth_credentials() -> bool:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in REQUIRED_CREDS if not (CONFIG_DIR / f).exists()]

    if not missing:
        print_success("OAuth credentials found")
        return True

    print_error("Missing Google OAuth credentials:")
    for f in missing:
        print_error(f"  - {CONFIG_DIR / f}")
    print()

    if "client_secret.json" in missing:
        print_info("To get client_secret.json:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Enable the Google Drive API")
        print("  3. Create OAuth client credentials (Desktop app)")
        print("  4. Download the JSON and save as:")
        print(f"     {Colors.CYAN}{CONFIG_DIR / 'client_secret.json'}{Colors.RESET}")
        print()

    if "token.json" in missing and "client_secret.json" not in missing:
        project_root = Path(__file__).parent.parent
        print_info("To generate token.json (run on host, needs browser):")
        print(f"  {Colors.CYAN}cd {project_root}{Colors.RESET}")
        print(f"  {Colors.CYAN}uv run python -c \"from google_drive.auth import get_credentials; import platformdirs; get_credentials(platformdirs.user_config_dir('google_drive'))\"{Colors.RESET}")
        print()

    return False


def configure_port(existing_port: int = None) -> int:
    """Find or confirm port for the container."""
    if existing_port:
        if is_port_available(existing_port):
            print_success(f"Reusing previously configured port: {existing_port}")
            return existing_port
        print_warning(f"Previously configured port {existing_port} is in use")

    port = find_available_port()
    print_success(f"Port {port} is available")
    return port


def configure_download_directory() -> str:
    """Prompt user for download directory path."""
    default = str(Path.home() / "Downloads" / "google_drive")

    print_info("When the AI downloads files from Google Drive, they go here.")
    print_info("This directory is bind-mounted read-write into the container.")
    print()
    path_str = prompt_path("Download directory", default)
    path = Path(path_str).expanduser().resolve()

    if not path.exists():
        if prompt_yes_no(f"Directory does not exist. Create {path}?"):
            path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {path}")
        else:
            print_error("Download directory must exist. Aborting.")
            sys.exit(1)

    print_success(f"Download directory: {path}")
    return str(path)


def configure_directory_mounts() -> list:
    """Prompt user for directories to mount into the container.

    Returns list of dicts: {"host_path": str, "container_path": str, "read_only": bool}
    """
    mounts = []

    print_info("The Docker container can only access files in directories you mount.")
    print_info("For upload_file to work, the file must be in a mounted directory.")
    print_info("Mounts default to read-only. The download directory is always read-write.")
    print()

    home_dir = str(Path.home())
    if prompt_yes_no(f"Mount home directory ({home_dir}) read-only?"):
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
            if not prompt_yes_no("Add anyway? (it must exist when container starts)"):
                continue

        read_only = prompt_yes_no("Mount as read-only?")
        mounts.append({
            "host_path": resolved,
            "container_path": convert_path_for_docker(resolved),
            "read_only": read_only,
        })
        label = "read-only" if read_only else "read-write"
        print_success(f"Added: {resolved} ({label})")

    if not mounts:
        print_warning("No directories mounted — upload_file will only work with")
        print_warning("files inside the download directory.")

    return mounts


def show_config_summary(port: int, download_dir: str, mounts: list):
    """Display configuration summary for user confirmation."""
    print_header("Configuration Summary")
    print(f"  Port:           {Colors.CYAN}{port}{Colors.RESET}")
    print(f"  Download dir:   {Colors.CYAN}{download_dir}{Colors.RESET} (read-write)")
    print(f"  Directory mounts:")
    if mounts:
        for m in mounts:
            label = "read-only" if m["read_only"] else "read-write"
            print(f"    - {Colors.CYAN}{m['host_path']}{Colors.RESET} ({label})")
    else:
        print(f"    {Colors.YELLOW}(none){Colors.RESET}")
    print()


def save_docker_config(port: int, download_dir: str, mounts: list):
    """Save expanded docker.json with mount configuration."""
    config = {
        "port": port,
        "download_dir": download_dir,
        "mounts": mounts,
    }
    save_state(config)
    print_success(f"Configuration saved to {STATE_FILE}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive Docker setup for Google Drive MCP server"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reconfigure even if docker.json already exists"
    )
    args = parser.parse_args()

    print_header("Google Drive MCP — Docker Setup")

    # Check if already configured
    existing = load_state()
    has_mounts = "mounts" in existing and "download_dir" in existing

    if has_mounts and not args.force:
        print_warning("Docker setup already configured.")
        print_info(f"Config file: {STATE_FILE}")
        print()
        print_info(f"To reconfigure: {Colors.CYAN}python scripts/setup.py --force{Colors.RESET}")
        print_info(f"To start:       {Colors.CYAN}python scripts/docker.py start{Colors.RESET}")
        return

    if existing and not has_mounts:
        print_warning("Found old-format docker.json (port only). Migrating...")
        print_info("Your existing port will be preserved.")
        print()

    # Step 1: Docker daemon
    print_header("Step 1: Docker Daemon")
    if not check_docker_running():
        sys.exit(1)

    # Step 2: OAuth credentials
    print_header("Step 2: OAuth Credentials")
    if not check_oauth_credentials():
        print_error("Cannot configure without Google OAuth credentials.")
        print_info("Set up credentials first, then run setup again.")
        sys.exit(1)

    # Step 3: Port
    print_header("Step 3: Port")
    port = configure_port(existing.get("port"))

    # Step 4: Download directory
    print_header("Step 4: Download Directory")
    download_dir = configure_download_directory()

    # Step 5: Directory mounts
    print_header("Step 5: Directory Mounts")
    mounts = configure_directory_mounts()

    # Confirm
    show_config_summary(port, download_dir, mounts)
    if not prompt_yes_no("Save this configuration?"):
        print_warning("Setup cancelled.")
        sys.exit(0)

    save_docker_config(port, download_dir, mounts)

    # Next steps
    print_header("Setup Complete")
    print_success("Docker configuration saved!")
    print()
    print_info("Next steps:")
    print(f"  {Colors.CYAN}python scripts/docker.py start{Colors.RESET}    # Build and start container")
    print(f"  {Colors.CYAN}python scripts/docker.py status{Colors.RESET}   # Check container status")
    print()


if __name__ == "__main__":
    main()
