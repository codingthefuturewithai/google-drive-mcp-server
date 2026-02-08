# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python MCP (Model Context Protocol) server for Google Drive using FastMCP with a **decorator pattern** for automatic tool enhancement. Provides 6 tools that let AI assistants search, browse, download, upload, inspect, and organize files on Google Drive. Binary content never enters the MCP protocol — files are transferred to/from the local filesystem.

## Build & Run Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_search_tools.py -v

# Run only unit tests
uv run pytest tests/unit/ -v

# Run only integration tests
uv run pytest tests/integration/ -v

# Run single test by name
uv run pytest -k "test_search_files" -v

# Start MCP Inspector for manual testing
uv run mcp dev google_drive/server/app.py

# Run server directly (stdio transport, default)
uv run python -m google_drive

# Run server with specific transport
uv run python -m google_drive.server.app --transport sse --port 3001
uv run python -m google_drive.server.app --transport streamable-http --port 3001

# Docker container (streamable HTTP on port 19001)
python scripts/docker.py start    # Build, copy creds, start
python scripts/docker.py update   # Rebuild and restart after code changes
python scripts/docker.py stop     # Stop container
```

## Architecture

### Decorator-Based Tool Registration

Tools are NOT registered with `@mcp.tool()` directly. Instead:

1. Write a plain `async def` in a file under `google_drive/tools/`
2. Export it in a list (e.g., `search_tools = [search_files, list_folder]`)
3. Import that list in `google_drive/tools/__init__.py` and add to `drive_tools`
4. `register_tools()` in `server/app.py` applies the decorator chain and calls `mcp_server.tool()` automatically

**Decorator chain order** (applied in `server/app.py:register_tools`):
- All tools: `exception_handler(tool_logger(type_converter(func)))`

### Google Drive Tools (6 total)

| Tool | File | Purpose |
|------|------|---------|
| `search_files` | `tools/search_tools.py` | Search by name or Drive API query |
| `list_folder` | `tools/search_tools.py` | List folder contents |
| `download_file` | `tools/transfer_tools.py` | Download/export files to local filesystem |
| `upload_file` | `tools/transfer_tools.py` | Upload local files to Drive |
| `get_file_info` | `tools/metadata_tools.py` | Get detailed file metadata |
| `create_folder` | `tools/folder_tools.py` | Create folders on Drive |

### Key Decorators (`google_drive/decorators/`)

- **`type_converter`** — Converts string params to proper Python types (int, float, bool, List, Dict) since some MCP clients send everything as strings. Preserves function signature.
- **`tool_logger`** — Generates correlation IDs per request, logs tool start/complete/fail with timing to UnifiedLogger.
- **`exception_handler`** — Catches exceptions, logs with traceback, then re-raises for MCP to handle.
- **`parallelize`** — Transforms signature to accept `List[Dict]` for batch execution via `asyncio.gather`. Not currently used by any Drive tools.

### Authentication (`google_drive/auth/`)

- `get_credentials(config_dir)` — Loads cached token, refreshes if expired, runs OAuth flow if needed
- `build_drive_service(config_dir)` — Builds the Google Drive API v3 service
- Token stored at `{config_dir}/token.json`, client secret at `{config_dir}/client_secret.json`

### Drive Service Layer (`google_drive/drive/`)

- `DriveService` — Async wrapper around the synchronous Google Drive API client
- All API calls wrapped with `asyncio.to_thread()` for non-blocking execution
- `_handle_http_error()` translates `HttpError` to standard Python exceptions (404→FileNotFoundError, 403→PermissionError)
- Lazy-initialized singleton via `get_drive_service()`

### Unified Logging System (`google_drive/log_system/`)

- **`UnifiedLogger`** — Singleton factory that intercepts both Loguru and stdlib logging, routes to pluggable destinations via `LogDestination` interface.
- **`correlation.py`** — Thread-safe correlation ID management using `contextvars.ContextVar`. Each tool invocation gets a unique ID.
- **`destinations/`** — Pluggable backends. SQLite is the default (`destinations/sqlite.py`). New destinations extend `LogDestination` ABC and register via `LogDestinationFactory`.

### Configuration (`google_drive/config.py`)

- `ServerConfig` dataclass with platform-aware paths via `platformdirs`
- YAML config file at `platformdirs.user_config_dir("google_drive")/config.yaml`
- Google Drive fields: `google_client_secret_path`, `max_upload_size_mb`, `download_dir`
- Default download directory: `~/Downloads/google_drive/`
- `get_config()` returns global singleton

### Server Entry Points (`pyproject.toml [project.scripts]`)

- `google_drive-server` — Main entry (default stdio)
- `google_drive-server-stdio`, `google_drive-server-http`, `google_drive-server-sse` — Transport-specific

## Tool Function Conventions

```python
async def my_tool(
    required_param: str,
    optional_param: int = 10,    # Use defaults, NEVER Optional
    ctx: Context = None          # Always include for MCP runtime
) -> str:
    """Docstring becomes the MCP tool description."""
    return "Text response to the user"
```

**Critical rules**:
- Never use `Optional[X]` for parameters — it breaks MCP clients. Use default values instead (e.g., `param: str = ""`).
- Tools return `str`, not `Dict` — text-only responses per project convention.

## Testing

- **Unit tests** mock `get_drive_service()` at the tool module level (e.g., `@patch("google_drive.tools.search_tools.get_drive_service")`)
- **Integration tests** use the `mcp_session` fixture from `tests/integration/conftest.py` which is parameterized to test across both STDIO and Streamable HTTP transports automatically
- Helper functions `extract_text_content()` and `extract_error_text()` in integration conftest for parsing MCP results
- Coverage config in `.coveragerc` with subprocess coverage support (`parallel = true`, `concurrency = multiprocessing`)
- pytest config in `pyproject.toml` with default coverage flags

## Project Structure

```
google_drive/
├── server/app.py          # FastMCP server, tool registration, transport handling
├── auth/                  # OAuth2 authentication (get_credentials, build_drive_service)
│   └── google_auth.py
├── drive/                 # Drive API service layer (DriveService, get_drive_service)
│   └── service.py
├── tools/                 # Tool implementations
│   ├── search_tools.py    # search_files, list_folder
│   ├── transfer_tools.py  # download_file, upload_file
│   ├── metadata_tools.py  # get_file_info
│   └── folder_tools.py    # create_folder
├── decorators/            # exception_handler, tool_logger, type_converter, parallelize
├── log_system/            # UnifiedLogger, correlation IDs, destination plugins
├── config.py              # ServerConfig with platformdirs paths
├── logging_config.py      # Traditional logging setup (stderr + rotating file)
├── ui/                    # Streamlit admin UI (optional, `pip install .[ui]`)
└── client/app.py          # MCP client for testing
```

## Claude Code Slash Commands

- `/add-tool "description"` — Guided tool creation with planning step
- `/generate-tests tool_name` — Auto-generate integration + unit tests
- `/getting-started` — Interactive onboarding tutorial
- `/remove-examples` — Remove all example tools for production
