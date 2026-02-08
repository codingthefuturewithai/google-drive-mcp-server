#!/usr/bin/env python3
"""Google Drive Docker Manager

Cross-platform script to manage the Google Drive MCP server Docker container.

Usage:
    python scripts/docker.py start    # Build and start container
    python scripts/docker.py stop     # Stop container
    python scripts/docker.py restart  # Restart container
    python scripts/docker.py update   # Rebuild image and restart (for code changes)
    python scripts/docker.py status   # Show container status
    python scripts/docker.py logs     # Tail container logs
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Tuple

import platformdirs


class Colors:
    """ANSI color codes for terminal output"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"


CONTAINER_NAME = "google-drive-mcp"
IMAGE_NAME = "google-drive-mcp"
BASE_PORT = 19001
CONFIG_DIR = Path(platformdirs.user_config_dir("google_drive"))
STATE_FILE = CONFIG_DIR / "docker.json"

# OAuth credential files that must exist before the container can work
REQUIRED_CREDS = ["client_secret.json", "token.json"]


def print_header(text: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}  {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}  {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}  {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}  {text}{Colors.RESET}")


def run_command(cmd: list, capture: bool = True, timeout: int = None) -> Tuple[int, str, str]:
    """Run shell command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout if capture else "", result.stderr if capture else ""
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def is_port_available(port: int) -> bool:
    """Check if port is available"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result != 0
    except Exception:
        return True


def find_available_port() -> int:
    """Find an available port starting from BASE_PORT.

    Used ONLY by 'start'. Scans BASE_PORT, BASE_PORT+1, ... up to +10.
    Respects GOOGLE_DRIVE_PORT env var as an explicit override.
    """
    env_port = os.getenv("GOOGLE_DRIVE_PORT")
    if env_port:
        port = int(env_port)
        if is_port_available(port):
            return port
        print_error(f"GOOGLE_DRIVE_PORT={port} is already in use.")
        print_info("Free the port or choose a different one.")
        sys.exit(1)

    for offset in range(11):
        candidate = BASE_PORT + offset
        if is_port_available(candidate):
            return candidate

    print_error(f"No available port found in range {BASE_PORT}-{BASE_PORT + 10}")
    print_info(f"Set an explicit port: {Colors.CYAN}GOOGLE_DRIVE_PORT=19020 python scripts/docker.py start{Colors.RESET}")
    sys.exit(1)


def require_saved_port(command_name: str) -> int:
    """Return the saved port from state, or fail loudly.

    Used by 'restart' and 'update' — these must reuse the port from 'start'.
    """
    state = load_state()
    port = state.get("port")

    if port is None:
        print_error("No saved port found — the container has never been started.")
        print_info(f"Run {Colors.CYAN}python scripts/docker.py start{Colors.RESET} first.")
        sys.exit(1)

    if not is_port_available(port):
        # Check if it's our own container occupying the port (that's fine for restart/update)
        exists, running, _ = get_container_status()
        if running:
            # Our container is using it — we'll stop it before restarting
            return port

        print_error(f"Saved port {port} is in use by another process.")
        print_info("Check what's using it:")
        print(f"  {Colors.CYAN}lsof -i :{port}{Colors.RESET}  (macOS/Linux)")
        print(f"  {Colors.CYAN}netstat -ano | findstr :{port}{Colors.RESET}  (Windows)")
        print()
        print_info(f"Free the port, or re-run: {Colors.CYAN}python scripts/docker.py start{Colors.RESET} to pick a new one.")
        sys.exit(1)

    return port


def load_state() -> dict:
    """Load persisted state"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    """Save state to disk"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_container_status() -> Tuple[bool, bool, str]:
    """Get container status: (exists, running, health)"""
    code, stdout, _ = run_command(
        ["docker", "ps", "-a", "--filter", f"name=^{CONTAINER_NAME}$", "--format", "{{.Status}}"]
    )
    if not stdout.strip():
        return False, False, "not found"

    status = stdout.strip()
    running = "Up" in status
    if "healthy" in status:
        health = "healthy"
    elif "starting" in status:
        health = "starting"
    elif running:
        health = "running"
    else:
        health = "stopped"
    return True, running, health


def check_docker_running() -> bool:
    """Check if Docker daemon is running"""
    print_info("Checking Docker daemon...")
    code, _, _ = run_command(["docker", "ps"])

    if code == 0:
        print_success("Docker daemon is running")
        return True

    print_error("Docker daemon is not running")
    print_info("Start Docker Desktop and try again")
    return False


