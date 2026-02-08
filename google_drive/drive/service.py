"""Google Drive API service layer.

Wraps the Google Drive API client with async support (via asyncio.to_thread),
error translation, and convenience methods for common operations.
"""

import asyncio
import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from google_drive.auth import build_drive_service
from google_drive.config import get_config

# Maps user-friendly type names to MIME type queries
FILE_TYPE_MAP = {
    "document": "application/vnd.google-apps.document",
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "presentation": "application/vnd.google-apps.presentation",
    "folder": "application/vnd.google-apps.folder",
    "pdf": "application/pdf",
    "image": "image/",
    "video": "video/",
    "audio": "audio/",
}

# Default export formats for Google Workspace types
EXPORT_FORMATS = {
    "application/vnd.google-apps.document": {
        "default": ("application/pdf", ".pdf"),
        "pdf": ("application/pdf", ".pdf"),
        "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
        "txt": ("text/plain", ".txt"),
        "html": ("text/html", ".html"),
        "md": ("text/plain", ".txt"),
    },
    "application/vnd.google-apps.spreadsheet": {
        "default": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
        "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
        "pdf": ("application/pdf", ".pdf"),
        "csv": ("text/csv", ".csv"),
    },
    "application/vnd.google-apps.presentation": {
        "default": ("application/pdf", ".pdf"),
        "pdf": ("application/pdf", ".pdf"),
        "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    },
    "application/vnd.google-apps.drawing": {
        "default": ("application/pdf", ".pdf"),
        "pdf": ("application/pdf", ".pdf"),
        "png": ("image/png", ".png"),
        "svg": ("image/svg+xml", ".svg"),
    },
}

UPLOAD_CHUNK_SIZE = 256 * 1024  # 256 KB chunks for resumable uploads

# Standard fields to request from files().get() and files().list()
FILE_FIELDS = (
    "id, name, mimeType, size, createdTime, modifiedTime, "
    "owners, parents, webViewLink, description, starred, trashed, "
    "shared, permissions, capabilities"
)

LIST_FILE_FIELDS = "id, name, mimeType, size, modifiedTime, parents"


def _handle_http_error(error: HttpError) -> None:
    """Translate Google API HttpError into standard Python exceptions.

    Args:
        error: The HttpError from the Google API client.

    Raises:
        FileNotFoundError: For 404 errors.
        PermissionError: For 403 errors.
        RuntimeError: For all other HTTP errors.
    """
    status = error.resp.status
    reason = error._get_reason() if hasattr(error, '_get_reason') else str(error)

    if status == 404:
        raise FileNotFoundError(f"File not found on Google Drive: {reason}")
    elif status == 403:
        raise PermissionError(f"Access denied: {reason}")
    else:
        raise RuntimeError(f"Google Drive API error ({status}): {reason}")


class DriveService:
    """Async wrapper around the Google Drive API v3 service."""

    def __init__(self):
        self._service = None

    def _get_service(self):
        """Lazily initialize the Drive API service."""
        if self._service is None:
            config = get_config()
            self._service = build_drive_service(
                config.config_dir,
                config.google_client_secret_path,
            )
        return self._service

    @staticmethod
    def is_google_native(mime_type: str) -> bool:
        """Check if a MIME type is a Google Workspace native type."""
        return mime_type.startswith("application/vnd.google-apps.")

    @staticmethod
    def get_export_mime_type(google_mime_type: str, export_format: str = "") -> Tuple[str, str]:
        """Get the export MIME type and file extension for a Google native type.

        Args:
            google_mime_type: The Google Workspace MIME type.
            export_format: Desired export format (e.g. "pdf", "docx"). Empty for default.

        Returns:
            Tuple of (export_mime_type, file_extension).

        Raises:
            ValueError: If the format is not supported for the given type.
        """
        formats = EXPORT_FORMATS.get(google_mime_type)
        if not formats:
            raise ValueError(
                f"No export formats available for MIME type: {google_mime_type}"
            )

        key = export_format.lower() if export_format else "default"
        if key not in formats:
            available = [k for k in formats if k != "default"]
            raise ValueError(
                f"Unsupported export format '{export_format}' for {google_mime_type}. "
                f"Available formats: {', '.join(available)}"
            )

        return formats[key]

    # ------------------------------------------------------------------
    # API methods (all async, use asyncio.to_thread for blocking calls)
    # ------------------------------------------------------------------

    async def search(self, query: str, max_results: int = 20, file_type: str = "") -> List[Dict[str, Any]]:
        """Search for files on Google Drive.

        Supports both natural-language-style queries (searches file names)
        and raw Drive API query strings (containing operators like 'in' or '=').

        Args:
            query: Search text or Drive API query string.
            max_results: Maximum number of results to return.
            file_type: Optional file type filter (e.g. "document", "pdf").

        Returns:
            List of file metadata dicts.
        """
        service = self._get_service()

        # Detect structured query (contains Drive API operators)
        # Use word-boundary patterns to avoid false matches (e.g. "report" matching "or")
        structured_patterns = [
            "in parents", "mimeType", "=",
            r"\bcontains\b", r"\band\b", r"\bor\b",
        ]
        is_structured = any(
            p in query if " " in p or "=" in p else re.search(p, query)
            for p in structured_patterns
        )

        if is_structured:
            q = query
        else:
            q = f"name contains '{query}' and trashed=false"

        # Add file type filter
        if file_type:
            mime = FILE_TYPE_MAP.get(file_type.lower())
            if mime:
                if mime.endswith("/"):
                    q += f" and mimeType contains '{mime}'"
                else:
                    q += f" and mimeType='{mime}'"

        try:
            result = await asyncio.to_thread(
                service.files()
                .list(
                    q=q,
                    pageSize=min(max_results, 100),
                    fields=f"files({LIST_FILE_FIELDS})",
                    orderBy="modifiedTime desc",
                )
                .execute
            )
            return result.get("files", [])
        except HttpError as e:
            _handle_http_error(e)

    async def list_children(self, folder_id: str = "root", max_results: int = 50) -> List[Dict[str, Any]]:
        """List immediate children of a folder.

        Args:
            folder_id: The folder ID (default "root" for My Drive root).
            max_results: Maximum number of results.

        Returns:
            List of file metadata dicts, folders sorted first.
        """
        service = self._get_service()
        q = f"'{folder_id}' in parents and trashed=false"

        try:
            result = await asyncio.to_thread(
                service.files()
                .list(
                    q=q,
                    pageSize=min(max_results, 100),
                    fields=f"files({LIST_FILE_FIELDS})",
                    orderBy="folder,name",
                )
                .execute
            )
            return result.get("files", [])
        except HttpError as e:
            _handle_http_error(e)

    async def get_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get detailed metadata for a file.

        Args:
            file_id: The Google Drive file ID.

        Returns:
            File metadata dict.
        """
        service = self._get_service()

        try:
            return await asyncio.to_thread(
                service.files()
                .get(fileId=file_id, fields=FILE_FIELDS)
                .execute
            )
        except HttpError as e:
            _handle_http_error(e)

    async def download(self, file_id: str, dest_path: str | Path, export_format: str = "") -> Tuple[str, int]:
        """Download a file from Google Drive to the local filesystem.

        For Google Workspace files (Docs, Sheets, etc.), exports to the
        requested format. For regular files, downloads the binary content.

        Args:
            file_id: The Google Drive file ID.
            dest_path: Local destination path (file or directory).
            export_format: Export format for Google native files (e.g. "pdf", "docx").

        Returns:
            Tuple of (final_path, bytes_written).
        """
        service = self._get_service()

        # Get file metadata first
        try:
            metadata = await asyncio.to_thread(
                service.files()
                .get(fileId=file_id, fields="id, name, mimeType, size")
                .execute
            )
        except HttpError as e:
            _handle_http_error(e)

        mime_type = metadata["mimeType"]
        file_name = metadata["name"]

        dest_path = Path(dest_path)

        if self.is_google_native(mime_type):
            export_mime, ext = self.get_export_mime_type(mime_type, export_format)

            # Ensure filename has correct extension
            if dest_path.is_dir() or not dest_path.suffix:
                target_dir = dest_path if dest_path.is_dir() else dest_path.parent
                target_dir.mkdir(parents=True, exist_ok=True)
                dest_path = target_dir / f"{Path(file_name).stem}{ext}"

            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            if dest_path.is_dir():
                dest_path = dest_path / file_name
            else:
                dest_path.parent.mkdir(parents=True, exist_ok=True)

            request = service.files().get_media(fileId=file_id)

        # Stream download to disk
        def _download():
            fh = io.FileIO(str(dest_path), "wb")
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.close()
            return os.path.getsize(str(dest_path))

        try:
            bytes_written = await asyncio.to_thread(_download)
        except HttpError as e:
            _handle_http_error(e)

        return str(dest_path), bytes_written

    async def upload(self, local_path: str | Path, folder_id: str = "root", file_name: str = "") -> Dict[str, Any]:
        """Upload a local file to Google Drive.

        Args:
            local_path: Path to the local file.
            folder_id: Parent folder ID on Drive (default "root").
            file_name: Override name for the uploaded file.

        Returns:
            Metadata dict of the created file.
        """
        service = self._get_service()
        local_path = Path(local_path)

        name = file_name if file_name else local_path.name

        file_metadata = {"name": name, "parents": [folder_id]}
        media = MediaFileUpload(
            str(local_path),
            resumable=True,
            chunksize=UPLOAD_CHUNK_SIZE,
        )

        try:
            result = await asyncio.to_thread(
                service.files()
                .create(body=file_metadata, media_body=media, fields="id, name, mimeType, size, webViewLink")
                .execute
            )
            return result
        except HttpError as e:
            _handle_http_error(e)

    async def create_folder(self, name: str, parent_id: str = "root") -> Dict[str, Any]:
        """Create a folder on Google Drive.

        Args:
            name: Folder name.
            parent_id: Parent folder ID (default "root").

        Returns:
            Metadata dict of the created folder.
        """
        service = self._get_service()

        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }

        try:
            result = await asyncio.to_thread(
                service.files()
                .create(body=file_metadata, fields="id, name, mimeType, webViewLink")
                .execute
            )
            return result
        except HttpError as e:
            _handle_http_error(e)


# Singleton instance
_drive_service = None


def get_drive_service() -> DriveService:
    """Get the global DriveService singleton."""
    global _drive_service
    if _drive_service is None:
        _drive_service = DriveService()
    return _drive_service
