"""
MCP Server — Exposes the Prompt Analyzer as discoverable tools
for enterprise multi-agent systems.

Tools:
- analyze_prompt: Analyze a prompt for quality
- get_analysis_history: Retrieve past analyses
"""

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from prompt_analyzer import PromptAnalyzer
from analytics_reporter.reporter import AnalyticsReporter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("prompt-analyzer")

# Shared instances
analyzer = PromptAnalyzer()
reporter = AnalyticsReporter()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise available tools to MCP clients."""
    return [
        Tool(
            name="analyze_prompt",
            description=(
                "Analyze a prompt for quality across 5 dimensions: "
                "clarity, token efficiency, goal alignment, structure, "
                "and vagueness. Returns scores (0-100), identified mistakes "
                "with suggestions, an optimized rewrite, and token savings. "
                "Supports project-aware analysis for context-specific recommendations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to analyze",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional goal or context for the prompt",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Project ID for context-aware analysis (isolated per project)",
                    },
                    "source_agent": {
                        "type": "string",
                        "description": "Name of the agent that authored this prompt",
                    },
                    "target_agent": {
                        "type": "string",
                        "description": "Name of the agent this prompt is directed to",
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="get_analysis_history",
            description=(
                "Retrieve past prompt analyses. Can filter by project. "
                "Useful for understanding prompt quality trends."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 10)",
                        "default": 10,
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Filter by project ID",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from MCP clients."""

    if name == "analyze_prompt":
        prompt = arguments.get("prompt", "")
        if not prompt:
            return [TextContent(type="text", text="Error: prompt is required")]

        try:
            result = await analyzer.analyze(
                prompt=prompt,
                context=arguments.get("context"),
                project_id=arguments.get("project_id"),
                source_agent=arguments.get("source_agent"),
                target_agent=arguments.get("target_agent"),
            )

            # Store via Agent 2
            await reporter.initialize()
            analysis_id = await reporter.report(result)

            response = result.model_dump(mode="json")
            response["analysis_id"] = analysis_id

            return [
                TextContent(
                    type="text",
                    text=json.dumps(response, indent=2, default=str),
                )
            ]

        except Exception as e:
            logger.error("analyze_prompt failed: %s", e, exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "get_analysis_history":
        try:
            await reporter.initialize()
            data = await reporter.get_interactions(
                limit=arguments.get("limit", 10),
                project_id=arguments.get("project_id"),
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(data, indent=2, default=str),
                )
            ]

        except Exception as e:
            logger.error("get_analysis_history failed: %s", e, exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server over stdio."""
    await reporter.initialize()
    logger.info("MCP Server starting (stdio mode)")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
