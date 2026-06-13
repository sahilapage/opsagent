from __future__ import annotations
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

import logging
import sys
# MCP uses stdio for protocol — redirect all logs to stderr
logging.basicConfig(stream=sys.stderr)
import structlog
structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

log = structlog.get_logger()

app = Server("opsagent")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_kb",
            description="Search the OpsAgent knowledge base for relevant information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="run_analysis",
            description="Run a RAG analysis query — retrieves context and generates grounded answer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Analysis question"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="send_email",
            description="Send an email via Gmail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            }
        ),
        Tool(
            name="read_emails",
            description="Read emails from Gmail inbox.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": ""},
                    "inbox": {"type": "string", "default": "primary"},
                    "max_results": {"type": "integer", "default": 5}
                }
            }
        ),
        Tool(
            name="create_calendar_event",
            description="Create a Google Calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "date_str": {"type": "string"}
                },
                "required": ["title", "date_str"]
            }
        ),
        Tool(
            name="list_calendar_events",
            description="List upcoming Google Calendar events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "default": 5}
                }
            }
        ),
        Tool(
            name="list_drive_files",
            description="List files in Google Drive.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": ""},
                    "max_results": {"type": "integer", "default": 10}
                }
            }
        ),
        Tool(
            name="get_memory",
            description="Retrieve stored memories for a user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "query": {"type": "string", "default": ""}
                },
                "required": ["user_id"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    log.info("mcp_tool_called", tool=name)

    if name == "search_kb":
        from rag.retriever import HybridRetriever
        retriever = HybridRetriever()
        results = retriever.retrieve(arguments["query"])
        if not results:
            return [TextContent(type="text", text="No results found.")]
        output = f"Found {len(results)} results:\n\n"
        for i, r in enumerate(results[:arguments.get("top_k", 5)], 1):
            output += f"[{i}] {r.metadata.get('source')} p.{r.metadata.get('page')}\n{r.text}\n\n"
        return [TextContent(type="text", text=output)]

    elif name == "run_analysis":
        from rag.chain import answer as rag_answer
        result = rag_answer(query=arguments["query"])
        return [TextContent(type="text", text=result.answer)]

    elif name == "send_email":
        from agents.action_agent import send_email
        result = send_email(
            to=arguments["to"],
            subject=arguments["subject"],
            body=arguments["body"]
        )
        return [TextContent(type="text", text=result)]

    elif name == "read_emails":
        from agents.action_agent import read_emails
        result = read_emails(
            query=arguments.get("query") or "",
            inbox=arguments.get("inbox") or "primary",
            max_results=arguments.get("max_results") or 5
        )
        return [TextContent(type="text", text=result)]

    elif name == "create_calendar_event":
        from agents.action_agent import create_event
        result = create_event(
            title=arguments["title"],
            date_str=arguments["date_str"]
        )
        return [TextContent(type="text", text=result)]

    elif name == "list_calendar_events":
        from agents.action_agent import list_events
        result = list_events(max_results=arguments.get("max_results", 5))
        return [TextContent(type="text", text=result)]

    elif name == "list_drive_files":
        from agents.action_agent import list_drive_files
        result = list_drive_files(
            query=arguments.get("query") or "",
            max_results=arguments.get("max_results") or 10
        )
        return [TextContent(type="text", text=result)]

    elif name == "get_memory":
        from memory.long_term import retrieve_memories
        memories = retrieve_memories(
            user_id=arguments["user_id"],
            query=arguments.get("query", "recent context"),
            top_k=5
        )
        return [TextContent(type="text", text="\n".join(f"- {m}" for m in memories))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    log.info("opsagent_mcp_server_starting")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
