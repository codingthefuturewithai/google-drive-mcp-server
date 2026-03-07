"""Google Drive search and browse tools.

Tools for searching files and listing folder contents on Google Drive.
"""

from mcp.server.fastmcp import Context

from google_drive.drive import get_drive_service


def _format_file_row(f: dict) -> str:
    """Format a single file metadata dict into a display line."""
    mime = f.get("mimeType", "")
    is_folder = mime == "application/vnd.google-apps.folder"
    icon = "[Folder]" if is_folder else "[File]"
    size = f.get("size")
    size_str = f"  ({_format_size(int(size))})" if size else ""
    modified = f.get("modifiedTime", "")[:10]
    return f"  {icon} {f['name']}{size_str}  |  {modified}  |  id:{f['id']}"


def _format_size(num_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


async def search_files(query: str, max_results: int = 20, file_type: str = "", account_email: str = "", ctx: Context = None) -> str:
    """Search for files on Google Drive.

    Finds files matching a search query. Supports natural language searches
    (searches by file name) and structured Drive API queries.

    Args:
        query: Search text or Drive API query string. The query parameter searches by
               file name or content — it cannot be empty. To browse all folders without
               a specific name to search for, use list_folder instead.
        max_results: Maximum results to return (default 20, max 100)
        file_type: Filter by type: document, spreadsheet, presentation, folder, pdf, image, video, audio.
                   Note: file_type alone doesn't return all items of that type — you must also provide
                   a query to search for.
        account_email: Google account to use. Leave empty to use the default account.
        ctx: MCP context

    Returns:
        Formatted search results with file names, sizes, dates, and IDs
    """
    drive = get_drive_service(account_email)
    max_results = max(1, min(max_results, 100))

    files = await drive.search(query, max_results=max_results, file_type=file_type)

    if not files:
        return f"No files found matching '{query}'."

    lines = [f"Found {len(files)} file(s) matching '{query}':"]
    for f in files:
        lines.append(_format_file_row(f))

    return "\n".join(lines)


async def list_folder(folder_id: str = "root", max_results: int = 50, account_email: str = "", ctx: Context = None) -> str:
    """List contents of a Google Drive folder.

    Use this to discover what folders and files exist in a location. Shows immediate
    children with folders listed first. Call with folder_id='root' to browse the top
    level of My Drive — this is the recommended way to discover available folders.

    Args:
        folder_id: Folder ID to list (default "root" for My Drive root)
        max_results: Maximum results to return (default 50, max 100)
        account_email: Google account to use. Leave empty to use the default account.
        ctx: MCP context

    Returns:
        Formatted list of folder contents with names, sizes, dates, and IDs
    """
    drive = get_drive_service(account_email)
    max_results = max(1, min(max_results, 100))

    files = await drive.list_children(folder_id, max_results=max_results)

    if not files:
        label = "My Drive root" if folder_id == "root" else f"folder {folder_id}"
        return f"No files found in {label}."

    folders = [f for f in files if f.get("mimeType") == "application/vnd.google-apps.folder"]
    regular = [f for f in files if f.get("mimeType") != "application/vnd.google-apps.folder"]

    label = "My Drive root" if folder_id == "root" else f"folder {folder_id}"
    lines = [f"Contents of {label} ({len(files)} items):"]

    if folders:
        lines.append(f"\nFolders ({len(folders)}):")
        for f in folders:
            lines.append(_format_file_row(f))
    if regular:
        lines.append(f"\nFiles ({len(regular)}):")
        for f in regular:
            lines.append(_format_file_row(f))

    return "\n".join(lines)


search_tools = [search_files, list_folder]
