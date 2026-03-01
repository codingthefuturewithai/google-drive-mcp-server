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
                        f"Path '{file_path}' is in a read-only mount.",
                        "",
                        "Requirement: The path must be within a read-write mount.",
                        "",
                        "Read-write mount:",
                        f"  - {download_dir} (read-write)",
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
        lines.append("No directories are mounted. No file operations can succeed until at least one directory is mounted.")
    else:
        lines.append("")
        lines.append("Requirement: local_path must exist within one of the mounted directories listed above.")

    return False, "\n".join(lines)


def _validate_directory_exists(dir_path: Path, is_default_download_dir: bool = False) -> None:
    """Validate that a directory exists and is accessible.

    Raises FileNotFoundError with a helpful message if the directory doesn't exist.

    Args:
        dir_path: Directory path to validate
        is_default_download_dir: If True, includes setup instructions in error message
    """
    if not dir_path.exists():
        lines = [
            f"Directory does not exist: {dir_path}",
            "",
        ]

        if is_default_download_dir:
            in_docker = bool(os.environ.get("GOOGLE_DRIVE_DOCKER"))
            if in_docker:
                lines.extend([
                    "This is the configured download directory for the Docker container.",
                    "The directory must exist on the host system before the container can write to it.",
                    "Create the directory on the host and restart the container.",
                ])
            else:
                lines.extend([
                    "This is the configured download directory.",
                    "The directory must exist before files can be downloaded.",
                ])
        else:
            lines.extend([
                "The specified path must be an existing directory.",
            ])

        raise FileNotFoundError("\n".join(lines))

    if not dir_path.is_dir():
        raise FileNotFoundError(
            f"Path exists but is not a directory: {dir_path}\n"
            f"Please specify a directory path, not a file."
        )


def _resolve_download_path(local_path: str, filename: str) -> Path:
    """Resolve the download destination path.

    When local_path is empty, uses the platform-aware download directory
    from config. Otherwise resolves the user-provided path.

    Args:
        local_path: User-provided path (may be empty, a directory, or a file path).
        filename: Original filename from Google Drive.

    Returns:
        Resolved Path for the download destination.

    Raises:
        FileNotFoundError: If the target directory doesn't exist (with helpful message)
    """
    if not local_path:
        config = get_config()
        download_dir = config.download_dir

        # Validate the default download directory exists
        _validate_directory_exists(download_dir, is_default_download_dir=True)

        return download_dir / filename

    path = Path(local_path)

    # If user specified a directory, validate it exists
    if path.is_dir():
        return path / filename

    # If it's a file path, validate the parent directory exists
    parent_dir = path.parent
    if not parent_dir.exists():
        # Try to create it, but catch the error and provide helpful message
        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            # Get helpful mount info (Docker) or empty string (non-Docker)
            _, helpful_msg = _check_path_accessible(str(path), need_write=True)
            if helpful_msg:
                # Docker mode: raise PermissionError (not FileNotFoundError) so download_file's
                # recovery block also runs, and the agent sees the full list of valid mounted directories
                raise PermissionError(helpful_msg) from e
            # Non-Docker mode: any writable path is valid — this is a genuine OS permissions error
            raise PermissionError(
                f"Cannot write to: {parent_dir}\n"
                f"Error: {e}\n\n"
                f"Choose a directory where you have write access and retry."
            ) from e

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

    try:
        dest = _resolve_download_path(local_path, filename)

        # Validate the download destination is in a writable mount (Docker only)
        accessible, msg = _check_path_accessible(str(dest), need_write=True)
        if not accessible:
            raise PermissionError(msg)

        final_path, bytes_written = await drive.download(file_id, dest, export_format=export_format)

    except PermissionError as e:
        # If this is already our detailed error message, re-raise as-is
        error_msg = str(e)
        if "Mounted directories:" in error_msg or "read-only mount" in error_msg:
            raise

        # Generate helpful error message with mount information
        # Use the destination path if it was successfully resolved, otherwise construct it
        if "dest" in locals():
            check_path = str(dest)
        else:
            # dest wasn't created yet, construct what it would have been
            check_path = local_path if local_path else str(get_config().download_dir / filename)

        _, helpful_msg = _check_path_accessible(check_path, need_write=True)
        if helpful_msg:
            raise PermissionError(helpful_msg) from e
        else:
            # Path passed validation but still got PermissionError - re-raise original
            raise

    return (
        f"Downloaded '{filename}' to {final_path}\n"
        f"Size: {_format_size(bytes_written)}"
    )


async def create_file(local_path: str, folder_id: str = "root", file_name: str = "", ctx: Context = None) -> str:
    """Create a new file on Google Drive by uploading a local file.

    This always creates a new file. To replace the content of an existing file, use update_file instead.

    In Docker mode, local_path must be within a directory mounted into the server container.

    Before calling this tool, ask the user where to save the file. Use list_folder to show
    available top-level folders, then confirm the destination before uploading. Only use
    folder_id="root" if the user explicitly says to save it to My Drive root.

    Args:
        local_path: Path to the local file to upload. In Docker mode, must be within a mounted directory.
        folder_id: Destination folder ID on Drive. Ask the user where to save the file
            and use list_folder to discover available folders before calling. Use "root"
            only if the user explicitly confirms they want the file in My Drive root.
        file_name: Override name for the uploaded file (default uses local filename)
        ctx: MCP context

    Returns:
        Confirmation with the created file's Drive ID and link
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
        f"Created '{name}' on Google Drive.",
        f"File ID: {drive_id}",
        f"Size: {_format_size(file_size)}",
    ]
    if link:
        lines.append(f"Link: {link}")

    return "\n".join(lines)


async def update_file(file_id: str, local_path: str, new_name: str = "", ctx: Context = None) -> str:
    """Replace the content of an existing file on Google Drive.

    Updates the file in place — no duplicate is created. Optionally renames the file.

    In Docker mode, local_path must be within a directory mounted into the server container.

    Args:
        file_id: Google Drive file ID of the existing file to update
        local_path: Path to the local file with new content. In Docker mode, must be within a mounted directory.
        new_name: Optional new name for the file on Drive
        ctx: MCP context

    Returns:
        Confirmation with the updated file's Drive ID and link
    """
    path = Path(local_path)

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
    result = await drive.update(file_id, path, new_name=new_name)

    name = result.get("name", path.name)
    drive_id = result.get("id", "unknown")
    link = result.get("webViewLink", "")

    lines = [
        f"Updated '{name}' on Google Drive.",
        f"File ID: {drive_id}",
        f"Size: {_format_size(file_size)}",
    ]
    if link:
        lines.append(f"Link: {link}")

    return "\n".join(lines)


transfer_tools = [download_file, create_file, update_file]
