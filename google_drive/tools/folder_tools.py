"""Google Drive folder management tools.

Tools for creating and organizing folders on Google Drive.
"""

from mcp.server.fastmcp import Context

from google_drive.drive import get_drive_service


async def create_folder(folder_name: str, parent_folder_id: str = "root", ctx: Context = None) -> str:
    """Create a new folder on Google Drive.

    Args:
        folder_name: Name for the new folder
        parent_folder_id: Parent folder ID (default "root" for My Drive root)
        ctx: MCP context

    Returns:
        Confirmation with the new folder's Drive ID and link
    """
    drive = get_drive_service()
    result = await drive.create_folder(folder_name, parent_id=parent_folder_id)

    folder_id = result.get("id", "unknown")
    link = result.get("webViewLink", "")

    lines = [
        f"Created folder '{folder_name}'.",
        f"Folder ID: {folder_id}",
    ]
    if link:
        lines.append(f"Link: {link}")

    return "\n".join(lines)


folder_tools = [create_folder]
