"""Tests for search tools."""

import pytest
from unittest.mock import patch, AsyncMock

from google_drive.tools.search_tools import search_files, list_folder


@pytest.fixture
def mock_drive():
    with patch("google_drive.tools.search_tools.get_drive_service") as mock_get:
        mock_svc = AsyncMock()
        mock_get.return_value = mock_svc
        yield mock_svc


class TestSearchFiles:
    """Test search_files tool."""

    @pytest.mark.asyncio
    async def test_returns_formatted_results(self, mock_drive):
        mock_drive.search.return_value = [
            {"id": "1", "name": "Report.pdf", "mimeType": "application/pdf",
             "size": "1048576", "modifiedTime": "2024-01-15T10:00:00Z"},
            {"id": "2", "name": "Notes", "mimeType": "application/vnd.google-apps.document",
             "modifiedTime": "2024-01-10T08:00:00Z"},
        ]

        result = await search_files("report")

        assert "Found 2 file(s)" in result
        assert "Report.pdf" in result
        assert "Notes" in result
        assert "id:1" in result
        assert "id:2" in result

    @pytest.mark.asyncio
    async def test_no_results_message(self, mock_drive):
        mock_drive.search.return_value = []

        result = await search_files("nonexistent")
        assert "No files found" in result

    @pytest.mark.asyncio
    async def test_max_results_clamped(self, mock_drive):
        mock_drive.search.return_value = []

        await search_files("test", max_results=999)
        mock_drive.search.assert_called_once_with("test", max_results=100, file_type="")

    @pytest.mark.asyncio
    async def test_max_results_min_one(self, mock_drive):
        mock_drive.search.return_value = []

        await search_files("test", max_results=0)
        mock_drive.search.assert_called_once_with("test", max_results=1, file_type="")

    @pytest.mark.asyncio
    async def test_file_type_passed_through(self, mock_drive):
        mock_drive.search.return_value = []

        await search_files("test", file_type="pdf")
        mock_drive.search.assert_called_once_with("test", max_results=20, file_type="pdf")

    @pytest.mark.asyncio
    async def test_folder_shown_with_icon(self, mock_drive):
        mock_drive.search.return_value = [
            {"id": "f1", "name": "My Folder", "mimeType": "application/vnd.google-apps.folder",
             "modifiedTime": "2024-01-01T00:00:00Z"},
        ]

        result = await search_files("folder")
        assert "[Folder]" in result


class TestListFolder:
    """Test list_folder tool."""

    @pytest.mark.asyncio
    async def test_lists_root_contents(self, mock_drive):
        mock_drive.list_children.return_value = [
            {"id": "f1", "name": "Documents", "mimeType": "application/vnd.google-apps.folder",
             "modifiedTime": "2024-01-01T00:00:00Z"},
            {"id": "f2", "name": "photo.jpg", "mimeType": "image/jpeg",
             "size": "2048000", "modifiedTime": "2024-02-01T00:00:00Z"},
        ]

        result = await list_folder()

        assert "My Drive root" in result
        assert "2 items" in result
        assert "Folders (1):" in result
        assert "Files (1):" in result
        assert "Documents" in result
        assert "photo.jpg" in result

    @pytest.mark.asyncio
    async def test_empty_folder_message(self, mock_drive):
        mock_drive.list_children.return_value = []

        result = await list_folder("abc123")
        assert "No files found in folder abc123" in result

    @pytest.mark.asyncio
    async def test_max_results_clamped(self, mock_drive):
        mock_drive.list_children.return_value = []

        await list_folder(max_results=200)
        mock_drive.list_children.assert_called_once_with("root", max_results=100)

    @pytest.mark.asyncio
    async def test_folders_sorted_first(self, mock_drive):
        mock_drive.list_children.return_value = [
            {"id": "1", "name": "Folder A", "mimeType": "application/vnd.google-apps.folder",
             "modifiedTime": "2024-01-01T00:00:00Z"},
            {"id": "2", "name": "file.txt", "mimeType": "text/plain",
             "size": "100", "modifiedTime": "2024-01-01T00:00:00Z"},
            {"id": "3", "name": "Folder B", "mimeType": "application/vnd.google-apps.folder",
             "modifiedTime": "2024-01-01T00:00:00Z"},
        ]

        result = await list_folder()
        folders_idx = result.index("Folders (2):")
        files_idx = result.index("Files (1):")
        assert folders_idx < files_idx