def check_oauth_credentials() -> bool:
    """Check if OAuth credentials exist in the config directory.

    The container needs client_secret.json and token.json to authenticate
    with Google Drive. These must be generated on the host first (the OAuth
    flow requires a browser).
    """
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
        print(f"  1. Go to https://console.cloud.google.com/")
        print(f"  2. Enable the Google Drive API")
        print(f"  3. Create OAuth client credentials (Desktop app)")
        print(f"  4. Download the JSON and save as:")
        print(f"     {Colors.CYAN}{CONFIG_DIR / 'client_secret.json'}{Colors.RESET}")
        print()

    if "token.json" in missing and "client_secret.json" not in missing:
        print_info("To generate token.json (run on host, needs browser):")
        print(f"  {Colors.CYAN}cd {Path(__file__).parent.parent}{Colors.RESET}")
        print(f"  {Colors.CYAN}uv run python -c \"from google_drive.auth import get_credentials; import platformdirs; get_credentials(platformdirs.user_config_dir('google_drive'))\"{Colors.RESET}")
        print()

    return False


def copy_credentials_to_volume() -> bool:
    """Copy OAuth credentials from host config dir into the Docker volume.

    Docker named volumes are not directly writable from the host, so we use
    a temporary container to copy the files in.
    """
    print_info("Copying OAuth credentials into Docker volume...")

    for cred_file in REQUIRED_CREDS:
        host_path = CONFIG_DIR / cred_file
        if not host_path.exists():
            print_error(f"Credential file not found: {host_path}")
            return False

        # Use a temporary container to copy into the named volume
        code, _, stderr = run_command([
            "docker", "run", "--rm",
            "-v", f"google_drive_config:/dest",
            "-v", f"{host_path}:/src/{cred_file}:ro",
            "python:3.12-slim",
            "bash", "-c",
            f"cp /src/{cred_file} /dest/{cred_file} && chown 1000:1000 /dest/{cred_file}"
        ])

        if code != 0:
            print_error(f"Failed to copy {cred_file}: {stderr}")
            return False

    print_success("Credentials copied to container volume")
    return True


def build_image() -> bool:
    """Build the Docker image from source code"""
    project_root = Path(__file__).parent.parent

    print_info("Building Docker image from latest code...")
    print_info(f"Project root: {project_root}")

    # Build with output visible
    code, _, _ = run_command(
        ["docker", "build", "-t", IMAGE_NAME, str(project_root)],
        capture=False,
        timeout=600
    )

    if code != 0:
        print_error("Failed to build Docker image")
        return False

    print_success("Docker image built successfully")
    return True


def start_container(port: int) -> bool:
    """Start the container on the given port."""
    print_info(f"Starting container on port {port}...")

    code, _, stderr = run_command([
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{port}:3001",
        "-e", "PORT=3001",
        "-e", f"LOG_LEVEL={os.getenv('LOG_LEVEL', 'INFO')}",
        "-v", "google_drive_config:/home/appuser/.config/google_drive",
        "-v", "google_drive_data:/home/appuser/.local/share/google_drive",
        "-v", "google_drive_logs:/home/appuser/.local/state/google_drive",
        "-v", "google_drive_downloads:/home/appuser/Downloads/google_drive",
        "--restart", "unless-stopped",
        IMAGE_NAME
    ])

    if code != 0:
        print_error(f"Failed to start container: {stderr}")
        return False

    # Save state
    save_state({"port": port})
    print_success(f"Container started on port {port}")
    return True


def stop_container() -> bool:
    """Stop and remove the container"""
    print_info("Stopping container...")
    run_command(["docker", "stop", CONTAINER_NAME])
    run_command(["docker", "rm", CONTAINER_NAME])
    print_success("Container stopped")
    return True


def verify_health(timeout_seconds: int = 60) -> bool:
    """Wait for container to become healthy"""
    print_info(f"Waiting up to {timeout_seconds}s for container to become healthy...")

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        code, stdout, _ = run_command(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER_NAME]
        )

        if code == 0:
            health_status = stdout.strip()

            if health_status == "healthy":
                elapsed = int(time.time() - start_time)
                print_success(f"Container is healthy (took {elapsed}s)")
                return True

            print_info(f"Health status: {health_status}, waiting...")

        time.sleep(2)

    print_warning("Health check timeout - container may still be starting")
    print_info(f"Check logs with: docker logs {CONTAINER_NAME}")
    return False


