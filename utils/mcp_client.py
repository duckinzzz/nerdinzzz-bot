"""Generic MCP client for interacting with MCP servers via stdio transport."""

from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from utils.logging_utils import logger


class McpError(Exception):
    """Base exception for MCP client errors."""


class McpConnectionError(McpError):
    """Raised when connecting to an MCP server fails."""


class McpToolCallError(McpError):
    """Raised when a tool call fails."""


class McpClient:
    """Manages a connection to an MCP server over stdio transport.

    Usage (context manager — auto cleanup):
        async with McpClient("npx", ["-y", "..."]) as client:
            result = await client.call_tool("foo", {})

    Usage (persistent — must call stop() on shutdown):
        client = McpClient("npx", ["-y", "..."])
        await client.start()
        result = await client.call_tool("foo", {})
        await client.stop()
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env,
        )
        self._session: ClientSession | None = None
        self._read = None
        self._write = None
        self._stdio = None

    async def start(self) -> "McpClient":
        """Start connection to the MCP server (for standalone use)."""
        logger.debug(
            f"MCP connecting: {self._params.command} {' '.join(self._params.args or [])}"
        )
        try:
            self._stdio = stdio_client(self._params)
            self._read, self._write = await self._stdio.__aenter__()
            self._session = await ClientSession(self._read, self._write).__aenter__()
            await self._session.initialize()
            logger.debug("MCP session initialized")
            return self
        except Exception as e:
            self._session = None
            self._stdio = None
            raise McpConnectionError(
                f"Failed to connect to MCP server: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop connection and clean up."""
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._stdio is not None:
            await self._stdio.__aexit__(None, None, None)
            self._stdio = None
        logger.debug("MCP session closed")

    async def __aenter__(self) -> "McpClient":
        return await self.start()

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> str:
        """Call an MCP tool and return the text content of the result."""
        if self._session is None:
            raise McpConnectionError("Not connected. Call start() first.")

        try:
            result = await self._session.call_tool(tool_name, arguments or {})
        except Exception as e:
            raise McpToolCallError(
                f"Tool '{tool_name}' call failed: {e}"
            ) from e

        # Extract text content from the result
        texts: list[str] = []
        if hasattr(result, "content") and result.content:
            for item in result.content:
                if hasattr(item, "type") and item.type == "text":
                    texts.append(item.text)
                elif hasattr(item, "text"):
                    texts.append(item.text)

        return "\n".join(texts)

    async def list_tools(self) -> Any:
        """List available tools from the MCP server."""
        if self._session is None:
            raise McpConnectionError("Not connected. Call start() first.")
        return await self._session.list_tools()
