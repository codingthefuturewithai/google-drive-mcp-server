"""Tests for metadata tools."""

import pytest
from unittest.mock import patch, AsyncMock

from google_drive.tools.metadata_tools import get_file_info


@pytest.fixture
def mock_drive():
    with patch("google_drive.tools.metadata_tools.get_drive_service") as mock_get:
        mock_svc = AsyncMock()
        mock_get.return_value = mock_svc
        yield mock_svc


class TestGetFileInfo:
    """Test get_file_info tool."""

    @pytest.mark.asyncio
    async def test_regular_file_info(self, mock_drive):
        mock_drive.get_metadata.return_value = {
            "id": "abc123",
            "name": "report.pdf",
            "mimeType": "application/pdf",
            "size": "1048576",
            "createdTime": "2024-01-15T10:30:00.000Z",
            "modifiedTime": "2024-02-20T14:45:00.000Z",
            "owners": [{"displayName": "Alice", "emailAddress": "alice@example.com"}],
            "starred": False,
            "shared": True,
            "webViewLink": "https://drive.google.com/file/abc123/view",
        }

        result = await get_file_info("abc123")

        assert "report.pdf" in result
        assert "abc123" in result
        assert "application/pdf" in result
        assert "1.0 MB" in result
        assert "2024-01-15 10:30:00" in result
        assert "Alice" in result
        assert "Starred: No" in result
        assert "Shared: Yes" in result
        assert "https://drive.google.com" in result

    @pytest.mark.asyncio
    async def test_google_native_no_size(self, mock_drive):
        mock_drive.get_metadata.return_value = {
            "id": "doc456",
            "name": "My Document",
            "mimeType": "application/vnd.google-apps.document",
            "createdTime": "2024-01-01T00:00:00.000Z",
            "modifiedTime": "2024-01-02T00:00:00.000Z",
            "owners": [{"displayName": "Bob"}],
            "starred": True,
            "shared": False,
        }

        result = await get_file_info("doc456")

        assert "N/A (Google Workspace file)" in result
        assert "Export formats:" in result
        assert "pdf" in result
        assert "docx" in result

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_drive):
        mock_drive.get_metadata.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            await get_file_info("nonexistent")

    @pytest.mark.asyncio
    async def test_file_with_description(self, mock_drive):
        mock_drive.get_metadata.return_value = {
            "id": "d1",
            "name": "notes.txt",
            "mimeType": "text/plain",
            "size": "256",
            "description": "My important notes",
            "starred": False,
            "shared": False,
        }

        result = await get_file_info("d1")
        assert "Description: My important notes" in result
