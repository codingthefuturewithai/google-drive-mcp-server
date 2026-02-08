"""Tests for DriveService layer."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from googleapiclient.errors import HttpError

from google_drive.drive.service import (
    DriveService,
    get_drive_service,
    _handle_http_error,
    FILE_TYPE_MAP,
    EXPORT_FORMATS,
)


class TestHandleHttpError:
    """Test HttpError translation."""

    def _make_http_error(self, status: int, reason: str = "test error"):
        resp = MagicMock()
        resp.status = status
        error = HttpError(resp, b"error content")
        error._get_reason = MagicMock(return_value=reason)
        return error

    def test_404_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="File not found"):
            _handle_http_error(self._make_http_error(404))

    def test_403_raises_permission_error(self):
        with pytest.raises(PermissionError, match="Access denied"):
            _handle_http_error(self._make_http_error(403))

    def test_500_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="Google Drive API error"):
            _handle_http_error(self._make_http_error(500))


class TestDriveServiceStatic:
    """Test static/class methods that don't need API calls."""

    def test_is_google_native_true(self):
        assert DriveService.is_google_native("application/vnd.google-apps.document")
        assert DriveService.is_google_native("application/vnd.google-apps.spreadsheet")

    def test_is_google_native_false(self):
        assert not DriveService.is_google_native("application/pdf")
        assert not DriveService.is_google_native("text/plain")

    def test_get_export_mime_type_default(self):
        mime, ext = DriveService.get_export_mime_type(
            "application/vnd.google-apps.document"
        )
        assert mime == "application/pdf"
        assert ext == ".pdf"

    def test_get_export_mime_type_specific(self):
        mime, ext = DriveService.get_export_mime_type(
            "application/vnd.google-apps.document", "docx"
        )
        assert ext == ".docx"

    def test_get_export_mime_type_spreadsheet_csv(self):
        mime, ext = DriveService.get_export_mime_type(
            "application/vnd.google-apps.spreadsheet", "csv"
        )
        assert mime == "text/csv"
        assert ext == ".csv"

    def test_get_export_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported export format"):
            DriveService.get_export_mime_type(
                "application/vnd.google-apps.document", "mp3"
            )

    def test_get_export_unknown_mime_type(self):
        with pytest.raises(ValueError, match="No export formats available"):
            DriveService.get_export_mime_type("application/octet-stream")


class TestDriveServiceSearch:
    """Test search method query construction."""

    @pytest.fixture
    def drive(self):
        svc = DriveService()
        mock_service = MagicMock()
        svc._service = mock_service
        return svc, mock_service

    @pytest.mark.asyncio
    async def test_natural_language_query(self, drive):
        svc, mock_service = drive
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": []}
        mock_service.files.return_value.list.return_value = mock_list

        await svc.search("budget report")

        call_kwargs = mock_service.files.return_value.list.call_args
        q = call_kwargs.kwargs.get("q") or call_kwargs[1].get("q")
        assert "name contains 'budget report'" in q
        assert "trashed=false" in q

    @pytest.mark.asyncio
    async def test_structured_query_passthrough(self, drive):
        svc, mock_service = drive
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": []}
        mock_service.files.return_value.list.return_value = mock_list

        raw_q = "'abc123' in parents and mimeType='application/pdf'"
        await svc.search(raw_q)

        call_kwargs = mock_service.files.return_value.list.call_args
        q = call_kwargs.kwargs.get("q") or call_kwargs[1].get("q")
        assert q == raw_q

    @pytest.mark.asyncio
    async def test_file_type_filter_exact(self, drive):
        svc, mock_service = drive
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": []}
        mock_service.files.return_value.list.return_value = mock_list

        await svc.search("report", file_type="document")

        call_kwargs = mock_service.files.return_value.list.call_args
        q = call_kwargs.kwargs.get("q") or call_kwargs[1].get("q")
        assert "mimeType='application/vnd.google-apps.document'" in q

    @pytest.mark.asyncio
    async def test_file_type_filter_prefix(self, drive):
        svc, mock_service = drive
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": []}
        mock_service.files.return_value.list.return_value = mock_list

        await svc.search("photo", file_type="image")

        call_kwargs = mock_service.files.return_value.list.call_args
        q = call_kwargs.kwargs.get("q") or call_kwargs[1].get("q")
        assert "mimeType contains 'image/'" in q

    @pytest.mark.asyncio
    async def test_max_results_capped_at_100(self, drive):
        svc, mock_service = drive
        mock_list = MagicMock()
        mock_list.execute.return_value = {"files": []}
        mock_service.files.return_value.list.return_value = mock_list

        await svc.search("test", max_results=500)

        call_kwargs = mock_service.files.return_value.list.call_args
        page_size = call_kwargs.kwargs.get("pageSize") or call_kwargs[1].get("pageSize")
        assert page_size == 100

    @pytest.mark.asyncio
    async def test_http_error_translated(self, drive):
        svc, mock_service = drive
        resp = MagicMock()
        resp.status = 403
        error = HttpError(resp, b"forbidden")
        error._get_reason = MagicMock(return_value="forbidden")
        mock_service.files.return_value.list.return_value.execute.side_effect = error

        with pytest.raises(PermissionError):
            await svc.search("test")


class TestDriveServiceLazyInit:
    """Test lazy initialization of the service."""

    def test_service_none_initially(self):
        svc = DriveService()
        assert svc._service is None

    @patch("google_drive.drive.service.build_drive_service")
    @patch("google_drive.drive.service.get_config")
    def test_get_service_initializes(self, mock_config, mock_build):
        mock_config.return_value = MagicMock(config_dir="/tmp", google_client_secret_path="")
        mock_build.return_value = MagicMock()

        svc = DriveService()
        result = svc._get_service()

        mock_build.assert_called_once()
        assert result is mock_build.return_value

    @patch("google_drive.drive.service.build_drive_service")
    @patch("google_drive.drive.service.get_config")
    def test_get_service_reuses(self, mock_config, mock_build):
        mock_config.return_value = MagicMock(config_dir="/tmp", google_client_secret_path="")
        mock_build.return_value = MagicMock()

        svc = DriveService()
        svc._get_service()
        svc._get_service()

        assert mock_build.call_count == 1


class TestGetDriveServiceSingleton:
    """Test module-level singleton."""

    def test_returns_same_instance(self):
        import google_drive.drive.service as mod
        mod._drive_service = None  # reset

        s1 = get_drive_service()
        s2 = get_drive_service()
        assert s1 is s2

        mod._drive_service = None  # cleanup
