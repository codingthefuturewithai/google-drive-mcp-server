"""Google Drive file transfer tools.

Tools for downloading files from and uploading files to Google Drive.
"""

import json
import os
from pathlib import Path

from mcp.server.fastmcp import Context

from google_drive.config import get_config
from google_drive.drive import get_drive_service


def _format_size(num_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def _get_docker_mounts() -> dict:
    """Load mount configuration from the GOOGLE_DRIVE_MOUNTS env var.

    Returns empty dict when not running in Docker (GOOGLE_DRIVE_DOCKER unset),
    meaning no mount restrictions apply.
    """
    if not os.environ.get("GOOGLE_DRIVE_DOCKER"):
        return {}
    mounts_json = os.environ.get("GOOGLE_DRIVE_MOUNTS", "")
    if not mounts_json:
        return {}
    try:
        return json.loads(mounts_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def _check_path_accessible(file_path: str, need_write: bool = False) -> tuple:
    """Check if a path is within a Docker-mounted directory.

    Only enforced when GOOGLE_DRIVE_DOCKER=1 (container mode).
    When running locally (stdio, MCP Inspector, etc.), always returns (True, "").

    Args:
        file_path: Absolute path to check.
        need_write: If True, also verifies the mount is read-write.

    Returns:
        (is_accessible, message) — message explains the problem on failure.
    """
    mounts_config = _get_docker_mounts()
    if not mounts_config:
        # Not in Docker or no mount info — no restrictions
        return True, ""

    resolved = str(Path(file_path).resolve())

    # Collect all accessible directories with their permissions
    accessible_dirs = []

    # Download dir is always read-write
    download_dir = mounts_config.get("download_dir", "")
    if download_dir:
        accessible_dirs.append({"path": download_dir, "read_only": False})
        if resolved.startswith(download_dir + "/") or resolved == download_dir:
            return True, ""

    # User-configured mounts
    for mount in mounts_config.get("mounts", []):
        host_path = mount.get("host_path", "")
        read_only = mount.get("read_only", True)
        if host_path:
            accessible_dirs.append({"path": host_path, "read_only": read_only})
            if resolved.startswith(host_path + "/") or resolved == host_path:
                if need_write and read_only:
                    lines = [
                        f"Path '{file_path}' is in a read-only mount ({host_path}).",
                        "",
                        "To write to this directory, reconfigure with a read-write mount:",
                        "  python scripts/setup.py --force",
                        "",
                        f"Or use the download directory instead: {download_dir}",
                    ]
                    return False, "\n".join(lines)
                return True, ""

    # Path is outside all mounted directories
    lines = [
        f"Path '{file_path}' is not accessible from the Docker container.",
        "",
        "Mounted directories:",
    ]
    for d in accessible_dirs:
        label = "read-only" if d["read_only"] else "read-write"
        lines.append(f"  - {d['path']} ({label})")

    if not accessible_dirs:
        lines.append("  (none configured)")

    lines.append("")
    lines.append("Move the file to one of these directories and try again.")
    lines.append("Or run 'python scripts/setup.py --force' to add more directories.")

    return False, "\n".join(lines)


def _resolve_download_path(local_path: str, filename: str) -> Path:
    """Resolve the download destination path.

    When local_path is empty, uses the platform-aware download directory
    from config. Otherwise resolves the user-provided path.

    Args:
        local_path: User-provided path (may be empty, a directory, or a file path).
        filename: Original filename from Google Drive.

    Returns:
        Resolved Path for the download destination.
    """
    if not local_path:
        config = get_config()
        return config.download_dir / filename

    path = Path(local_path)
    if path.is_dir():
        return path / filename
    # If it's a file path, ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def download_file(file_id: str, local_path: str = "", export_format: str = "", ctx: Context = None) -> str:
    """Download a file from Google Drive to the local filesystem.

    For Google Workspace files (Docs, Sheets, Slides), exports to the specified
    format. For regular files, downloads the binary content directly.

    Args:
        file_id: Google Drive file ID to download
        local_path: Local destination path (file or directory). If empty, uses default download directory
        export_format: Export format for Google Workspace files (pdf, docx, xlsx, csv, pptx, txt, html)
        ctx: MCP context

    Returns:
        Confirmation with the local file path and size
    """
    drive = get_drive_service()

    # Get metadata to determine filename and type
    metadata = await drive.get_metadata(file_id)
    filename = metadata["name"]

    dest = _resolve_download_path(local_path, filename)

    # Validate the download destination is in a writable mount (Docker only)
    accessible, msg = _check_path_accessible(str(dest), need_write=True)
    if not accessible:
        raise PermissionError(msg)

    final_path, bytes_written = await drive.download(file_id, dest, export_format=export_format)

    return (
        f"Downloaded '{filename}' to {final_path}\n"
        f"Size: {_format_size(bytes_written)}"
    )


async def upload_file(local_path: str, folder_id: str = "root", file_name: str = "", ctx: Context = None) -> str:
    """Upload a local file to Google Drive.

    Args:
        local_path: Path to the local file to upload
        folder_id: Destination folder ID on Drive (default "root" for My Drive root)
        file_name: Override name for the uploaded file (default uses local filename)
        ctx: MCP context

    Returns:
        Confirmation with the uploaded file's Drive ID and link
    """
    path = Path(local_path)

    # Validate the upload source is in a mounted directory (Docker only)
    accessible, msg = _check_path_accessible(local_path, need_write=False)
    if not accessible:
        raise PermissionError(msg)

    if not path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")
    if path.is_dir():
        raise ValueError(f"Cannot upload a directory: {local_path}. Specify a file path.")

    config = get_config()
    file_size = path.stat().st_size
    max_bytes = config.max_upload_size_mb * 1024 * 1024

    if file_size > max_bytes:
        raise ValueError(
            f"File size ({_format_size(file_size)}) exceeds the "
            f"{config.max_upload_size_mb} MB upload limit."
        )

    drive = get_drive_service()
    result = await drive.upload(path, folder_id=folder_id, file_name=file_name)

    name = result.get("name", path.name)
    drive_id = result.get("id", "unknown")
    link = result.get("webViewLink", "")

    lines = [
        f"Uploaded '{name}' to Google Drive.",
        f"File ID: {drive_id}",
        f"Size: {_format_size(file_size)}",
    ]
    if link:
        lines.append(f"Link: {link}")

    return "\n".join(lines)


transfer_tools = [download_file, upload_file]
