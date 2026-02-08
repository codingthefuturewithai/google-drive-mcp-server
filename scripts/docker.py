#!/usr/bin/env python3
"""Google Drive Docker Manager

Non-interactive container lifecycle management. Reads configuration saved by
setup.py and handles start/stop/restart/update.

Prerequisites:
    python scripts/setup.py    # Interactive first-time setup (run once)

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
import platform
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


def load_docker_config() -> dict:
    """Load and validate the Docker configuration saved by setup.py.

    Exits with a helpful message if setup hasn't been run or config is
    in the old port-only format.
    """
    state = load_state()

    if not state:
        print_error("No Docker configuration found.")
        print_info(f"Run setup first: {Colors.CYAN}python scripts/setup.py{Colors.RESET}")
        sys.exit(1)

    # Detect old-format docker.json (port only, no mounts)
    if "mounts" not in state or "download_dir" not in state:
        print_error("Docker configuration is incomplete (old format).")
        print_info(f"Run setup to configure directory mounts:")
        print(f"  {Colors.CYAN}python scripts/setup.py{Colors.RESET}")
        sys.exit(1)

    # Validate port
    port = state.get("port")
    if not port:
        print_error("No port configured.")
        print_info(f"Run setup: {Colors.CYAN}python scripts/setup.py --force{Colors.RESET}")
        sys.exit(1)

    return state


def validate_port(port: int) -> int:
    """Validate the saved port is usable, accounting for our own container.

    Returns the port if available or occupied by our container.
    Exits if the port is taken by another process.
    """
    if is_port_available(port):
        return port

    # Check if it's our own container occupying the port
    exists, running, _ = get_container_status()
    if running:
        return port

    print_error(f"Configured port {port} is in use by another process.")
    print_info("Check what's using it:")
    print(f"  {Colors.CYAN}lsof -i :{port}{Colors.RESET}  (macOS/Linux)")
    print(f"  {Colors.CYAN}netstat -ano | findstr :{port}{Colors.RESET}  (Windows)")
    print()
    print_info(f"Reconfigure: {Colors.CYAN}python scripts/setup.py --force{Colors.RESET}")
    sys.exit(1)


def build_volume_args(config: dict) -> list:
    """Build Docker -v flags from the saved configuration.

    Named volumes:
        google_drive_config  — OAuth creds, config.yaml
        google_drive_data    — SQLite log DB
        google_drive_logs    — Log files

    Bind mounts:
        download_dir  — at same host path in container (read-write)
        mounts[]      — user directories at same host path in container
    """
    args = []

    # Named volumes (unchanged)
    args += ["-v", "google_drive_config:/home/appuser/.config/google_drive"]
    args += ["-v", "google_drive_data:/home/appuser/.local/share/google_drive"]
    args += ["-v", "google_drive_logs:/home/appuser/.local/state/google_drive"]

    # Bind mount: download directory (read-write, same path in container)
    download_dir = config["download_dir"]
    docker_path = convert_path_for_docker(download_dir)
    args += ["-v", f"{docker_path}:{docker_path}:rw"]

    # Bind mounts: user-configured directories
    for mount in config.get("mounts", []):
        host_path = mount["host_path"]
        container_path = mount.get("container_path", convert_path_for_docker(host_path))
        mode = "ro" if mount.get("read_only", True) else "rw"
        args += ["-v", f"{host_path}:{container_path}:{mode}"]

    return args


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


def start_container(config: dict) -> bool:
    """Start the container using the saved configuration."""
    port = config["port"]
    print_info(f"Starting container on port {port}...")

    # Serialize config as JSON env var so the MCP server can read mount info
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

    # Add volume mounts
    cmd += build_volume_args(config)

    cmd += ["--restart", "unless-stopped", IMAGE_NAME]

    code, _, stderr = run_command(cmd)

    if code != 0:
        print_error(f"Failed to start container: {stderr}")
        return False

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


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_start():
    """Build and start the container"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Start{Colors.RESET}\n")

    # Check if already running
    exists, running, _ = get_container_status()
    if running:
        config = load_docker_config()
        port = config["port"]
        print_warning("Container already running")
        print_info(f"MCP endpoint: http://localhost:{port}/mcp")
        print_info("Use 'update' to rebuild and restart, or 'restart' to just restart")
        return

    if not check_docker_running():
        sys.exit(1)

    # Load and validate setup config
    config = load_docker_config()
    port = validate_port(config["port"])

    # Remove stopped container if exists
    if exists and not running:
        print_info("Removing stopped container...")
        run_command(["docker", "rm", CONTAINER_NAME])

    print_header("Step 1: Building Image")
    if not build_image():
        sys.exit(1)

    print_header("Step 2: Copying Credentials")
    if not copy_credentials_to_volume():
        sys.exit(1)

    print_header("Step 3: Starting Container")
    if not start_container(config):
        sys.exit(1)

    print_header("Step 4: Verifying Health")
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

    config = load_docker_config()
    validate_port(config["port"])

    stop_container()

    print_header("Starting Container")
    if not start_container(config):
        sys.exit(1)

    print_header("Verifying Health")
    verify_health(timeout_seconds=60)

    print_header("Restart Complete")
    print_success("Container restarted successfully")
    print_info(f"MCP endpoint: http://localhost:{config['port']}/mcp")
    print()


def cmd_update():
    """Rebuild image and restart container (for code changes)"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}Google Drive MCP - Update{Colors.RESET}")
    print("Rebuilds image from latest code and restarts container\n")

    if not check_docker_running():
        sys.exit(1)

    config = load_docker_config()
    validate_port(config["port"])

    exists, _, _ = get_container_status()

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
    if not start_container(config):
        sys.exit(1)

    print_header("Step 5: Verifying Health")
    verify_health(timeout_seconds=60)

    print_header("Update Complete")
    print_success("Google Drive MCP server updated with latest code!")
    print()
    print_info(f"MCP endpoint: http://localhost:{config['port']}/mcp")
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
        if "mounts" in state:
            print_info("Run 'python scripts/docker.py start' to deploy")
        else:
            print_info("Run 'python scripts/setup.py' first, then 'python scripts/docker.py start'")
    elif running:
        print_success(f"Status: {health}")
        print_info(f"Port: {port}")
        print_info(f"MCP endpoint: http://localhost:{port}/mcp")

        # Show mount info
        download_dir = state.get("download_dir")
        mounts = state.get("mounts", [])
        if download_dir:
            print()
            print_info(f"Download dir: {download_dir}")
        if mounts:
            print_info("Mounted directories:")
            for m in mounts:
                label = "read-only" if m.get("read_only", True) else "read-write"
                print(f"    {m['host_path']} ({label})")
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
  start    Build image and start container (requires setup.py first)
  stop     Stop and remove container
  restart  Restart container (without rebuild)
  update   Rebuild image and restart (use after code changes)
  status   Show container status
  logs     Tail container logs

First-time setup:
  python scripts/setup.py          # Interactive configuration
  python scripts/docker.py start   # Build and launch

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
