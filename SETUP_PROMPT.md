# Google Drive MCP Server - Quick Setup Guide

Quick setup instructions for using this MCP server with AI assistants.

## Quick Setup

### Installation

```bash
# Clone and install
git clone <repository-url>
cd google_drive
uv sync
```

### Google Credentials Setup (required for both direct and Docker)

```bash
# Place your OAuth client credentials in the config directory
cp /path/to/client_secret.json "$(python -c "import platformdirs; print(platformdirs.user_config_dir('google_drive'))")/client_secret.json"

# Run OAuth flow (opens browser for Google sign-in)
uv run python -c "from google_drive.auth import get_credentials; import platformdirs; get_credentials(platformdirs.user_config_dir('google_drive'))"
```

### Option A: Run directly (STDIO)

```bash
claude mcp add google-drive -- uv run --directory /path/to/google_drive python -m google_drive
```

### Option B: Run via Docker container (Streamable HTTP)

```bash
# Build, copy credentials, and start
python scripts/docker.py start

# Add to Claude Code
claude mcp add google-drive --transport http http://localhost:19001/mcp
```

## Key Commands

### Server Commands (Direct)
```bash
# Start server (stdio - default)
uv run python -m google_drive

# Start with SSE transport
uv run python -m google_drive.server.app --transport sse --port 3001

# Start with streamable HTTP transport
uv run python -m google_drive.server.app --transport streamable-http --host 0.0.0.0 --port 3001
```

### Docker Commands
```bash
python scripts/docker.py start     # Build and start container
python scripts/docker.py stop      # Stop and remove container
python scripts/docker.py restart   # Restart without rebuild
python scripts/docker.py update    # Rebuild and restart (after code changes)
python scripts/docker.py status    # Show container status
python scripts/docker.py logs      # Tail container logs
```

### Testing Commands
```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit/ -v

# Run integration tests only
uv run pytest tests/integration/ -v

# Run with coverage
uv run pytest --cov=google_drive
```

### Development Tools
```bash
# MCP Inspector (interactive testing)
uv run mcp dev google_drive/server/app.py
```

## Important Files

### Core Server Files
- **`server/app.py`**: FastMCP server with multi-transport support and tool registration
- **`auth/google_auth.py`**: OAuth2 authentication (token caching, refresh, flow)
- **`drive/service.py`**: Async Drive API wrapper (DriveService, get_drive_service)
- **`config.py`**: Platform-aware configuration management

### Tool Implementations
- **`tools/search_tools.py`**: `search_files`, `list_folder`
- **`tools/transfer_tools.py`**: `download_file`, `upload_file`
- **`tools/metadata_tools.py`**: `get_file_info`
- **`tools/folder_tools.py`**: `create_folder`

### Infrastructure
- **`decorators/`**: 4 decorators (exception_handler, tool_logger, type_converter, parallelize)
- **`log_system/`**: Unified logging with SQLite backend and correlation IDs
- **`tests/`**: Unit and integration test suite

## Available Tools (6 total)

| Tool | Purpose |
|------|---------|
| **search_files** | Search for files by name or with structured Drive API queries |
| **list_folder** | List contents of a Google Drive folder |
| **download_file** | Download files to local filesystem (with Workspace export support) |
| **upload_file** | Upload local files to Google Drive |
| **get_file_info** | Get detailed metadata for a file |
| **create_folder** | Create a new folder on Google Drive |

## Architecture Overview

### Transport Support
- **STDIO**: Default, for MCP clients like Claude Code and Claude Desktop
- **SSE**: Server-Sent Events for web clients
- **Streamable HTTP**: HTTP streaming for modern clients

### Decorator Chain
Applied automatically to all tools during registration:
1. **type_converter**: Parameter type conversion (strings to proper types)
2. **tool_logger**: Request logging with correlation IDs
3. **exception_handler**: Error handling and logging

### Key Patterns
- **Tools return `str`** — text-only responses, never `Dict`
- **Never use `Optional[X]`** for parameters — breaks MCP clients
- **Always include `ctx: Context = None`** — enables correlation ID support
- **`asyncio.to_thread()`** — wraps synchronous Google API calls

## Configuration

Configuration is stored at platform-appropriate locations:
- **macOS**: `~/Library/Application Support/google_drive/config.yaml`
- **Linux**: `~/.config/google_drive/config.yaml`
- **Windows**: `%APPDATA%\google_drive\config.yaml`

Key settings under the `google_drive:` section:
- `client_secret_path`: Override path to `client_secret.json`
- `max_upload_size_mb`: Upload size limit (default 500 MB)

Downloads go to `~/Downloads/google_drive/` by default.

## Troubleshooting

### "client_secret.json not found"
- Download OAuth credentials from Google Cloud Console
- Place in config directory (see setup commands above)

### "Authorized user info was not in the expected format"
- You may have copied `client_secret.json` as `token.json` — these are different files
- `client_secret.json` = your OAuth client credentials (you download this)
- `token.json` = auto-generated after the OAuth flow completes

### Tool not appearing
- Verify MCP server is registered: `claude mcp list`
- Restart your AI assistant after adding the server
