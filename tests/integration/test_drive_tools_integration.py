"""MCP Integration Tests for Google Drive tools.

Validates that all Google Drive tools are properly registered and discoverable
via the MCP protocol. Tests tool schemas for correctness.

These tests do NOT call the real Google Drive API -- they only verify
tool registration and schema through the MCP client-server flow.
"""

import pytest
from mcp import types
from .conftest import extract_text_content, extract_error_text

pytestmark = pytest.mark.anyio


DRIVE_TOOLS = [
    "search_files",
    "list_folder",
    "download_file",
    "upload_file",
    "get_file_info",
    "create_folder",
]


class TestDriveToolDiscovery:
    """Test that drive tools are discoverable via MCP."""

    async def test_all_drive_tools_discoverable(self, mcp_session):
        """All 6 drive tools should appear in list_tools()."""
        session, transport = mcp_session
        tools_response = await session.list_tools()
        tool_names = [t.name for t in tools_response.tools]

        for expected in DRIVE_TOOLS:
            assert expected in tool_names, (
                f"Drive tool '{expected}' not found in {tool_names} (transport: {transport})"
            )

    async def test_no_kwargs_in_drive_tool_schemas(self, mcp_session):
        """Drive tool schemas must not expose a 'kwargs' parameter."""
        session, transport = mcp_session
        tools_response = await session.list_tools()

        drive_tool_map = {t.name: t for t in tools_response.tools if t.name in DRIVE_TOOLS}

        for name, tool in drive_tool_map.items():
            schema = tool.inputSchema
            props = schema.get("properties", {})
            assert "kwargs" not in props, (
                f"Tool '{name}' has 'kwargs' in schema (transport: {transport})"
            )

    async def test_drive_tool_schemas_correct(self, mcp_session):
        """Verify key parameters exist in each drive tool schema."""
        session, transport = mcp_session
        tools_response = await session.list_tools()

        tool_map = {t.name: t for t in tools_response.tools}

        # search_files must have 'query' required
        sf = tool_map["search_files"]
        assert "query" in sf.inputSchema.get("properties", {}), "search_files missing 'query'"
        assert "query" in sf.inputSchema.get("required", []), "search_files 'query' not required"

        # download_file must have 'file_id' required
        df = tool_map["download_file"]
        assert "file_id" in df.inputSchema.get("properties", {}), "download_file missing 'file_id'"
        assert "file_id" in df.inputSchema.get("required", []), "download_file 'file_id' not required"

        # upload_file must have 'local_path' required
        uf = tool_map["upload_file"]
        assert "local_path" in uf.inputSchema.get("properties", {}), "upload_file missing 'local_path'"
        assert "local_path" in uf.inputSchema.get("required", []), "upload_file 'local_path' not required"

        # get_file_info must have 'file_id' required
        gfi = tool_map["get_file_info"]
        assert "file_id" in gfi.inputSchema.get("properties", {}), "get_file_info missing 'file_id'"
        assert "file_id" in gfi.inputSchema.get("required", []), "get_file_info 'file_id' not required"

        # create_folder must have 'folder_name' required
        cf = tool_map["create_folder"]
        assert "folder_name" in cf.inputSchema.get("properties", {}), "create_folder missing 'folder_name'"
        assert "folder_name" in cf.inputSchema.get("required", []), "create_folder 'folder_name' not required"

        # list_folder has no required params (folder_id defaults to "root")
        lf = tool_map["list_folder"]
        required = lf.inputSchema.get("required", [])
        assert "folder_id" not in required, "list_folder 'folder_id' should not be required"

    async def test_drive_tool_count(self, mcp_session):
        """Verify we have exactly 6 drive tools registered."""
        session, transport = mcp_session
        tools_response = await session.list_tools()
        tool_names = [t.name for t in tools_response.tools]

        drive_count = sum(1 for name in tool_names if name in DRIVE_TOOLS)
        assert drive_count == 6, f"Expected 6 drive tools, found {drive_count} (transport: {transport})"
