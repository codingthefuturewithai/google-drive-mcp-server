# Decorator Patterns in Google Drive MCP Server

This document explains the decorator patterns used in the server and provides guidance on async patterns and tool conventions.

## Overview

The MCP server automatically applies decorators to all tools. These decorators follow strict async-only patterns and provide:
- **Exception handling**: Standard error responses
- **Logging**: Comprehensive execution tracking with SQLite persistence
- **Type conversion**: Automatic parameter type coercion
- **Parallelization**: Concurrent execution with signature transformation (available but not used by current Drive tools)

## Async-Only Pattern

**All tools must be async functions.** The decorators only support async functions.

```python
# CORRECT - Async function
async def my_tool(param: str, ctx: Context = None) -> str:
    return f"Result: {param.upper()}"

# INCORRECT - Sync function (will cause errors)
def my_tool(param: str) -> str:
    return f"Result: {param.upper()}"
```

## The Three Core Decorators

### 1. Exception Handler (Applied to ALL tools)

The exception handler ensures consistent error handling:

```python
async def my_tool(param: str, ctx: Context = None) -> str:
    if not param:
        raise ValueError("Parameter required")
    return f"Result: {param.upper()}"
```

**What it does:**
- Catches any exception thrown by your tool
- Logs the error with full stack trace
- Re-raises for MCP to handle
- Your tool can raise exceptions freely

### 2. Tool Logger (Applied to ALL tools)

Tracks execution metrics and logs all tool invocations to SQLite database.

**Context Parameter Requirement:**

For correlation IDs to work properly, all tools MUST include a `ctx: Context = None` parameter:

```python
from mcp.server.fastmcp import Context

# CORRECT - Includes Context parameter
async def my_tool(param: str, ctx: Context = None) -> str:
    return "processed"

# INCORRECT - Missing Context parameter (correlation IDs won't work)
async def my_tool(param: str) -> str:
    return "processed"
```

The Context parameter:
- Must be imported from `mcp.server.fastmcp`
- Should be the last parameter in the function signature
- Should have a default value of `None`
- Will be automatically provided by the MCP runtime when available

**What it logs:**
- Correlation ID (client-provided or auto-generated)
- Tool name and parameters
- Execution time in milliseconds
- Success/failure status
- Output summary (first 500 chars)
- Error messages and stack traces

### 3. Type Converter (Applied to ALL tools)

Converts string parameters to proper Python types since some MCP clients send everything as strings:

```python
# Even if the client sends max_results as "20" (string),
# your tool receives it as int 20
async def search_files(
    query: str,
    max_results: int = 20,
    ctx: Context = None
) -> str:
    # max_results is guaranteed to be an int here
    ...
```

### 4. Parallelize (Available, not currently used)

The parallelize decorator transforms a function signature to accept `List[Dict]` for batch execution via `asyncio.gather`. It is not currently applied to any Drive tools but is available for future use.

## How Tools Are Registered

The server's `register_tools()` in `server/app.py` automatically applies decorators:

```python
# For all Drive tools:
# type_converter → tool_logger → exception_handler
decorated = exception_handler(tool_logger(type_converter(func), config.__dict__))
mcp_server.tool(name=tool_name)(decorated)
```

## Adding New Tools

### To the Drive tools list

```python
# google_drive/tools/my_tools.py
from mcp.server.fastmcp import Context
from google_drive.drive import get_drive_service

async def my_tool(param: str, ctx: Context = None) -> str:
    """A tool with automatic exception handling, logging, and type conversion."""
    service = get_drive_service()
    result = await service.some_method(param)
    return f"Result: {result}"

# Export as a list
my_tools = [my_tool]
```

Then add to `google_drive/tools/__init__.py`:
```python
from .my_tools import my_tools

drive_tools = search_tools + transfer_tools + metadata_tools + folder_tools + my_tools
```

No changes to `server/app.py` needed.

## Common Patterns

### Pattern 1: Drive API Tool with Error Handling

```python
from mcp.server.fastmcp import Context
from google_drive.drive import get_drive_service

async def my_drive_tool(file_id: str, ctx: Context = None) -> str:
    """Operate on a Drive file."""
    service = get_drive_service()
    # DriveService translates HttpError to FileNotFoundError/PermissionError
    # Exception handler catches and logs any errors
    metadata = await service.get_metadata(file_id)
    return f"File: {metadata['name']}"
```

### Pattern 2: Tool with Default Parameters

```python
async def search_with_defaults(
    query: str,
    max_results: int = 20,   # Default value, never Optional
    file_type: str = "",       # Empty string instead of None
    ctx: Context = None
) -> str:
    """Search with sensible defaults."""
    service = get_drive_service()
    results = await service.search(query, max_results, file_type)
    return format_results(results)
```

### Pattern 3: Tool with Local Filesystem Interaction

```python
from pathlib import Path
from google_drive.config import get_config

async def download_tool(file_id: str, local_path: str = "", ctx: Context = None) -> str:
    """Download a file to local filesystem."""
    if not local_path:
        config = get_config()
        local_path = str(config.download_dir / "filename.pdf")

    service = get_drive_service()
    await service.download(file_id, local_path)
    return f"Downloaded to {local_path}"
```

## Best Practices

1. **Always include Context parameter** — Required for correlation ID support
2. **Return `str`** — All tools return formatted text, never `Dict`
3. **Never use `Optional[X]`** — Use default values instead (empty string, 0, etc.)
4. **Let exceptions bubble up** — The exception handler will catch them
5. **Use type hints** — Helps with type_converter and documentation
6. **Log important operations** — Use the standard logging module
7. **Test with MCP Inspector** — Verify parameters and outputs

## Debugging

1. **Check MCP Inspector Output** — Parameters should show proper names (not "kwargs")
2. **Enable Debug Logging** — `uv run python -m google_drive.server.app --transport stdio`
3. **Check SQLite Logs** — Located at `platformdirs.user_data_dir("google_drive")/unified_logs.db`
