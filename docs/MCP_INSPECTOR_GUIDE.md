# MCP Inspector Testing Guide

This guide helps you test the Google Drive MCP server tools using the MCP Inspector.

## Prerequisites

### 1. Virtual Environment Setup

**CRITICAL**: Always ensure you're using the virtual environment's MCP, not any global installation.

```bash
# From your project root
cd google_drive

# Activate your virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows

# Verify MCP is using the correct version
which mcp
# Should show: /path/to/google_drive/.venv/bin/mcp
# NOT: /opt/homebrew/bin/mcp or /usr/local/bin/mcp
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Google Credentials (for live testing)

To test tools against real Google Drive, you'll need OAuth credentials set up. See the main [README.md](../README.md) for instructions.

Without credentials, the server starts but tools will fail with authentication errors when called.

## Launching MCP Inspector

### STDIO Transport (Default)

```bash
uv run mcp dev google_drive/server/app.py
```

You should see:
- Server logs showing tool registration (6 Drive tools)
- SQLite database initialization
- Inspector URL: http://127.0.0.1:6274

Open the Inspector URL in your browser.

### Other Transports

The `mcp dev` command always uses STDIO transport. To test other transports, run the server directly:

```bash
# SSE Transport
uv run python -m google_drive.server.app --transport sse --port 3001

# Streamable HTTP Transport
uv run python -m google_drive.server.app --transport streamable-http --port 3001
```

### Transport Comparison

| Transport | Use Case | Endpoint |
|-----------|----------|----------|
| STDIO | Desktop clients (Claude Code, Claude Desktop) | N/A |
| SSE | Web clients (legacy) | Multiple endpoints |
| Streamable HTTP | Modern web clients | Single `/mcp` endpoint |

## Testing Google Drive Tools

### 1. search_files

**Purpose**: Search for files on Google Drive by name or with structured Drive API queries.

**Parameters**:
- `query` (required): Search text or Drive API query string
- `max_results` (optional, default 20): Maximum results (1-100)
- `file_type` (optional): Filter by type — `document`, `spreadsheet`, `presentation`, `folder`, `pdf`, `image`, `video`, `audio`

**Test Examples**:
```
query: "budget report"
→ Searches for files containing "budget report"

query: "quarterly review"
file_type: "spreadsheet"
→ Searches for spreadsheets matching "quarterly review"

query: "name contains 'invoice'"
→ Passes through as a structured Drive API query
```

### 2. list_folder

**Purpose**: List immediate contents of a Google Drive folder, with folders sorted first.

**Parameters**:
- `folder_id` (optional, default "root"): Folder ID to list
- `max_results` (optional, default 50): Maximum results (1-100)

**Test Examples**:
```
(no parameters) → Lists root Drive folder contents

folder_id: "root"
max_results: 10
→ Lists first 10 items in root folder
```

### 3. download_file

**Purpose**: Download a file from Google Drive to the local filesystem. Google Workspace files are exported to the requested format.

**Parameters**:
- `file_id` (required): Google Drive file ID
- `local_path` (optional): Destination path. If empty, saves to `~/Downloads/google_drive/`
- `export_format` (optional): Export format for Workspace files — `pdf`, `docx`, `xlsx`, `csv`, `pptx`, `txt`, `html`

**Test Examples**:
```
file_id: "<a-valid-file-id>"
→ Downloads to ~/Downloads/google_drive/

file_id: "<a-google-doc-id>"
export_format: "pdf"
→ Exports Google Doc as PDF

file_id: "<a-file-id>"
local_path: "/tmp/test_download.pdf"
→ Downloads to specific path
```

### 4. upload_file

**Purpose**: Upload a local file to Google Drive.

**Parameters**:
- `local_path` (required): Path to the local file
- `folder_id` (optional, default "root"): Destination folder ID on Drive
- `file_name` (optional): Override filename on Drive

**Test Examples**:
```
local_path: "/path/to/some/file.pdf"
→ Uploads to root of Drive

local_path: "/path/to/report.xlsx"
folder_id: "<target-folder-id>"
file_name: "Q4_Report.xlsx"
→ Uploads with custom name to specific folder
```

### 5. get_file_info

**Purpose**: Get detailed metadata for a file (name, type, size, dates, owner, sharing, link, export formats).

**Parameters**:
- `file_id` (required): Google Drive file ID

**Test Examples**:
```
file_id: "<a-valid-file-id>"
→ Returns formatted metadata (name, MIME type, size, dates, owner, permissions, etc.)
```

### 6. create_folder

**Purpose**: Create a new folder on Google Drive.

**Parameters**:
- `folder_name` (required): Name for the new folder
- `parent_folder_id` (optional, default "root"): Parent folder ID

**Test Examples**:
```
folder_name: "Test Folder"
→ Creates folder in root Drive

folder_name: "Subfolder"
parent_folder_id: "<parent-folder-id>"
→ Creates folder inside another folder
```

## Testing Error Handling

The decorators provide comprehensive error handling. Test these scenarios:

1. **File not found**: Use an invalid `file_id` like `"nonexistent_id_12345"` with `get_file_info` or `download_file`

2. **Invalid parameters**: Leave required fields empty or provide invalid values

3. **Upload validation**: Try uploading a non-existent file path or a directory path

## Viewing Logs

### Log Locations

**SQLite Database** (tool execution history):
- macOS: `~/Library/Application Support/google_drive/unified_logs.db`
- Linux: `~/.local/share/google_drive/unified_logs.db`
- Windows: `%LOCALAPPDATA%\google_drive\unified_logs.db`

**Text Logs**:
- macOS: `~/Library/Logs/google_drive/google_drive.log`
- Linux: `~/.local/state/google_drive/logs/google_drive.log`
- Windows: `%LOCALAPPDATA%\google_drive\logs\google_drive.log`

### Viewing Logs in Admin UI

```bash
streamlit run google_drive/ui/app.py
```

Navigate to the "Logs" page to see tool execution history, success/failure rates, and performance metrics.

## Common Issues

### ModuleNotFoundError

If you see `ModuleNotFoundError: No module named 'google_drive'`:
1. Ensure you're in the project root directory
2. Check virtual environment is activated: `which python`
3. Reinstall: `uv sync`
4. Use full mcp path: `.venv/bin/mcp dev google_drive/server/app.py`

### MCP Inspector Not Loading

1. Check server started without errors
2. Check if port 6274 is already in use
3. Clear browser cache and refresh

### Tools Not Appearing

1. Check server logs for registration messages (should show 6 Drive tools)
2. Refresh the Inspector page
3. Verify no import errors in terminal

### Authentication Errors When Calling Tools

1. Ensure `client_secret.json` is in the config directory
2. Run the OAuth flow to generate `token.json`
3. See [README.md](../README.md) troubleshooting section for details
