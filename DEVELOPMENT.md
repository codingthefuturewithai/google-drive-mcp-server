# Development Guide

This guide covers development practices, architecture, and contribution guidelines for the Google Drive MCP Server.

## Development Setup

### Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- Git for version control

### Initial Setup

1. **Clone and install:**
   ```bash
   git clone <repository-url>
   cd google_drive
   uv sync
   ```

2. **Verify installation:**
   ```bash
   # Run the test suite
   uv run pytest -v

   # Start MCP Inspector
   uv run mcp dev google_drive/server/app.py

   # Run server directly
   uv run python -m google_drive --help
   ```

3. **Set up Google credentials** (for live testing):
   ```bash
   # Place your OAuth client credentials
   cp /path/to/client_secret.json "$(python -c "import platformdirs; print(platformdirs.user_config_dir('google_drive'))")/client_secret.json"

   # Run OAuth flow
   uv run python -c "from google_drive.auth import get_credentials; import platformdirs; get_credentials(platformdirs.user_config_dir('google_drive'))"
   ```

## Architecture Overview

### Core Components

- **Server (`server/app.py`)**: FastMCP server with multi-transport support (STDIO, SSE, Streamable HTTP)
- **Auth (`auth/google_auth.py`)**: OAuth2 authentication — token caching, refresh, and flow
- **Drive Service (`drive/service.py`)**: Async wrapper around Google Drive API v3
- **Tools (`tools/`)**: 6 Google Drive tool implementations
- **Decorators (`decorators/`)**: Automatic exception handling, logging, and type conversion
- **Log System (`log_system/`)**: Unified logging with SQLite backend and correlation ID tracking
- **Config (`config.py`)**: Platform-aware configuration with `platformdirs`

### Project Structure

```
google_drive/
├── google_drive/                    # Main package
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py                    # ServerConfig with platformdirs paths
│   ├── logging_config.py            # Traditional logging setup
│   │
│   ├── server/                      # MCP server implementation
│   │   └── app.py                   # FastMCP server, tool registration
│   │
│   ├── auth/                        # Google OAuth2 authentication
│   │   ├── __init__.py
│   │   └── google_auth.py           # get_credentials, build_drive_service
│   │
│   ├── drive/                       # Google Drive API service layer
│   │   ├── __init__.py
│   │   └── service.py               # DriveService class, get_drive_service
│   │
│   ├── tools/                       # Tool implementations
│   │   ├── __init__.py              # Combines tool lists into drive_tools
│   │   ├── search_tools.py          # search_files, list_folder
│   │   ├── transfer_tools.py        # download_file, upload_file
│   │   ├── metadata_tools.py        # get_file_info
│   │   └── folder_tools.py          # create_folder
│   │
│   ├── decorators/                  # Function decorators
│   │   ├── exception_handler.py     # Error handling
│   │   ├── tool_logger.py           # Request logging with correlation IDs
│   │   ├── type_converter.py        # Parameter type conversion
│   │   └── parallelize.py           # Async parallelization
│   │
│   ├── log_system/                  # Unified logging system
│   │   ├── correlation.py           # Correlation ID management
│   │   ├── unified_logger.py        # Main logger interface
│   │   └── destinations/            # Log destinations
│   │       ├── base.py              # Base destination class
│   │       ├── factory.py           # Destination factory
│   │       └── sqlite.py            # SQLite log destination
│   │
│   ├── client/                      # Test client
│   │   └── app.py                   # STDIO test client
│   │
│   └── ui/                          # Streamlit web interface (optional)
│       ├── app.py
│       ├── lib/
│       └── pages/
│
├── tests/                           # Test suite
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_auth.py
│   │   ├── test_drive_service.py
│   │   ├── test_search_tools.py
│   │   ├── test_transfer_tools.py
│   │   ├── test_metadata_tools.py
│   │   ├── test_folder_tools.py
│   │   └── test_decorators.py
│   └── integration/
│       ├── conftest.py              # mcp_session fixture (STDIO + HTTP)
│       └── test_drive_tools_integration.py
│
├── pyproject.toml                   # Package configuration
├── README.md                        # User documentation
├── CLAUDE.md                        # Claude Code guidance
├── DEVELOPER_GUIDE.md               # Developer quick-start
└── DEVELOPMENT.md                   # This file
```

### Design Patterns

#### 1. Decorator Pattern
All tools are automatically decorated in `server/app.py:register_tools()`:
```python
# Applied to every tool:
decorated = exception_handler(tool_logger(type_converter(func), config.__dict__))
```

