"""Google Drive file metadata tools.

Tools for inspecting file details on Google Drive.
"""

from mcp.server.fastmcp import Context

from google_drive.drive import get_drive_service
from google_drive.drive.service import DriveService


def _format_size(num_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


async def get_file_info(file_id: str, ctx: Context = None) -> str:
    """Get detailed information about a file on Google Drive.

    Returns comprehensive metadata including name, type, size, dates,
    owner, sharing status, and link.

    Args:
        file_id: Google Drive file ID
        ctx: MCP context

    Returns:
        Formatted file metadata
    """
    drive = get_drive_service()
    meta = await drive.get_metadata(file_id)

    name = meta.get("name", "Unknown")
    mime = meta.get("mimeType", "Unknown")
    is_native = DriveService.is_google_native(mime)

    lines = [
        f"File: {name}",
        f"ID: {meta.get('id', 'Unknown')}",
        f"Type: {mime}",
    ]

    size = meta.get("size")
    if size:
        lines.append(f"Size: {_format_size(int(size))}")
    elif is_native:
        lines.append("Size: N/A (Google Workspace file)")

    created = meta.get("createdTime", "")
    if created:
        lines.append(f"Created: {created[:19].replace('T', ' ')}")

    modified = meta.get("modifiedTime", "")
    if modified:
        lines.append(f"Modified: {modified[:19].replace('T', ' ')}")

    owners = meta.get("owners", [])
    if owners:
        owner_names = ", ".join(o.get("displayName", o.get("emailAddress", "Unknown")) for o in owners)
        lines.append(f"Owner: {owner_names}")

    description = meta.get("description")
    if description:
        lines.append(f"Description: {description}")

    # Resolve parent folder path
    parents = meta.get("parents", [])
    if parents:
        path_parts = []
        current_parent_id = parents[0]  # Files have one parent in My Drive
        try:
            while current_parent_id:
                parent_meta = await drive.get_metadata(current_parent_id)
                parent_name = parent_meta.get("name", "")
                # "My Drive" is the root — stop here but include it
                path_parts.insert(0, parent_name)
                grandparents = parent_meta.get("parents", [])
                if not grandparents or parent_name == "My Drive":
                    break
                current_parent_id = grandparents[0]
        except Exception:
            pass  # If resolution fails, omit the path rather than crashing

        if path_parts:
            lines.append(f"Folder: {' > '.join(path_parts)}")
            lines.append(f"Folder ID: {parents[0]}")  # The immediate parent ID for use in create_file

    lines.append(f"Starred: {'Yes' if meta.get('starred') else 'No'}")
    lines.append(f"Shared: {'Yes' if meta.get('shared') else 'No'}")

    link = meta.get("webViewLink")
    if link:
        lines.append(f"Link: {link}")

    if is_native:
        from google_drive.drive.service import EXPORT_FORMATS
        formats = EXPORT_FORMATS.get(mime, {})
        available = [k for k in formats if k != "default"]
        if available:
            lines.append(f"Export formats: {', '.join(available)}")

    return "\n".join(lines)


metadata_tools = [get_file_info]
