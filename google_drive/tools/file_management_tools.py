"""Google Drive file management tools.

Tools for organizing files: moving and deleting.
"""

from mcp.server.fastmcp import Context

from google_drive.drive import get_drive_service


async def delete_file(file_id: str, permanent: bool = False, account_email: str = "", ctx: Context = None) -> str:
    """Delete a file or folder from Google Drive.

    By default, moves the file to trash (recoverable). Set permanent=True to
    permanently delete without recovery option.

    IMPORTANT: Deleting a folder deletes all its contents recursively.

    Args:
        file_id: Google Drive file ID to delete
        permanent: If True, permanently delete. If False, move to trash (default)
        account_email: Google account to use. Leave empty to use the default account.
        ctx: MCP context

    Returns:
        Confirmation message with file name and deletion type
    """
    drive = get_drive_service(account_email)

    # Get file info first to provide helpful confirmation message
    try:
        metadata = await drive.get_metadata(file_id)
    except FileNotFoundError:
        # File doesn't exist - this is idempotent (already deleted is success)
        return (
            f"File {file_id} does not exist (may have already been deleted).\n\n"
            f"This is a success case - the file is not present on Drive."
        )

    name = metadata.get("name", "Unknown")
    mime = metadata.get("mimeType", "")
    is_folder = mime == "application/vnd.google-apps.folder"
    file_type = "folder" if is_folder else "file"

    # Perform the deletion
    await drive.delete(file_id, permanent=permanent)

    if permanent:
        warning = "\n⚠️  This folder and all its contents were permanently deleted." if is_folder else ""
        return (
            f"Permanently deleted {file_type}: {name}\n"
            f"ID: {file_id}{warning}\n\n"
            f"This action cannot be undone."
        )
    else:
        restore_hint = "\n\nTo restore, find it in your Drive trash." if not is_folder else "\n\nTo restore this folder and its contents, find it in your Drive trash."
        return (
            f"Moved {file_type} to trash: {name}\n"
            f"ID: {file_id}{restore_hint}\n\n"
            f"To permanently delete, call delete_file with permanent=True."
        )


async def move_file(file_id: str, new_parent_folder_id: str, account_email: str = "", ctx: Context = None) -> str:
    """Move a file or folder to a different parent folder.

    Changes the parent folder while preserving all file metadata, sharing settings,
    edit history, and comments. Works for both regular files and Google Workspace files
    (Docs, Sheets, Slides) without re-uploading or converting formats.

    Args:
        file_id: Google Drive file ID to move
        new_parent_folder_id: Destination folder ID (use "root" for My Drive root)
        account_email: Google account to use. Leave empty to use the default account.
        ctx: MCP context

    Returns:
        Confirmation with file name, old location, and new location
    """
    drive = get_drive_service(account_email)

    # Validate file exists and get current location
    try:
        file_meta = await drive.get_metadata(file_id)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"File not found: {file_id}\n\n"
            f"The file may have been deleted or you may not have access to it."
        )

    file_name = file_meta.get("name", "Unknown")
    current_parents = file_meta.get("parents", [])

    # Check if already in destination folder (idempotent)
    if new_parent_folder_id in current_parents:
        return (
            f"File '{file_name}' is already in the destination folder.\n"
            f"File ID: {file_id}\n"
            f"Folder ID: {new_parent_folder_id}\n\n"
            f"No move needed - this is a success case."
        )

    # Validate destination folder exists and is actually a folder
    if new_parent_folder_id != "root":
        try:
            folder_meta = await drive.get_metadata(new_parent_folder_id)
            folder_mime = folder_meta.get("mimeType", "")

            if folder_mime != "application/vnd.google-apps.folder":
                folder_name = folder_meta.get("name", "Unknown")
                raise ValueError(
                    f"Destination is not a folder: {new_parent_folder_id}\n"
                    f"Name: {folder_name}\n"
                    f"Type: {folder_mime}\n\n"
                    f"Requirement: new_parent_folder_id must be a folder ID, not a file ID."
                )

        except FileNotFoundError:
            raise FileNotFoundError(
                f"Destination folder not found: {new_parent_folder_id}\n\n"
                f"The folder may have been deleted or you may not have access to it."
            )

    # Get destination folder name for confirmation message
    if new_parent_folder_id == "root":
        dest_folder_name = "My Drive (root)"
    else:
        folder_meta = await drive.get_metadata(new_parent_folder_id)
        dest_folder_name = folder_meta.get("name", "Unknown")

    # Perform the move
    result = await drive.move(file_id, new_parent_folder_id)

    # Build confirmation with path information if available
    lines = [
        f"Moved '{file_name}' to {dest_folder_name}",
        f"File ID: {file_id}",
        f"New parent folder ID: {new_parent_folder_id}",
    ]

    return "\n".join(lines)


file_management_tools = [delete_file, move_file]
