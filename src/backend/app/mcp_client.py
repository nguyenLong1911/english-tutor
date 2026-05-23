"""
MCP client placeholder.

Wraps a Model Context Protocol client session so FastAPI routes can call
MCP tools from external MCP servers. Wire real server params in connect().
"""


class MCPClient:
    def __init__(self):
        self.session = None

    async def connect(self):
        # TODO: open an MCP session, e.g. via mcp.client.stdio.stdio_client
        # and mcp.ClientSession — configure server command + args here.
        self.session = None

    async def disconnect(self):
        self.session = None

    async def list_tools(self) -> list[dict]:
        if self.session is None:
            return []
        return []

    async def call_tool(self, name: str, arguments: dict) -> str:
        if self.session is None:
            return f"[placeholder] would call {name}({arguments})"
        return ""
