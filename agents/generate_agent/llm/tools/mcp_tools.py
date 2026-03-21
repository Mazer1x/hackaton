# llm/tools/mcp_tools.py
"""Load MCP tools: Astro (HTTP) and CSS (stdio). Playwright disabled."""
import asyncio
import logging
import os
import shutil
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


def _stdio_connections() -> dict:
    """Stdio MCP connections: css (design), sequentialthinking (reasoning only). npx from PATH."""
    npx = shutil.which("npx")
    if not npx:
        logger.warning(
            "npx not found in PATH — stdio MCP (css, sequentialthinking) will be skipped. "
            "Install Node.js or run from environment with npx available."
        )
        return {}
    return {
        "css": {
            "transport": "stdio",
            "command": npx,
            "args": ["-y", "css-mcp@1.3.0"],
        },
        "sequentialthinking": {
            "transport": "stdio",
            "command": npx,
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        },
        # Playwright disabled to save tokens
        # "playwright": {
        #     "transport": "stdio",
        #     "command": npx,
        #     "args": ["-y", "@playwright/mcp@latest"],
        # },
    }


# Design (load_skills): astro + css only. Sequential thinking is reasoning-only.
def _get_mcp_connections() -> dict:
    out = {
        "astro": {
            "url": "http://155.212.185.165/mcp",
            "transport": "streamable_http",
        },
    }
    stdio = _stdio_connections()
    # Exclude sequentialthinking so it is not added to design tools
    for name, conn in stdio.items():
        if name != "sequentialthinking":
            out[name] = conn
    return out


async def get_sequential_thinking_tools_async() -> list[BaseTool]:
    """Load only Sequential Thinking MCP tools (for reasoning node). Uses config from _stdio_connections()."""
    # Run blocking shutil.which() in thread to avoid BlockingError under ASGI
    stdio = await asyncio.to_thread(_stdio_connections)
    if "sequentialthinking" not in stdio:
        return []
    connections = {"sequentialthinking": stdio["sequentialthinking"]}
    client = MultiServerMCPClient(
        connections=connections,
        tool_name_prefix=True,
    )
    try:
        tools = await client.get_tools(server_name="sequentialthinking")
        logger.info("MCP sequentialthinking: loaded %s tool(s)", len(tools))
        return tools
    except Exception as e:
        logger.warning("MCP sequentialthinking not loaded: %s", e, exc_info=False)
        return []


def get_sequential_thinking_tools() -> list[BaseTool]:
    """Synchronous wrapper for Sequential Thinking tools (reasoning phase)."""
    return asyncio.run(get_sequential_thinking_tools_async())


async def get_mcp_tools_async() -> list[BaseTool]:
    """Load tools from each MCP separately; on server error — log and skip."""
    # Run blocking shutil.which() in thread to avoid BlockingError under ASGI
    connections = await asyncio.to_thread(_get_mcp_connections)
    if not connections:
        logger.warning("No MCP connections (npx not found?).")
        return []
    client = MultiServerMCPClient(
        connections=connections,
        tool_name_prefix=True,
    )
    all_tools: list[BaseTool] = []
    for name in connections:
        try:
            tools = await client.get_tools(server_name=name)
            all_tools.extend(tools)
            logger.info("MCP %s: loaded %s tool(s)", name, len(tools))
        except Exception as e:
            logger.warning("MCP %s not loaded: %s", name, e, exc_info=False)
    return all_tools


def get_mcp_tools() -> list[BaseTool]:
    """Synchronous wrapper: get tools (for use during graph building)."""
    return asyncio.run(get_mcp_tools_async())
