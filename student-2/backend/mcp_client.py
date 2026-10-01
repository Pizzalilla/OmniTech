import os
from mcp_client import McpClient, McpError

mcp = McpClient(os.getenv("MCP_HOST", "http://localhost:6003"))
res = mcp.call_tool("get_order_status", {"order_id": 5})
if res["isError"]:
    print(res["content"][0]["text"])        # e.g. "Order #999 not found"
else:
    print(res["structuredContent"])        # the tool's JSON result