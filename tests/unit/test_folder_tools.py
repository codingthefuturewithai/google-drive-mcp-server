"""Tests for folder tools."""

import pytest
from unittest.mock import patch, AsyncMock

from google_drive.tools.folder_tools import create_folder


@pytest.fixture
def mock_drive():
    with patch("google_drive.tools.folder_tools.get_drive_service") as mock_get:
        mock_svc = AsyncMock()
        mock_get.return_value = mock_svc
        yield mock_svc


class TestCreateFolder:
    """Test create_folder tool."""

    @pytest.mark.asyncio
    async def test_create_folder_default_parent(self, mock_drive):
        mock_drive.create_folder.return_value = {
            "id": "folder_id_1",
            "name": "New Project",
            "mimeType": "application/vnd.google-apps.folder",
            "webViewLink": "https://drive.google.com/drive/folders/folder_id_1",
        }

        result = await create_folder("New Project")

        assert "Created folder 'New Project'" in result
        assert "folder_id_1" in result
        assert "https://drive.google.com" in result
        mock_drive.create_folder.assert_called_once_with("New Project", parent_id="root")

    @pytest.mark.asyncio
    async def test_create_folder_custom_parent(self, mock_drive):
        mock_drive.create_folder.return_value = {
            "id": "subfolder_id",
            "name": "Subfolder",
            "mimeType": "application/vnd.google-apps.folder",
            "webViewLink": "",
        }

        result = await create_folder("Subfolder", parent_folder_id="parent123")

        assert "Created folder 'Subfolder'" in result
        assert "subfolder_id" in result
        mock_drive.create_folder.assert_called_once_with("Subfolder", parent_id="parent123")

    @pytest.mark.asyncio
    async def test_create_folder_no_link(self, mock_drive):
        mock_drive.create_folder.return_value = {
            "id": "fid",
            "name": "Folder",
            "mimeType": "application/vnd.google-apps.folder",
        }

        result = await create_folder("Folder")

        assert "Created folder 'Folder'" in result
        assert "Link:" not in result
