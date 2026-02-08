"""Tests for transfer tools (download and upload)."""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

from google_drive.tools.transfer_tools import (
    download_file,
    upload_file,
    _resolve_download_path,
    _format_size,
)


class TestFormatSize:
    """Test _format_size helper."""

    def test_bytes(self):
        assert _format_size(512) == "512 B"

    def test_kilobytes(self):
        assert _format_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert _format_size(1048576) == "1.0 MB"

    def test_gigabytes(self):
        result = _format_size(1073741824)
        assert "1.0 GB" == result


class TestResolveDownloadPath:
    """Test _resolve_download_path helper."""

    @patch("google_drive.tools.transfer_tools.get_config")
    def test_empty_path_uses_config_dir(self, mock_config, tmp_path):
        mock_config.return_value = MagicMock(download_dir=tmp_path)
        result = _resolve_download_path("", "report.pdf")
        assert result == tmp_path / "report.pdf"

    def test_directory_path_appends_filename(self, tmp_path):
        result = _resolve_download_path(str(tmp_path), "report.pdf")
        assert result == tmp_path / "report.pdf"

    def test_file_path_returned_as_is(self, tmp_path):
        file_path = str(tmp_path / "custom_name.pdf")
        result = _resolve_download_path(file_path, "report.pdf")
        assert result == Path(file_path)


@pytest.fixture
def mock_drive():
    with patch("google_drive.tools.transfer_tools.get_drive_service") as mock_get:
        mock_svc = AsyncMock()
        mock_get.return_value = mock_svc
        yield mock_svc


class TestDownloadFile:
    """Test download_file tool."""

    @pytest.mark.asyncio
    async def test_download_confirmation(self, mock_drive, tmp_path):
        mock_drive.get_metadata.return_value = {
            "name": "report.pdf", "mimeType": "application/pdf"
        }
        mock_drive.download.return_value = (str(tmp_path / "report.pdf"), 1024)

        with patch("google_drive.tools.transfer_tools.get_config") as mock_config:
            mock_config.return_value = MagicMock(download_dir=tmp_path)
            result = await download_file("file123")

        assert "Downloaded 'report.pdf'" in result
        assert "1.0 KB" in result

    @pytest.mark.asyncio
    async def test_download_with_custom_path(self, mock_drive, tmp_path):
        mock_drive.get_metadata.return_value = {
            "name": "data.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        dest = str(tmp_path / "data.xlsx")
        mock_drive.download.return_value = (dest, 2048)

        result = await download_file("file456", local_path=dest)

        assert "Downloaded 'data.xlsx'" in result
        assert str(tmp_path) in result

    @pytest.mark.asyncio
    async def test_download_with_export_format(self, mock_drive, tmp_path):
        mock_drive.get_metadata.return_value = {
            "name": "My Doc", "mimeType": "application/vnd.google-apps.document"
        }
        mock_drive.download.return_value = (str(tmp_path / "My Doc.docx"), 5000)

        with patch("google_drive.tools.transfer_tools.get_config") as mock_config:
            mock_config.return_value = MagicMock(download_dir=tmp_path)
            result = await download_file("doc123", export_format="docx")

        mock_drive.download.assert_called_once()
        assert "Downloaded 'My Doc'" in result


class TestUploadFile:
    """Test upload_file tool."""

    @pytest.mark.asyncio
    async def test_upload_confirmation(self, mock_drive, tmp_path):
        test_file = tmp_path / "upload_me.txt"
        test_file.write_text("hello")

        mock_drive.upload.return_value = {
            "id": "new_id_123",
            "name": "upload_me.txt",
            "webViewLink": "https://drive.google.com/file/new_id_123/view",
        }

        with patch("google_drive.tools.transfer_tools.get_config") as mock_config:
            mock_config.return_value = MagicMock(max_upload_size_mb=500)
            result = await upload_file(str(test_file))

        assert "Uploaded 'upload_me.txt'" in result
        assert "new_id_123" in result
        assert "https://drive.google.com" in result

    @pytest.mark.asyncio
    async def test_upload_missing_file_raises(self, mock_drive):
        with pytest.raises(FileNotFoundError, match="Local file not found"):
            await upload_file("/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_upload_directory_raises(self, mock_drive, tmp_path):
        with pytest.raises(ValueError, match="Cannot upload a directory"):
            await upload_file(str(tmp_path))

    @pytest.mark.asyncio
    async def test_upload_exceeds_size_limit(self, mock_drive, tmp_path):
        big_file = tmp_path / "big.bin"
        big_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB

        with patch("google_drive.tools.transfer_tools.get_config") as mock_config:
            mock_config.return_value = MagicMock(max_upload_size_mb=1)  # 1 MB limit
            with pytest.raises(ValueError, match="exceeds the .* upload limit"):
                await upload_file(str(big_file))

    @pytest.mark.asyncio
    async def test_upload_custom_name(self, mock_drive, tmp_path):
        test_file = tmp_path / "local.txt"
        test_file.write_text("data")

        mock_drive.upload.return_value = {
            "id": "id1", "name": "custom.txt", "webViewLink": ""
        }

        with patch("google_drive.tools.transfer_tools.get_config") as mock_config:
            mock_config.return_value = MagicMock(max_upload_size_mb=500)
            result = await upload_file(str(test_file), file_name="custom.txt")

        mock_drive.upload.assert_called_once()
        call_kwargs = mock_drive.upload.call_args
        assert call_kwargs.kwargs["file_name"] == "custom.txt"
