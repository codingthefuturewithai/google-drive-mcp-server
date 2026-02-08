# Developer Guide - Google Drive MCP Server

This guide is for developers extending this MCP server with new tools or features.

## Quick Navigation

**First time with this server?** Start with [Understanding the Architecture](#understanding-the-architecture)

**Adding a new tool?** Jump to [Adding New Tools](#adding-new-tools)

**Running tests?** See [Testing Your Tools](#testing-your-tools)

---

## Understanding the Architecture

### What Makes This Server Special

This isn't a typical MCP server. It uses a **decorator pattern** which automatically adds:
- **Exception handling** — All errors are caught and returned cleanly
- **Logging** — Every tool execution is logged to SQLite with correlation IDs
- **Type conversion** — MCP sends strings, your tools get proper types

### How Tools Are Registered

Unlike most MCP servers where you use `@mcp.tool` on each function, here:

1. You write a plain async function in `google_drive/tools/`
2. Add it to a list (e.g., `my_tools = [func1, func2]`)
3. Import that list in `google_drive/tools/__init__.py` and add to `drive_tools`
4. The server automatically applies all decorators during registration

**Why?** This ensures consistent error handling and logging across all tools.

### Current Tools

The server provides 6 Google Drive tools:

| Tool | File | Purpose |
|------|------|---------|
| `search_files` | `search_tools.py` | Search by name or Drive API query |
| `list_folder` | `search_tools.py` | List folder contents |
| `download_file` | `transfer_tools.py` | Download/export files to local filesystem |
| `upload_file` | `transfer_tools.py` | Upload local files to Drive |
| `get_file_info` | `metadata_tools.py` | Get detailed file metadata |
| `create_folder` | `folder_tools.py` | Create folders on Drive |

---

## Adding New Tools

### Method 1: Claude Code Commands (Recommended)

```bash
# In Claude Code
/add-tool "description of what you want"

# Example:
/add-tool "move a file to a different folder on Drive"
```

This command will:
1. Research any needed libraries
2. Create a detailed implementation plan
3. Wait for your approval
4. Generate the tool with proper typing
5. Register it in the server
6. Help you test it in MCP Inspector

### Method 2: Manual Tool Creation

1. **Create your tool file**:
```python
# google_drive/tools/my_tools.py
from mcp.server.fastmcp import Context

async def my_tool(
    param1: str,
    param2: int = 10,  # Use defaults, never Optional
    ctx: Context = None
) -> str:
    """Tool description for MCP."""
    # Your implementation
    return f"Processed {param1} with {param2}"

# Export your tools
my_tools = [my_tool]
```

2. **Register in `google_drive/tools/__init__.py`**:
```python
from .my_tools import my_tools

drive_tools = search_tools + transfer_tools + metadata_tools + folder_tools + my_tools
```

That's it! The decorators are applied automatically in `server/app.py`.

### Critical Rules for Tools

**NEVER use Optional parameters** — they break MCP clients:
```python
# WRONG
async def bad_tool(text: Optional[str] = None): ...

# CORRECT
async def good_tool(text: str = ""): ...
```

**Tools return `str`**, not `Dict`:
```python
# WRONG
async def bad_tool(file_id: str, ctx: Context = None) -> Dict[str, Any]:
    return {"result": "data"}

# CORRECT
async def good_tool(file_id: str, ctx: Context = None) -> str:
    return "Result: data"
```

**Always include `ctx: Context = None`** as the last parameter.

---

## Testing Your Tools

### Generating Tests Automatically

```bash
# In Claude Code
/generate-tests my_tool

# This creates:
# - Integration tests (MCP protocol testing)
# - Unit tests (with mocked dependencies)
```

### Manual Testing with MCP Inspector

```bash
# Start the inspector
uv run mcp dev google_drive/server/app.py

# Opens at http://localhost:6274
# 1. Click "Connect" (left side)
# 2. Click "Tools" → "List Tools"
# 3. Find your tool and test it
```

### Running the Test Suite

```bash
# Run all tests
uv run pytest

# Run only unit tests
uv run pytest tests/unit/ -v

# Run only integration tests
uv run pytest tests/integration/ -v

# Run with coverage report
uv run pytest --cov=google_drive --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_search_tools.py -v
```

---

## Project Structure

```
google_drive/
├── server/
│   └── app.py              # Main server - imports and registers tools
├── auth/
│   └── google_auth.py      # OAuth2 authentication
├── drive/
│   └── service.py          # Drive API service layer
├── tools/
│   ├── __init__.py          # Combines all tool lists into drive_tools
│   ├── search_tools.py      # search_files, list_folder
│   ├── transfer_tools.py    # download_file, upload_file
│   ├── metadata_tools.py    # get_file_info
│   └── folder_tools.py      # create_folder
├── decorators/              # exception_handler, tool_logger, type_converter, parallelize
├── log_system/              # UnifiedLogger, correlation IDs, destination plugins
├── config.py                # ServerConfig with platformdirs paths
└── ui/                      # Streamlit admin UI (optional)

tests/
├── unit/
│   ├── test_auth.py
│   ├── test_drive_service.py
│   ├── test_search_tools.py
│   ├── test_transfer_tools.py
│   ├── test_metadata_tools.py
│   ├── test_folder_tools.py
│   └── test_decorators.py
└── integration/
    └── test_drive_tools_integration.py
```

---

## Troubleshooting

### Import Errors
- Old MCP processes running — Kill them and restart
- Virtual environment issues — `uv sync`

### Tool Not Appearing
- Check it's in the export list (`my_tools = [...]`)
- Check it's imported in `google_drive/tools/__init__.py` and added to `drive_tools`
- Restart the MCP Inspector

### Tests Failing
- Check for Optional parameters (not allowed)
- Verify async function signature
- Ensure `ctx: Context = None` parameter exists
- Unit tests should mock `get_drive_service()` at the tool module level

---

## Getting Help

1. **Reference code**: Look at existing tools in `google_drive/tools/` for working patterns
2. **Claude Code**: Ask questions directly in your session
3. **Documentation**: See `docs/DECORATOR_PATTERNS.md` for deep technical details
