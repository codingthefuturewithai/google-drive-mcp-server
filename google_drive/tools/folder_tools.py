"""Google Drive folder management tools.

Tools for creating and organizing folders on Google Drive.
"""

from mcp.server.fastmcp import Context

from google_drive.drive import get_drive_service


async def create_folder(folder_name: str, parent_folder_id: str = "root", account_email: str = "", ctx: Context = None) -> str:
    """Create a new folder on Google Drive.

    Before calling this tool, ask the user where to create the folder. Use list_folder to
    show available locations, then confirm the destination. Only use parent_folder_id="root"
    if the user explicitly says to create it in My Drive root.

    Args:
        folder_name: Name for the new folder
        parent_folder_id: Parent folder ID. Ask the user where to create the folder
            and use list_folder to discover available locations before calling. Use "root"
            only if the user explicitly confirms they want it in My Drive root.
        account_email: Google account to use. Leave empty to use the default account.
        ctx: MCP context

    Returns:
        Confirmation with the new folder's Drive ID and link
    """
    drive = get_drive_service(account_email)
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
