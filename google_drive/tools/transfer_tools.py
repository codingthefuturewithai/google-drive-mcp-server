"""Google Drive file transfer tools.

Tools for downloading files from and uploading files to Google Drive.
"""

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
