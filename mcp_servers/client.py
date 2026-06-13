from __future__ import annotations
import asyncio
import json
import subprocess
import sys
import os
import structlog

log = structlog.get_logger()


class MCPClient:
    """Simple MCP client that communicates with the OpsAgent MCP server via stdio."""

    def __init__(self):
        self.server_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "server.py"
        )

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call an MCP tool synchronously."""
        try:
            result = asyncio.run(self._call_tool_async(tool_name, arguments))
            return result
        except RuntimeError:
            # Already in event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._call_tool_async(tool_name, arguments))
                return future.result()

    async def _call_tool_async(self, tool_name: str, arguments: dict) -> str:
        """Call tool via MCP protocol over stdio subprocess."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_path],
            env=dict(os.environ),
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if result.content:
                    return result.content[0].text
                return "No result"

    def list_tools(self) -> list[str]:
        """List available MCP tools."""
        try:
            result = asyncio.run(self._list_tools_async())
            return result
        except Exception as e:
            log.error("mcp_list_tools_error", error=str(e))
            return []

    async def _list_tools_async(self) -> list[str]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_path],
            env=dict(os.environ),
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [t.name for t in tools.tools]


# Singleton
_client = None

def get_mcp_client() -> MCPClient:
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