def cmd_start():
    """Build and start the container"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Start{Colors.RESET}\n")

    # Check if already running
    exists, running, _ = get_container_status()
    if running:
        state = load_state()
        port = state.get("port", BASE_PORT)
        print_warning("Container already running")
        print_info(f"MCP endpoint: http://localhost:{port}/mcp")
        print_info("Use 'update' to rebuild and restart, or 'restart' to just restart")
        return

    if not check_docker_running():
        sys.exit(1)

    # Check OAuth credentials before building
    print_header("Step 1: Checking OAuth Credentials")
    if not check_oauth_credentials():
        print_error("Cannot start without Google OAuth credentials.")
        print_info("Set up credentials first, then run 'start' again.")
        sys.exit(1)

    # Remove stopped container if exists
    if exists and not running:
        print_info("Removing stopped container...")
        run_command(["docker", "rm", CONTAINER_NAME])

    print_header("Step 2: Building Image")
    if not build_image():
        sys.exit(1)

    print_header("Step 3: Copying Credentials")
    if not copy_credentials_to_volume():
        sys.exit(1)

    print_header("Step 4: Starting Container")
    port = find_available_port()
    if not start_container(port):
        sys.exit(1)

    print_header("Step 5: Verifying Health")
    verify_health(timeout_seconds=60)

    # Success summary
    print_header("Start Complete")
    print_success("Google Drive MCP server is running!")
    print()
    print_info(f"MCP endpoint: http://localhost:{port}/mcp")
    print()
    print_info("Add to Claude Code:")
    print(f"  {Colors.CYAN}claude mcp add google-drive --transport http http://localhost:{port}/mcp{Colors.RESET}")
    print()
    print_info("Useful commands:")
    print(f"  View logs:    {Colors.CYAN}python scripts/docker.py logs{Colors.RESET}")
    print(f"  Check status: {Colors.CYAN}python scripts/docker.py status{Colors.RESET}")
    print(f"  Update:       {Colors.CYAN}python scripts/docker.py update{Colors.RESET}")
    print()


def cmd_stop():
    """Stop the container"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Stop{Colors.RESET}\n")
    stop_container()


def cmd_restart():
    """Restart the container (without rebuild)"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Restart{Colors.RESET}\n")

    port = require_saved_port("restart")

    stop_container()

    print_header("Starting Container")
    if not start_container(port):
        sys.exit(1)

    print_header("Verifying Health")
    verify_health(timeout_seconds=60)

    print_header("Restart Complete")
    print_success("Container restarted successfully")
    print_info(f"MCP endpoint: http://localhost:{port}/mcp")
    print()


def cmd_update():
    """Rebuild image and restart container (for code changes)"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Update{Colors.RESET}")
    print("Rebuilds image from latest code and restarts container\n")

    if not check_docker_running():
        sys.exit(1)

    # Check if container exists
    state = load_state()
    exists, _, _ = get_container_status()
    if not exists and not state.get("port"):
        print_warning("No existing deployment found")
        print_info("Running 'start' instead...")
        cmd_start()
        return

    port = require_saved_port("update")

    print_header("Step 1: Stopping Container")
    if exists:
        stop_container()
    else:
        print_info("Container not running")

    print_header("Step 2: Rebuilding Image")
    if not build_image():
        sys.exit(1)

    print_header("Step 3: Copying Credentials")
    if not copy_credentials_to_volume():
        print_warning("Credential copy failed - container may not authenticate")

    print_header("Step 4: Starting Container")
    if not start_container(port):
        sys.exit(1)

    print_header("Step 5: Verifying Health")
    verify_health(timeout_seconds=60)

    print_header("Update Complete")
    print_success("Google Drive MCP server updated with latest code!")
    print()
    print_info(f"MCP endpoint: http://localhost:{port}/mcp")
    print()
    print_info("Useful commands:")
    print(f"  View logs:    {Colors.CYAN}python scripts/docker.py logs{Colors.RESET}")
    print(f"  Check status: {Colors.CYAN}python scripts/docker.py status{Colors.RESET}")
    print()


def cmd_status():
    """Show container status"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Status{Colors.RESET}\n")

    exists, running, health = get_container_status()
    state = load_state()
    port = state.get("port", "unknown")

    if not exists:
        print_info("Status: not deployed")
        print_info("Run 'python scripts/docker.py start' to deploy")
    elif running:
        print_success(f"Status: {health}")
        print_info(f"Port: {port}")
        print_info(f"MCP endpoint: http://localhost:{port}/mcp")
    else:
        print_warning("Status: stopped")
        print_info("Run 'python scripts/docker.py start' to start")
    print()


def cmd_logs():
    """Tail container logs"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Logs{Colors.RESET}")
    print("Press Ctrl+C to stop\n")
    subprocess.run(["docker", "logs", "-f", CONTAINER_NAME])


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Google Drive Docker Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start    Build image and start container
  stop     Stop and remove container
  restart  Restart container (without rebuild)
  update   Rebuild image and restart (use after code changes)
  status   Show container status
  logs     Tail container logs

Examples:
  python scripts/docker.py start     # Initial deployment
  python scripts/docker.py update    # After making code changes
  python scripts/docker.py logs      # View container logs
"""
    )
    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "update", "status", "logs"],
        help="Command to run"
    )

    args = parser.parse_args()

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "update": cmd_update,
        "status": cmd_status,
        "logs": cmd_logs,
    }

    try:
        commands[args.command]()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Cancelled by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
