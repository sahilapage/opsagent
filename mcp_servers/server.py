from __future__ import annotations
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from rag.retriever import HybridRetriever
from rag.chain import answer as rag_answer
from rag.config import get_settings

log = structlog.get_logger()

# ── MCP Server ─────────────────────────────────────────────────────────────────

app = Server("opsagent")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_kb",
            description="Search the OpsAgent knowledge base for relevant information. Use this to find answers from ingested documents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="run_analysis",
            description="Run a full RAG analysis query — retrieves relevant context and generates a grounded answer with citations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The analysis question"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_memory",
            description="Retrieve past conversation context or stored facts about a user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user ID to retrieve memory for"
                    }
                },
                "required": ["user_id"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    log.info("mcp_tool_called", tool=name, args=arguments)

    if name == "search_kb":
        query = arguments["query"]
        top_k = arguments.get("top_k", 5)
        retriever = HybridRetriever()
        results = retriever.retrieve(query)
        if not results:
            return [TextContent(type="text", text="No relevant results found in knowledge base.")]
        
        output = f"Found {len(results)} relevant chunks for: '{query}'\n\n"
        for i, r in enumerate(results[:top_k], 1):
            source = r.metadata.get("source", "unknown")
            page = r.metadata.get("page", "")
            output += f"[{i}] ({source}, page {page})\n{r.text}\n\n"
        
        return [TextContent(type="text", text=output)]

    elif name == "run_analysis":
        query = arguments["query"]
        result = rag_answer(query=query)
        return [TextContent(type="text", text=result.answer)]

    elif name == "get_memory":
        user_id = arguments["user_id"]
        # Phase 5 stub — long term memory coming
        return [TextContent(
            type="text",
            text=f"Memory for user '{user_id}': No long-term memory stored yet. (Phase 5 — pgvector memory coming soon)"
        )]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    log.info("opsagent_mcp_server_starting")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
