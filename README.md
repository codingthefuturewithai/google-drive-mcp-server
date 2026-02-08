# Google Drive MCP Server

An MCP (Model Context Protocol) server that gives AI coding assistants the ability to search, browse, download, upload, and organize files on Google Drive. Binary content never enters the MCP protocol — files are transferred to/from the local filesystem.

## Quick Start for MCP Clients

There are two ways to run the server: **direct install** or **Docker container**. Both require Google OAuth credentials.

### 1. Get your Google credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select an existing one)
3. Enable the **Google Drive API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Choose **Desktop app**, then download the JSON file
6. Rename it to `client_secret.json`

### 2. Place credentials and run OAuth flow

```bash
# Clone the repo
git clone <repository-url>
cd google_drive
uv sync

# Place your credentials in the platform config directory
cp /path/to/client_secret.json "$(python -c "import platformdirs; print(platformdirs.user_config_dir('google_drive'))")/client_secret.json"

# Run OAuth flow (opens browser for Google sign-in)
uv run python -c "from google_drive.auth import get_credentials; import platformdirs; get_credentials(platformdirs.user_config_dir('google_drive'))"
```

This generates a `token.json` in the same directory. Both files are needed whether you run directly or via Docker.

### 3a. Option A — Run directly (STDIO)

```bash
# Add to Claude Code
claude mcp add google-drive -- uv run --directory /path/to/google_drive python -m google_drive
```

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/)

### 3b. Option B — Run via Docker container (Streamable HTTP)

```bash
# Build and start the container
python scripts/docker.py start

# Add to Claude Code (use the port shown in the output)
claude mcp add google-drive --transport http http://localhost:19001/mcp
```

The Docker manager handles building the image, copying your OAuth credentials into the container volume, health checking, and port assignment. Manage the container with:

```bash
python scripts/docker.py status   # Check if running
python scripts/docker.py logs     # Tail container logs
python scripts/docker.py restart  # Restart without rebuild
python scripts/docker.py update   # Rebuild and restart (after code changes)
python scripts/docker.py stop     # Stop and remove container
```

**Prerequisites:** Docker Desktop (or Docker Engine on Linux)

### 4. Start using the tools

Once configured, you can ask your AI assistant to:
- "Search my Google Drive for budget reports"
- "Download the Q4 presentation as a PDF"
- "Upload this file to my Projects folder on Drive"
- "List the contents of my shared Documents folder"
- "Create a new folder called 'Archive' on my Drive"

## Available Tools

### search_files

Search for files on Google Drive by name or with structured Drive API queries.

**Parameters:**
- `query` (required, string): Search text or Drive API query string
- `max_results` (optional, int, default 20): Maximum results (1–100)
- `file_type` (optional, string): Filter by type — `document`, `spreadsheet`, `presentation`, `folder`, `pdf`, `image`, `video`, `audio`

### list_folder

List immediate contents of a Google Drive folder, with folders sorted first.

**Parameters:**
- `folder_id` (optional, string, default "root"): Folder ID to list
- `max_results` (optional, int, default 50): Maximum results (1–100)

### download_file

Download a file from Google Drive to the local filesystem. Google Workspace files (Docs, Sheets, Slides) are exported to the requested format.

**Parameters:**
- `file_id` (required, string): Google Drive file ID
- `local_path` (optional, string): Destination path. If empty, saves to `~/Downloads/google_drive/`
- `export_format` (optional, string): Export format for Workspace files — `pdf`, `docx`, `xlsx`, `csv`, `pptx`, `txt`, `html`

### upload_file

Upload a local file to Google Drive.

**Parameters:**
- `local_path` (required, string): Path to the local file
- `folder_id` (optional, string, default "root"): Destination folder ID on Drive
- `file_name` (optional, string): Override filename on Drive

### get_file_info

Get detailed metadata for a file (name, type, size, dates, owner, sharing, link, export formats).

**Parameters:**
- `file_id` (required, string): Google Drive file ID

### create_folder

Create a new folder on Google Drive.

**Parameters:**
- `folder_name` (required, string): Name for the new folder
- `parent_folder_id` (optional, string, default "root"): Parent folder ID

## Features

- Full-scope Google Drive access (search, browse, download, upload, organize)
- Automatic export of Google Workspace files (Docs → PDF/DOCX, Sheets → XLSX/CSV, etc.)
- Resumable uploads with configurable size limits
- Platform-aware default download directory (`~/Downloads/google_drive/`)
- Multi-transport support (STDIO, SSE, Streamable HTTP)
- Docker container support with lifecycle management script
- Automatic decorator-based exception handling, logging, and type conversion
- Unified logging with SQLite backend and correlation ID tracking

## Configuration

Configuration is stored at the platform-appropriate location:
- **macOS:** `~/Library/Application Support/google_drive/config.yaml`
- **Linux:** `~/.config/google_drive/config.yaml`
- **Windows:** `%APPDATA%\google_drive\config.yaml`

Key settings under the `google_drive:` section:
- `client_secret_path`: Override path to `client_secret.json`
- `max_upload_size_mb`: Upload size limit (default 500 MB)

Downloads go to `~/Downloads/google_drive/` by default (configurable).

## Troubleshooting

### Common Issues

1. **"client_secret.json not found" error**
   - Ensure you've downloaded OAuth credentials from Google Cloud Console
   - Place the file in the config directory shown by: `python -c "import platformdirs; print(platformdirs.user_config_dir('google_drive'))"`

2. **"Authorized user info was not in the expected format" error**
   - You may have copied `client_secret.json` as `token.json`. These are different files.
   - `client_secret.json` = your OAuth client credentials (you download this)
   - `token.json` = auto-generated after the OAuth flow completes
   - Rename the file to `client_secret.json` and run the OAuth flow

3. **"Access denied" errors**
   - Re-run the OAuth flow to refresh permissions
   - Ensure the Drive API is enabled in your Google Cloud project

4. **Tool not appearing in your AI assistant**
   - Verify the MCP server is registered: `claude mcp list`
   - Restart your AI assistant after adding the server

## Development

```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit/ -v

# Run integration tests (tests both STDIO and Streamable HTTP transports)
uv run pytest tests/integration/ -v

# Start MCP Inspector for manual testing
uv run mcp dev google_drive/server/app.py
```

For development setup and contribution guidelines, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Requirements

- **Direct install:** Python 3.11 or 3.12, [uv](https://docs.astral.sh/uv/)
- **Docker:** Docker Desktop (macOS/Windows) or Docker Engine (Linux)
- **All methods:** Google Cloud project with Drive API enabled and OAuth2 client credentials
- Operating Systems: Linux, macOS, Windows

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Author

Tim Kitchens - codingthefuturewithai@gmail.com