#### 2. Lazy Singleton Pattern
Both configuration and Drive service use lazy-initialized singletons:
```python
from google_drive.config import get_config        # ServerConfig singleton
from google_drive.drive import get_drive_service   # DriveService singleton
```

#### 3. HttpError Translation
`DriveService._handle_http_error()` translates Google API errors to standard Python exceptions:
- 404 → `FileNotFoundError`
- 403 → `PermissionError`
- Others → `RuntimeError`

#### 4. Correlation ID Pattern
All requests are tracked with unique correlation IDs (`req_xxxxxxxxxxxx`):
- Generated per tool invocation by `tool_logger`
- Propagated via `contextvars.ContextVar`
- Logged to SQLite for tracing

## Adding New Tools

### Tool Structure

```python
# google_drive/tools/my_tools.py
import logging
from mcp.server.fastmcp import Context
from google_drive.drive import get_drive_service

logger = logging.getLogger(__name__)

async def my_tool(
    param1: str,
    param2: int = 10,       # Use defaults, never Optional
    ctx: Context = None      # Always include
) -> str:
    """Tool description — becomes the MCP tool description."""
    service = get_drive_service()
    result = await service.some_method(param1)
    return f"Result: {result}"

# Export tool list
my_tools = [my_tool]
```

### Registration

Add to `google_drive/tools/__init__.py`:
```python
from .my_tools import my_tools

drive_tools = search_tools + transfer_tools + metadata_tools + folder_tools + my_tools
```

No changes to `server/app.py` needed — it iterates `drive_tools` automatically.

### Critical Rules

1. **Never use `Optional[X]`** for parameters — breaks MCP clients
2. **Return `str`**, not `Dict` — text-only responses
3. **Always include `ctx: Context = None`** as the last parameter
4. **Always be async** — all tools must be `async def`

## Testing Guidelines

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests only (tests STDIO + Streamable HTTP transports)
uv run pytest tests/integration/ -v

# Specific test file
uv run pytest tests/unit/test_search_tools.py -v

# Specific test by name
uv run pytest -k "test_search_files_formatted_output" -v
```

### Writing Unit Tests

Unit tests mock `get_drive_service()` at the tool module level:

```python
# tests/unit/test_my_tools.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_service():
    service = MagicMock()
    service.some_method = AsyncMock(return_value={"key": "value"})
    return service

@patch("google_drive.tools.my_tools.get_drive_service")
@pytest.mark.asyncio
async def test_my_tool(mock_get_service, mock_service):
    mock_get_service.return_value = mock_service

    result = await my_tool("test_param")

    assert "Result" in result
    mock_service.some_method.assert_called_once_with("test_param")
```

### Writing Integration Tests

Integration tests use the `mcp_session` fixture to verify tools work through the MCP protocol:

```python
# tests/integration/test_my_tools_integration.py
import pytest
from tests.integration.conftest import extract_text_content

class TestMyToolIntegration:
    @pytest.mark.asyncio
    async def test_tool_discoverable(self, mcp_session):
        tools_result = await mcp_session.list_tools()
        tool_names = [t.name for t in tools_result.tools]
        assert "my_tool" in tool_names

    @pytest.mark.asyncio
    async def test_tool_schema(self, mcp_session):
        tools_result = await mcp_session.list_tools()
        tool = next(t for t in tools_result.tools if t.name == "my_tool")
        props = tool.inputSchema.get("properties", {})
        assert "param1" in props
```

## Debugging and Development Tools

### MCP Inspector

```bash
uv run mcp dev google_drive/server/app.py
# Opens at http://localhost:6274
```

### Server Transports

```bash
# STDIO (default, for MCP clients like Claude Code)
uv run python -m google_drive

# Streamable HTTP
uv run python -m google_drive.server.app --transport streamable-http --port 3001

# SSE
uv run python -m google_drive.server.app --transport sse --port 3001
```

### Log Locations

- **SQLite database**: `~/Library/Application Support/google_drive/unified_logs.db` (macOS)
- **Text logs**: `~/Library/Logs/google_drive/google_drive.log` (macOS)

Use `platformdirs` paths for Linux/Windows equivalents.

## Contribution Guidelines

### Code Standards

1. Follow PEP 8 style guidelines
2. Use type hints for all functions
3. Write descriptive docstrings
4. Add tests for new functionality
5. Tools return `str`, never `Dict`

### Git Workflow

1. Create feature branch: `git checkout -b feature/my-new-tool`
2. Make changes with good commit messages
3. Run tests: `uv run pytest`
4. Push and create PR

### Commit Message Format

Use conventional commit format:
- `feat:` new features
- `fix:` bug fixes
- `docs:` documentation changes
- `test:` adding tests
- `refactor:` code refactoring
