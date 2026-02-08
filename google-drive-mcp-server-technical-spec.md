# Technical Specification: Google Drive MCP Server

**Version:** 1.0
**Author:** Tim Kitchens, Coding the Future with AI
**Status:** Draft
**Date:** 2026-02-08
**Companion Document:** `google-drive-mcp-server-prd.md`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Scaffolding: MCP Cookiecutter Template](#2-scaffolding-mcp-cookiecutter-template)
3. [Project Structure](#3-project-structure)
4. [Authentication System](#4-authentication-system)
5. [MCP Tool Specifications](#5-mcp-tool-specifications)
6. [Google Drive API Integration Layer](#6-google-drive-api-integration-layer)
7. [File Transfer Architecture](#7-file-transfer-architecture)
8. [Configuration](#8-configuration)
9. [Error Handling](#9-error-handling)
10. [Testing Strategy](#10-testing-strategy)
11. [Claude Code Integration](#11-claude-code-integration)
12. [Google API Reference Documentation](#12-google-api-reference-documentation)

---

## 1. Overview

### 1.1 What This Server Does

This MCP server acts as a **file transfer agent** between Google Drive and the local filesystem. It exposes six MCP tools that AI coding assistants call to search, browse, download, upload, inspect, and organize files on Google Drive.

### 1.2 The Core Design Decision: Filesystem-Mediated Binary Transfer

The central architectural decision is that **binary file content never passes through the MCP protocol**. Instead:

- **Downloads:** The MCP server calls the Google Drive API, streams the bytes directly to a file on the local filesystem, and returns a short text confirmation to the AI assistant.
- **Uploads:** The MCP server reads bytes from a file on the local filesystem, streams them to the Google Drive API, and returns a short text confirmation.

This means:
- The AI assistant's context window is never polluted with binary data
- Files of any size work (the MCP response is always a small text string)
- Every file type works (the server never attempts to decode or interpret binary content)

### 1.3 Technology Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| MCP Framework | FastMCP (via mcp SDK) | Latest |
| Google API Client | `google-api-python-client` | Latest |
| Google Auth | `google-auth-oauthlib`, `google-auth-httplib2` | Latest |
| HTTP Client | `google-api-python-client` built-in (httplib2) | — |
| Configuration | PyYAML, python-dotenv, platformdirs | Latest |
| Logging | Loguru (via cookiecutter template) | Latest |
| Transport | STDIO (primary), SSE and Streamable HTTP (secondary) | — |

---

## 2. Scaffolding: MCP Cookiecutter Template

### 2.1 Initial Project Generation

The project MUST be scaffolded using the MCP cookiecutter template before any custom code is added:

```bash
# Step 1: Generate the project skeleton
cookiecutter https://github.com/codingthefuturewithai/mcp-cookie-cutter.git
```

**Cookiecutter prompts — use these values:**

| Prompt | Value |
|---|---|
| `project_name` | Google Drive MCP Server |
| `author_name` | (implementer's name) |
| `email` | (implementer's email) |
| `server_port` | 3001 |

This generates a project slug of `google_drive_mcp_server` with the full decorator-based architecture, logging system, configuration management, and multi-transport support already in place.

### 2.2 What the Template Provides (Do Not Reimplement)

The cookiecutter template provides the following infrastructure that must be used as-is:

- **Decorator chain** (`decorators/`): `exception_handler`, `tool_logger`, `type_converter`, `parallelize` — all MCP tools are automatically wrapped with these
- **Unified logging** (`log_system/`): Correlation-aware structured logging with SQLite destination
- **Configuration management** (`config.py`): Platform-aware config/data/log directories, YAML config with env var overrides
- **Multi-transport server** (`server/app.py`): STDIO, SSE, and Streamable HTTP transports
- **Test scaffolding** (`tests/`): Unit and integration test structure with pytest/pytest-asyncio

### 2.3 What Must Be Added on Top

After scaffolding, the following must be added to implement the Google Drive functionality:

1. **Authentication module** — OAuth2 flow with credential storage (new module)
2. **Google Drive service layer** — Wrapper around `google-api-python-client` for Drive operations (new module)
3. **Tool implementations** — The six MCP tools (replace example tools)
4. **Additional dependencies** — Google API libraries added to `pyproject.toml`
5. **Configuration extensions** — OAuth client ID path, default download directory, etc.

---

## 3. Project Structure

After scaffolding and adding Google Drive features, the project structure should be:

```
google_drive_mcp_server/
├── google_drive_mcp_server/
│   ├── __init__.py                          # (from template)
│   ├── __main__.py                          # (from template)
│   ├── config.py                            # (from template, extended)
│   │
│   ├── server/
│   │   ├── __init__.py                      # (from template)
│   │   └── app.py                           # (from template, modified to register drive tools)
│   │
│   ├── tools/
│   │   ├── __init__.py                      # (from template)
│   │   ├── search_tools.py                  # NEW: search_files, list_folder
│   │   ├── transfer_tools.py                # NEW: download_file, upload_file
│   │   ├── metadata_tools.py                # NEW: get_file_info
│   │   └── folder_tools.py                  # NEW: create_folder
│   │
│   ├── auth/
│   │   ├── __init__.py                      # NEW
│   │   └── google_auth.py                   # NEW: OAuth2 flow and credential management
│   │
│   ├── drive/
│   │   ├── __init__.py                      # NEW
│   │   └── service.py                       # NEW: Google Drive API wrapper
│   │
│   ├── decorators/                          # (from template, unchanged)
│   │   ├── __init__.py
│   │   ├── exception_handler.py
│   │   ├── tool_logger.py
│   │   ├── type_converter.py
│   │   └── parallelize.py
│   │
│   ├── log_system/                          # (from template, unchanged)
│   │   ├── __init__.py
│   │   ├── correlation.py
│   │   ├── unified_logger.py
│   │   └── destinations/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── factory.py
│   │       └── sqlite.py
│   │
│   └── client/
│       ├── __init__.py                      # (from template)
│       └── app.py                           # (from template, can be adapted for testing)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                          # Extended with Drive-specific fixtures
│   ├── unit/
│   │   ├── test_config.py                   # (from template)
│   │   ├── test_decorators.py               # (from template)
│   │   ├── test_auth.py                     # NEW: OAuth flow tests
│   │   ├── test_search_tools.py             # NEW
│   │   ├── test_transfer_tools.py           # NEW
│   │   ├── test_metadata_tools.py           # NEW
│   │   └── test_folder_tools.py             # NEW
│   └── integration/
│       └── test_server.py                   # (from template, extended)
│
├── pyproject.toml                           # (from template, extended with google deps)
├── README.md                                # (from template, rewritten for this project)
├── .gitignore                               # (from template, extended)
└── LICENSE                                  # (from template)
```

---

## 4. Authentication System

### 4.1 OAuth2 Flow

The server uses Google's **OAuth 2.0 for Desktop Applications** flow:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  MCP Server  │────>│ Local Browser │────>│ Google OAuth2    │
│  (first run) │     │ (consent)     │     │ Consent Screen   │
└─────────────┘     └──────────────┘     └─────────────────┘
       │                    │                       │
       │                    │    auth code           │
       │                    │<──────────────────────│
       │   auth code        │                       │
       │<───────────────────│                       │
       │                                            │
       │   exchange code for tokens                 │
       │───────────────────────────────────────────>│
       │                                            │
       │   access_token + refresh_token             │
       │<───────────────────────────────────────────│
       │                                            │
       │   store refresh_token locally              │
       └────────────────────────────────────────────┘
```

### 4.2 Required OAuth Scopes

```python
SCOPES = [
    "https://www.googleapis.com/auth/drive",  # Full Drive access (read, write, delete)
]
```

**Rationale:** The `drive` scope is the simplest scope that covers all operations (search, download, upload, folder creation). The more restrictive `drive.file` scope only allows access to files created by the app, which defeats the purpose (users need to access files they didn't create through this tool). The `drive.readonly` scope doesn't allow uploads or folder creation.

**Note:** This is a "restricted" scope per Google's classification, which means the OAuth consent screen will show a warning to users. For internal/consulting use, this is acceptable. If the app is ever published to Google's marketplace, it would require a security review.

### 4.3 Credential Storage

```
~/.config/google_drive_mcp_server/          # Linux
~/Library/Application Support/google_drive_mcp_server/  # macOS

├── client_secret.json        # OAuth client credentials (user provides)
└── token.json                # Stored access + refresh token (auto-generated)
```

The `platformdirs` library (already included by the cookiecutter template) determines the correct platform-specific path.

### 4.4 Implementation: `auth/google_auth.py`

```python
"""
Google OAuth2 authentication for Google Drive MCP Server.

Handles the OAuth2 Desktop Application flow:
1. First run: Opens browser for user consent, stores refresh token
2. Subsequent runs: Uses stored refresh token, auto-refreshes access token
3. Token expiry: Automatically refreshes using the refresh token
4. Token revocation: Detects and prompts re-authentication
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_credentials(config_dir: Path) -> Credentials:
    """
    Get valid Google credentials, initiating OAuth flow if necessary.

    Args:
        config_dir: Platform-specific config directory path

    Returns:
        Valid Google OAuth2 Credentials object

    Raises:
        FileNotFoundError: If client_secret.json is not found in config_dir
        AuthenticationError: If OAuth flow fails or is cancelled by user
    """
    token_path = config_dir / "token.json"
    client_secret_path = config_dir / "client_secret.json"

    creds = None

    # Load existing token if available
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # If no valid credentials, initiate OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            creds.refresh(Request())
        else:
            # No credentials or refresh failed — run full OAuth flow
            if not client_secret_path.exists():
                raise FileNotFoundError(
                    f"OAuth client credentials not found at {client_secret_path}. "
                    f"Download client_secret.json from Google Cloud Console "
                    f"and place it at: {client_secret_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path), SCOPES
            )
            creds = flow.run_local_server(port=0)  # port=0 picks an available port

        # Save credentials for next run
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return creds


def build_drive_service(config_dir: Path):
    """
    Build an authenticated Google Drive API service object.

    Returns:
        googleapiclient.discovery.Resource: Drive v3 service object
    """
    from googleapiclient.discovery import build

    creds = get_credentials(config_dir)
    return build("drive", "v3", credentials=creds)
```

### 4.5 Setup Instructions for Users

Users must create a Google Cloud project with the Drive API enabled and download OAuth credentials. The README should include step-by-step instructions:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the "Google Drive API" via APIs & Services > Library
4. Create OAuth 2.0 credentials: APIs & Services > Credentials > Create Credentials > OAuth client ID
5. Select "Desktop app" as the application type
6. Download the JSON file and save it as `client_secret.json` in the config directory
7. On first server run, a browser window will open for consent

---

## 5. MCP Tool Specifications

### 5.1 Tool Overview

| Tool | Purpose | Returns |
|---|---|---|
| `search_files` | Search Drive by name, content, or type | Text: list of matching files with metadata |
| `list_folder` | List contents of a Drive folder | Text: list of items with metadata |
| `download_file` | Download any file to local filesystem | Text: confirmation with local path and size |
| `upload_file` | Upload any local file to Drive | Text: confirmation with Drive file ID and link |
| `get_file_info` | Get metadata about a file without downloading | Text: detailed file metadata |
| `create_folder` | Create a new folder in Drive | Text: confirmation with folder ID and link |

### 5.2 Tool: `search_files`

**File:** `tools/search_tools.py`

```python
async def search_files(
    query: str,
    max_results: int = 20,
    file_type: str = None,
) -> str:
    """
    Search for files and folders in Google Drive.

    Supports natural language queries (e.g., "architecture document") and
    Google Drive query syntax (e.g., "name contains 'spec' and mimeType = 'application/pdf'").

    Args:
        query: Search query. Can be natural language or Drive query syntax.
               Natural language queries are automatically converted to fullText search.
               Drive query syntax (containing operators like =, contains, in) is passed through as-is.
        max_results: Maximum number of results to return. Default 20, maximum 100.
        file_type: Optional filter by file type. Accepts: "pdf", "doc", "sheet", "slide",
                   "image", "folder", or a MIME type string.

    Returns:
        Formatted list of matching files with: name, ID, type, size, modified date, and web link.
        Returns "No files found" message if no matches.
    """
```

**Implementation details:**

- Detect whether `query` is structured (contains Drive API operators like `=`, `contains`, `in parents`, `mimeType`) or natural language
- If natural language: wrap as `fullText contains '{query}'`
- If structured: pass through as-is to the `q` parameter
- If `file_type` is provided, append a `mimeType` filter (map friendly names to MIME types)
- Use `files.list` with `supportsAllDrives=True` and `includeItemsFromAllDrives=True`
- Request fields: `id, name, mimeType, size, modifiedTime, webViewLink, parents`
- Format results as a readable text list

**MIME type mapping for `file_type` parameter:**

```python
FILE_TYPE_MAP = {
    "pdf": "application/pdf",
    "doc": "application/vnd.google-apps.document",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "sheet": "application/vnd.google-apps.spreadsheet",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "slide": "application/vnd.google-apps.presentation",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "image": None,  # Special case: matches image/*
    "folder": "application/vnd.google-apps.folder",
    "text": "text/plain",
    "csv": "text/csv",
    "json": "application/json",
}
```

### 5.3 Tool: `list_folder`

**File:** `tools/search_tools.py`

```python
async def list_folder(
    folder_id: str = "root",
    max_results: int = 50,
) -> str:
    """
    List contents of a Google Drive folder.

    Args:
        folder_id: The Drive folder ID to list. Use "root" for the top-level
                   of My Drive. Use a folder ID from search_files or a previous
                   list_folder call to browse into subfolders.
        max_results: Maximum number of items to return. Default 50, maximum 200.

    Returns:
        Formatted list of folder contents with: name, ID, type (file/folder),
        size, and modified date. Folders are listed first, then files.
    """
```

**Implementation details:**

- Query: `'{folder_id}' in parents and trashed=false`
- Sort folders before files in the output
- Include `supportsAllDrives=True` for shared drive access
- Clearly indicate which items are folders vs files in the output (prefix with `[Folder]` or `[File]`)

### 5.4 Tool: `download_file`

**File:** `tools/transfer_tools.py`

This is the most important tool in the server. It must handle every file type correctly.

```python
async def download_file(
    file_id: str,
    local_path: str = None,
    export_format: str = None,
) -> str:
    """
    Download a file from Google Drive to the local filesystem.

    For regular files (PDFs, images, Office docs, etc.), downloads the original file.
    For Google-native documents (Docs, Sheets, Slides), exports to a portable format.

    The file is written directly to disk. Binary content never enters the AI context.

    Args:
        file_id: The Google Drive file ID to download. Get this from search_files
                 or list_folder results.
        local_path: Local filesystem path to save the file. Can be a directory
                    (file keeps its Drive name) or a full file path.
                    If not specified, downloads to ./downloads/ in the current
                    working directory.
        export_format: For Google-native documents only. Specifies the export format.
                       Google Docs: "pdf" (default), "docx", "txt", "html"
                       Google Sheets: "xlsx" (default), "csv", "pdf"
                       Google Slides: "pdf" (default), "pptx"
                       Ignored for non-Google-native files.

    Returns:
        Confirmation message with: filename, file size, local path where saved,
        and original Drive file type.
    """
```

**Implementation details — this is the critical path:**

```
┌───────────────────────────────────────────────────────┐
│                  download_file flow                     │
├───────────────────────────────────────────────────────┤
│                                                         │
│  1. Get file metadata (files.get)                      │
│     → name, mimeType, size                             │
│                                                         │
│  2. Determine download strategy:                       │
│     ┌──────────────────────────┐                       │
│     │ Google-native document?  │                       │
│     └─────────┬────────────────┘                       │
│           yes │          no │                          │
│               ▼              ▼                          │
│     files.export()    files.get_media()                │
│     (with target       (alt=media)                     │
│      mimeType)                                         │
│               │              │                          │
│               ▼              ▼                          │
│     ┌──────────────────────────┐                       │
│     │  Stream bytes to disk    │                       │
│     │  using MediaIoBaseDownload│                       │
│     │  with chunked transfer   │                       │
│     └──────────────────────────┘                       │
│               │                                         │
│               ▼                                         │
│     Return text confirmation:                          │
│     "Downloaded 'report.pdf' (4.1 MB)                  │
│      to ./downloads/report.pdf"                        │
│                                                         │
└───────────────────────────────────────────────────────┘
```

**Google-native document export MIME type mapping:**

```python
EXPORT_FORMATS = {
    "application/vnd.google-apps.document": {
        "pdf": ("application/pdf", ".pdf"),
        "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
        "txt": ("text/plain", ".txt"),
        "html": ("text/html", ".html"),
        "default": "pdf",
    },
    "application/vnd.google-apps.spreadsheet": {
        "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
        "csv": ("text/csv", ".csv"),
        "pdf": ("application/pdf", ".pdf"),
        "default": "xlsx",
    },
    "application/vnd.google-apps.presentation": {
        "pdf": ("application/pdf", ".pdf"),
        "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
        "default": "pdf",
    },
}
```

**Streaming download implementation:**

```python
import io
from googleapiclient.http import MediaIoBaseDownload

async def _download_to_file(service, file_id: str, dest_path: Path, mime_type: str = None):
    """
    Stream download from Drive API directly to a file on disk.

    Uses chunked transfer to avoid loading entire file into memory.
    Suitable for files of any size.
    """
    if mime_type:
        # Google-native document: export
        request = service.files().export_media(fileId=file_id, mimeType=mime_type)
    else:
        # Regular file: download original binary
        request = service.files().get_media(fileId=file_id)

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=256 * 1024)
        done = False
        while not done:
            status, done = await asyncio.to_thread(downloader.next_chunk)
            # Optional: log progress for large files
            if status:
                logger.debug(f"Download progress: {int(status.progress() * 100)}%")
```

**Local path resolution logic:**

```python
def _resolve_download_path(local_path: str | None, filename: str, cwd: str) -> Path:
    """
    Resolve the local filesystem path for a download.

    Rules:
    1. If local_path is None → use {cwd}/downloads/{filename}
    2. If local_path is a directory → use {local_path}/{filename}
    3. If local_path is a file path → use as-is
    """
    if local_path is None:
        dest = Path(cwd) / "downloads" / filename
    else:
        dest = Path(local_path)
        if dest.is_dir() or (not dest.suffix and not dest.exists()):
            # Treat as directory
            dest = dest / filename

    return dest
```

### 5.5 Tool: `upload_file`

**File:** `tools/transfer_tools.py`

```python
async def upload_file(
    local_path: str,
    folder_id: str = "root",
    file_name: str = None,
) -> str:
    """
    Upload a file from the local filesystem to Google Drive.

    Supports any file type. Uses resumable upload for reliability with large files.

    Args:
        local_path: Absolute or relative path to the local file to upload.
        folder_id: Google Drive folder ID to upload into. Default is "root"
                   (My Drive top level). Use a folder ID from search_files,
                   list_folder, or create_folder.
        file_name: Optional name for the file in Drive. If not specified,
                   uses the local filename.

    Returns:
        Confirmation message with: filename, file size, Drive file ID, and web link.
    """
```

**Implementation details:**

```python
import mimetypes
from googleapiclient.http import MediaFileUpload

UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB (Google recommended minimum for resumable)

async def _upload_from_file(
    service, local_path: Path, folder_id: str, file_name: str
) -> dict:
    """
    Upload a local file to Google Drive using resumable upload.

    Returns the created file's metadata dict.
    """
    # Detect MIME type from file extension
    mime_type, _ = mimetypes.guess_type(str(local_path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    file_metadata = {
        "name": file_name,
        "parents": [folder_id],
    }

    media = MediaFileUpload(
        str(local_path),
        mimetype=mime_type,
        resumable=True,
        chunksize=UPLOAD_CHUNK_SIZE,
    )

    created_file = await asyncio.to_thread(
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, size, mimeType",
            supportsAllDrives=True,
        )
        .execute
    )

    return created_file
```

**Validation:**
- Verify `local_path` exists and is a readable file before attempting upload
- Verify the path is a file, not a directory
- Provide clear error message if file not found

### 5.6 Tool: `get_file_info`

**File:** `tools/metadata_tools.py`

```python
async def get_file_info(
    file_id: str,
) -> str:
    """
    Get detailed metadata about a Google Drive file without downloading it.

    Args:
        file_id: The Google Drive file ID.

    Returns:
        Formatted metadata including: name, type, size, created date, modified date,
        owner, sharing status, parent folder(s), and web link.
    """
```

**Implementation details:**

- Use `files.get` with comprehensive fields:
  ```
  id, name, mimeType, size, createdTime, modifiedTime,
  owners, shared, parents, webViewLink, description,
  trashed, starred
  ```
- Format output as readable key-value pairs
- For Google-native documents (no `size` field), note the document type and that size is not available
- Resolve parent folder names (make a `files.get` call for each parent ID to get its name) for better readability

### 5.7 Tool: `create_folder`

**File:** `tools/folder_tools.py`

```python
async def create_folder(
    folder_name: str,
    parent_folder_id: str = "root",
) -> str:
    """
    Create a new folder in Google Drive.

    Args:
        folder_name: Name for the new folder.
        parent_folder_id: ID of the parent folder. Default is "root"
                          (My Drive top level). Use a folder ID from
                          search_files or list_folder to create a subfolder.

    Returns:
        Confirmation message with: folder name, folder ID, and web link.
    """
```

**Implementation details:**

```python
async def _create_folder(service, name: str, parent_id: str) -> dict:
    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = await asyncio.to_thread(
        service.files()
        .create(
            body=file_metadata,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        )
        .execute
    )
    return folder
```

### 5.8 MCP Parameter Rules

Per the cookiecutter template's MCP constraints:

- **No `Optional[T]` type hints** — use `param: str = None` instead of `param: Optional[str] = None`
- The `type_converter` decorator handles string-to-int and string-to-bool conversions from clients that send all parameters as strings
- All tools are automatically wrapped with the decorator chain: `exception_handler` > `tool_logger` > `type_converter`

---

## 6. Google Drive API Integration Layer

### 6.1 Service Layer: `drive/service.py`

This module provides a high-level wrapper around the Google Drive API, used by all tool implementations. It handles service construction, shared drive support, and common patterns.

```python
"""
Google Drive API service layer.

Provides authenticated access to Drive v3 API with shared drive support
and consistent error handling.
"""

class DriveService:
    """
    Wrapper around Google Drive API v3 service.

    Constructed once at server startup, shared across all tool calls.
    Handles authentication, shared drive support, and Google Workspace
    document detection.
    """

    def __init__(self, config_dir: Path):
        self._service = None
        self._config_dir = config_dir

    def _get_service(self):
        """Lazy-initialize the Drive service on first use."""
        if self._service is None:
            self._service = build_drive_service(self._config_dir)
        return self._service

    async def search(self, query: str, max_results: int, file_type: str = None) -> list[dict]:
        """Search for files. Returns list of file metadata dicts."""
        ...

    async def list_children(self, folder_id: str, max_results: int) -> list[dict]:
        """List folder contents. Returns list of file/folder metadata dicts."""
        ...

    async def get_metadata(self, file_id: str) -> dict:
        """Get file metadata. Returns metadata dict."""
        ...

    async def download(self, file_id: str, dest_path: Path, export_format: str = None) -> dict:
        """Download file to local path. Returns download info dict."""
        ...

    async def upload(self, local_path: Path, folder_id: str, file_name: str) -> dict:
        """Upload local file to Drive. Returns created file metadata dict."""
        ...

    async def create_folder(self, name: str, parent_id: str) -> dict:
        """Create folder in Drive. Returns folder metadata dict."""
        ...

    def is_google_native(self, mime_type: str) -> bool:
        """Check if a MIME type represents a Google Workspace document."""
        return mime_type in EXPORT_FORMATS

    def get_export_mime_type(self, google_mime_type: str, export_format: str = None) -> tuple[str, str]:
        """Get the export MIME type and file extension for a Google-native doc."""
        ...
```

### 6.2 Shared Drive Support

All API calls must include `supportsAllDrives=True` to work with files in shared drives. For `files.list` calls, also include `includeItemsFromAllDrives=True`.

### 6.3 Service Initialization

The `DriveService` instance should be created at server startup and injected into tools. In `server/app.py`, this fits into the existing template's initialization pattern:

```python
# In server/app.py, during tool registration
drive_service = DriveService(config_dir=get_config().config_dir)

# Tools receive drive_service through closure or module-level reference
```

---

## 7. File Transfer Architecture

### 7.1 Download Flow (Complete)

```
AI Assistant                MCP Server               Google Drive API        Local Filesystem
     │                          │                          │                       │
     │  download_file(id, path) │                          │                       │
     │─────────────────────────>│                          │                       │
     │                          │                          │                       │
     │                          │  files.get(id, fields)   │                       │
     │                          │─────────────────────────>│                       │
     │                          │  {name, mimeType, size}  │                       │
     │                          │<─────────────────────────│                       │
     │                          │                          │                       │
     │                          │  [if google-native:]     │                       │
     │                          │  files.export(mimeType)  │                       │
     │                          │  [else:]                 │                       │
     │                          │  files.get(alt=media)    │                       │
     │                          │─────────────────────────>│                       │
     │                          │  <chunked bytes stream>  │                       │
     │                          │<─────────────────────────│                       │
     │                          │                          │                       │
     │                          │  write chunks to file ──────────────────────────>│
     │                          │                          │                       │
     │  "Downloaded report.pdf  │                          │                       │
     │   (4.1 MB) to            │                          │                       │
     │   ./downloads/report.pdf"│                          │                       │
     │<─────────────────────────│                          │                       │
     │                          │                          │                       │
     │  [user asks to read it]  │                          │                       │
     │  Read("./downloads/      │                          │                       │
     │        report.pdf")      │                          │                       │
     │─────────(native tool)────│──────────────────────────│───────────────────────>│
     │  <file content>          │                          │                       │
     │<─────────────────────────│──────────────────────────│───────────────────────│
```

### 7.2 Upload Flow (Complete)

```
AI Assistant                MCP Server               Google Drive API        Local Filesystem
     │                          │                          │                       │
     │  upload_file(path,       │                          │                       │
     │    folder_id)            │                          │                       │
     │─────────────────────────>│                          │                       │
     │                          │                          │                       │
     │                          │  validate file exists ──────────────────────────>│
     │                          │  read metadata (size, name) <───────────────────│
     │                          │                          │                       │
     │                          │  files.create(           │                       │
     │                          │    uploadType=resumable, │                       │
     │                          │    media=MediaFileUpload)│                       │
     │                          │─────────────────────────>│                       │
     │                          │  <chunked upload>        │                       │
     │                          │─────────────────────────>│                       │
     │                          │  {id, name, webViewLink} │                       │
     │                          │<─────────────────────────│                       │
     │                          │                          │                       │
     │  "Uploaded spec.pdf      │                          │                       │
     │   (2.3 MB) to            │                          │                       │
     │   'Project Docs' folder  │                          │                       │
     │   ID: abc123             │                          │                       │
     │   Link: https://..."     │                          │                       │
     │<─────────────────────────│                          │                       │
```

### 7.3 Memory Management

The server must not load entire files into memory. For both downloads and uploads:

- **Downloads:** Use `MediaIoBaseDownload` with a file handle opened in write-binary mode (`"wb"`). The Google API client streams chunks directly to the file handle.
- **Uploads:** Use `MediaFileUpload` with a file path (not `MediaIoBaseUpload` with BytesIO). The Google API client reads chunks directly from disk.

This ensures the server's memory usage stays constant regardless of file size.

---

## 8. Configuration

### 8.1 Extending the Template's Config

The cookiecutter template provides `ServerConfig` in `config.py`. Extend it with Google Drive-specific settings:

```python
@dataclass
class ServerConfig:
    # --- From template (keep all existing fields) ---
    name: str = "google-drive-mcp-server"
    description: str = "Google Drive MCP Server for AI coding assistants"
    port: int = 3001
    log_level: str = "INFO"
    default_transport: str = "stdio"
    default_host: str = "127.0.0.1"

    # --- Google Drive specific (add these) ---
    default_download_dir: str = "./downloads"   # Default download location
    google_client_secret_path: str = None       # Override path to client_secret.json
    max_upload_size_mb: int = 500               # Safety limit for uploads
```

### 8.2 Environment Variable Overrides

Following the template's pattern, all config values can be overridden via environment variables:

```bash
GOOGLE_DRIVE_MCP_DEFAULT_DOWNLOAD_DIR="./my-downloads"
GOOGLE_DRIVE_MCP_GOOGLE_CLIENT_SECRET_PATH="/path/to/client_secret.json"
GOOGLE_DRIVE_MCP_LOG_LEVEL="DEBUG"
```

### 8.3 Config File

```yaml
# ~/.config/google_drive_mcp_server/config.yaml
server:
  name: google-drive-mcp-server
  log_level: INFO
  default_transport: stdio

google_drive:
  default_download_dir: ./downloads
  max_upload_size_mb: 500
```

---

## 9. Error Handling

### 9.1 Error Categories

The cookiecutter template's `exception_handler` decorator catches all exceptions and logs them with correlation IDs. On top of that, the tools should raise specific, user-friendly exceptions:

| Error Scenario | Exception | User-Facing Message |
|---|---|---|
| OAuth credentials not found | `FileNotFoundError` | "OAuth client credentials not found at {path}. Download client_secret.json from Google Cloud Console and place it at: {path}" |
| OAuth token expired and refresh failed | `AuthenticationError` | "Google authentication expired. Please re-authenticate by deleting {token_path} and restarting the server." |
| File not found on Drive | `FileNotFoundError` | "File with ID '{file_id}' not found on Google Drive. It may have been deleted or you may not have access." |
| Local file not found for upload | `FileNotFoundError` | "Local file not found: {path}. Please verify the file exists." |
| Permission denied on Drive | `PermissionError` | "Access denied to file '{name}'. You may not have permission to access this file." |
| Google API quota exceeded | `RateLimitError` | "Google Drive API rate limit reached. Please wait a moment and try again." |
| Network error during transfer | `ConnectionError` | "Network error during {operation}. Please check your connection and try again." |
| Local disk full during download | `OSError` | "Failed to write file: disk may be full. {details}" |

### 9.2 Google API Error Handling

The Google API client raises `googleapiclient.errors.HttpError` for API failures. These should be caught and translated to user-friendly messages:

```python
from googleapiclient.errors import HttpError

try:
    result = await asyncio.to_thread(request.execute)
except HttpError as e:
    status = e.resp.status
    if status == 404:
        raise FileNotFoundError(f"File '{file_id}' not found on Google Drive.")
    elif status == 403:
        raise PermissionError(f"Access denied to file '{file_id}'.")
    elif status == 429:
        raise RateLimitError("Google Drive API rate limit reached.")
    else:
        raise RuntimeError(f"Google Drive API error ({status}): {e.reason}")
```

---

## 10. Testing Strategy

### 10.1 Unit Tests (No Google API Required)

Unit tests mock the Google Drive API service and verify tool logic:

- **Path resolution tests:** Verify `_resolve_download_path` handles all cases (None path, directory path, file path, missing parents)
- **Query construction tests:** Verify natural language vs structured query detection and formatting
- **Export format mapping tests:** Verify correct MIME type selection for all Google-native document types and export formats
- **MIME type detection tests:** Verify upload MIME type guessing for various file extensions
- **Error handling tests:** Verify correct exception types for each error scenario
- **Config tests:** Verify config loading, env var overrides, platform path resolution

### 10.2 Integration Tests (Require Google API Credentials)

These tests hit the real Google Drive API and require a test Google account:

- **Auth flow test:** Verify token storage and refresh
- **Search test:** Upload a test file, search for it, verify it appears in results
- **Download test:** Upload a test file, download it, verify byte-for-byte match
- **Upload test:** Upload a local file, download it back, verify match
- **Google-native export test:** Create a Google Doc (via API), export as PDF, verify non-empty PDF
- **Folder test:** Create folder, upload file into it, list folder, verify file appears
- **Large file test:** Upload and download a file > 10MB to verify chunked transfer

### 10.3 Test Fixtures

```python
# conftest.py additions
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_drive_service():
    """Mocked Google Drive service for unit tests."""
    service = MagicMock()
    service.files.return_value.list.return_value.execute = MagicMock(
        return_value={"files": []}
    )
    service.files.return_value.get.return_value.execute = MagicMock(
        return_value={"id": "test", "name": "test.pdf", "mimeType": "application/pdf"}
    )
    return service

@pytest.fixture
def tmp_download_dir(tmp_path):
    """Temporary download directory for tests."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir
```

---

## 11. Claude Code Integration

### 11.1 Claude Code MCP Configuration

Users add the server to their Claude Code configuration:

**Via `claude mcp add`:**
```bash
claude mcp add google-drive -- uv run --directory /path/to/google_drive_mcp_server google-drive-mcp-server
```

**Or manually in `~/.claude/claude_desktop_config.json`:**
```json
{
  "mcpServers": {
    "google-drive": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/google_drive_mcp_server",
        "google-drive-mcp-server"
      ]
    }
  }
}
```

### 11.2 Expected Usage Patterns in Claude Code

Once configured, developers should be able to interact naturally:

```
User: "Find the architecture document in our team's Google Drive"
→ Claude Code calls: search_files(query="architecture document")
→ Returns: list of matching files with IDs

User: "Download that PDF to my current directory"
→ Claude Code calls: download_file(file_id="abc123", local_path="./")
→ File written to ./Architecture_Overview.pdf
→ Returns: "Downloaded 'Architecture_Overview.pdf' (2.1 MB) to ./Architecture_Overview.pdf"

User: "Read that file and summarize the key decisions"
→ Claude Code uses its native Read tool on ./Architecture_Overview.pdf
→ Claude Code reads the PDF content and provides summary

User: "Upload this spec to the 'Project Docs' folder on Drive"
→ Claude Code calls: upload_file(local_path="./api_spec.yaml", folder_id="xyz789")
→ Returns: "Uploaded 'api_spec.yaml' (45 KB) to 'Project Docs' - Link: https://..."
```

### 11.3 STDIO Transport

Claude Code uses STDIO transport exclusively. The cookiecutter template already supports this as the default transport. No special configuration needed — when Claude Code spawns the server process, it communicates via stdin/stdout.

---

## 12. Google API Reference Documentation

The following official Google documentation should be referenced during implementation.

### 12.1 Authentication

| Document | URL | Relevance |
|---|---|---|
| OAuth 2.0 Overview | https://developers.google.com/identity/protocols/oauth2 | General OAuth flow understanding |
| OAuth 2.0 for Desktop Apps | https://developers.google.com/identity/protocols/oauth2/native-app | **Primary auth reference** — loopback redirect flow, PKCE, token exchange |
| Drive API Scopes | https://developers.google.com/workspace/drive/api/guides/api-specific-auth | Scope selection and sensitivity levels |
| Python `InstalledAppFlow` Reference | https://google-auth-oauthlib.readthedocs.io/en/latest/reference/google_auth_oauthlib.flow.html | `from_client_secrets_file()`, `run_local_server()` implementation |

### 12.2 Core API Operations

| Document | URL | Relevance |
|---|---|---|
| Python Quickstart | https://developers.google.com/workspace/drive/api/quickstart/python | End-to-end setup: credentials, dependencies, service construction |
| files.list (REST Reference) | https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list | Search/list parameters: `q`, `fields`, `pageSize`, `corpora` |
| Search Query Syntax | https://developers.google.com/workspace/drive/api/guides/ref-search-terms | Query operators: `contains`, `=`, `in parents`, `mimeType`, etc. |
| files.get (REST Reference) | https://developers.google.com/workspace/drive/api/reference/rest/v3/files/get | File metadata retrieval, `fields` parameter |
| File Resource Schema | https://developers.google.com/workspace/drive/api/reference/rest/v3/files | Complete field reference for file metadata |

### 12.3 Downloads and Exports

| Document | URL | Relevance |
|---|---|---|
| Download and Export Files Guide | https://developers.google.com/workspace/drive/api/guides/manage-downloads | **Critical** — `alt=media` for binary download, `files.export` for Google-native docs, 10MB export limit |
| files.export (REST Reference) | https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export | Export parameters and MIME type requirements |
| Supported MIME Types | https://developers.google.com/workspace/drive/api/guides/mime-types | Export format mappings for Google Docs/Sheets/Slides |

### 12.4 Uploads

| Document | URL | Relevance |
|---|---|---|
| Upload File Data Guide | https://developers.google.com/workspace/drive/api/guides/manage-uploads | **Critical** — simple, multipart, and resumable upload protocols; chunk size requirements (256KB multiples) |
| files.create (REST Reference) | https://developers.google.com/workspace/drive/api/reference/rest/v3/files/create | Upload parameters: `uploadType`, `fields`, `supportsAllDrives` |
| Python `MediaFileUpload` Reference | https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient.http.MediaFileUpload-class.html | Constructor parameters: `mimetype`, `chunksize`, `resumable` |
| Python Media Upload Guide | https://googleapis.github.io/google-api-python-client/docs/media.html | `MediaFileUpload`, `MediaIoBaseUpload`, resumable upload with `next_chunk()` |

### 12.5 Folders

| Document | URL | Relevance |
|---|---|---|
| Create and Populate Folders Guide | https://developers.google.com/workspace/drive/api/guides/folder | Folder creation (`mimeType: "application/vnd.google-apps.folder"`), parent-child relationships, listing folder contents |

### 12.6 Python Client Library

| Document | URL | Relevance |
|---|---|---|
| `google-api-python-client` Getting Started | https://googleapis.github.io/google-api-python-client/docs/start.html | Library installation, building service objects |
| Drive v3 Python Methods Reference | https://googleapis.github.io/google-api-python-client/docs/dyn/drive_v3.files.html | Auto-generated docs for all `files()` methods with exact Python signatures |

### 12.7 Dependencies to Add to `pyproject.toml`

```toml
[project]
dependencies = [
    # ... existing cookiecutter dependencies ...
    "google-api-python-client>=2.100.0",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.2.0",
]
```

---

## Appendix A: Cookiecutter Template Reference

The MCP cookiecutter template at `https://github.com/codingthefuturewithai/mcp-cookie-cutter.git` provides the foundational scaffolding. Key aspects that the implementation must preserve:

### Decorator Chain (Applied Automatically)

All tools registered through `server/app.py` are automatically wrapped with:
1. `type_converter` (innermost) — Handles string-to-int, string-to-bool conversions for client compatibility
2. `tool_logger` — Correlation-aware execution logging with timing
3. `exception_handler` (outermost) — Catches exceptions, logs with correlation ID, re-raises for MCP error response

### Tool Registration Pattern

Tools are added to lists and registered in `server/app.py`:

```python
# In tools/__init__.py or individual tool files
drive_tools = [search_files, list_folder, download_file, upload_file, get_file_info, create_folder]

# In server/app.py register_tools()
for tool_func in drive_tools:
    decorated = exception_handler(tool_logger(type_converter(tool_func)))
    mcp_server.tool()(decorated)
```

### No `Optional[T]` in MCP Tool Parameters

MCP/Pydantic rejects `Optional[T]`. Use `param: str = None` instead:

```python
# Correct
async def download_file(file_id: str, local_path: str = None, export_format: str = None) -> str:

# Wrong — will fail
async def download_file(file_id: str, local_path: Optional[str] = None) -> str:
```

### Configuration Access

```python
from google_drive_mcp_server.config import get_config

config = get_config()
download_dir = config.default_download_dir
```

### Logging

```python
from google_drive_mcp_server.log_system.unified_logger import UnifiedLogger

logger = UnifiedLogger.get_logger(__name__)
logger.info("Downloading file", file_id=file_id, dest=str(dest_path))
```
