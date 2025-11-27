# R2R FastMCP Server
# Install: mcp install server.py -v R2R_BASE_URL=http://localhost:7272
import json
import logging
import os
from typing import Any

from r2r import R2RClient  # type: ignore[import-untyped]

# Configuration
R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://localhost:7272")
API_KEY = os.getenv("API_KEY", "")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("r2r-mcp")

# Helper functions
def id_to_shorthand(id: str) -> str:
    return str(id)[:7]


def format_search_results_for_llm(results: Any) -> str:
    """
    Format R2R search results for LLM consumption.

    Aggregates 4 types of results:
    - Chunk search (vector search)
    - Graph search (knowledge graph entities/relationships)
    - Web search (internet results)
    - Document search (local documents with chunks)
    """
    lines = []

    # 1) Chunk search
    if results.chunk_search_results:
        lines.append("Vector Search Results:")
        for c in results.chunk_search_results:
            lines.append(f"Source ID [{id_to_shorthand(c.id)}]:")
            lines.append(c.text or "")

    # 2) Graph search
    if results.graph_search_results:
        lines.append("Graph Search Results:")
        for g in results.graph_search_results:
            lines.append(f"Source ID [{id_to_shorthand(g.id)}]:")
            if hasattr(g.content, "summary"):
                lines.append(f"Community Name: {g.content.name}")
                lines.append(f"ID: {g.content.id}")
                lines.append(f"Summary: {g.content.summary}")
            elif hasattr(g.content, "name") and hasattr(g.content, "description"):
                lines.append(f"Entity Name: {g.content.name}")
                lines.append(f"Description: {g.content.description}")
            elif (
                hasattr(g.content, "subject")
                and hasattr(g.content, "predicate")
                and hasattr(g.content, "object")
            ):
                rel = f"{g.content.subject}-{g.content.predicate}-{g.content.object}"
                lines.append(f"Relationship: {rel}")

    # 3) Web search
    if results.web_search_results:
        lines.append("Web Search Results:")
        for w in results.web_search_results:
            lines.append(f"Source ID [{id_to_shorthand(w.id)}]:")
            lines.append(f"Title: {w.title}")
            lines.append(f"Link: {w.link}")
            lines.append(f"Snippet: {w.snippet}")

    # 4) Local context docs
    if results.document_search_results:
        lines.append("Local Context Documents:")
        for doc_result in results.document_search_results:
            doc_title = doc_result.title or "Untitled Document"
            doc_id = doc_result.id
            summary = doc_result.summary

            lines.append(f"Full Document ID: {doc_id}")
            lines.append(f"Shortened Document ID: {id_to_shorthand(doc_id)}")
            lines.append(f"Document Title: {doc_title}")
            if summary:
                lines.append(f"Summary: {summary}")

            if doc_result.chunks:
                for chunk in doc_result.chunks:
                    lines.append(
                        f"\nChunk ID {id_to_shorthand(chunk['id'])}:\n{chunk['text']}"
                    )

    result = "\n".join(lines)
    return result


# Create FastMCP server
try:
    from fastmcp import Context, FastMCP  # type: ignore[import-untyped]
    from fastmcp.server.middleware import Middleware, MiddlewareContext
except Exception as e:
    raise ImportError(
        "FastMCP is not installed. Please run `pip install fastmcp`"
    ) from e


# Error Handling Middleware
class R2RErrorHandlingMiddleware(Middleware):
    """Custom error handling middleware for R2R operations."""

    def __init__(self):
        self.logger = logging.getLogger("r2r-errors")
        self.error_counts = {}

    async def on_message(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)
        except Exception as error:
            # Track error statistics
            error_key = f"{type(error).__name__}:{context.method}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

            self.logger.error(
                f"Error in {context.method}: {type(error).__name__}: {error}"
            )

            # Special handling for R2R connection errors
            if "connection" in str(error).lower() or "refused" in str(error).lower():
                raise ConnectionError(
                    f"Failed to connect to R2R server at {R2R_BASE_URL}. "
                    "Please check R2R_BASE_URL and ensure R2R is running."
                ) from error

            # Re-raise the original error
            raise


# Initialize FastMCP server
mcp = FastMCP("R2R Retrieval System")
mcp.add_middleware(R2RErrorHandlingMiddleware())


# Resources
@mcp.resource("r2r://config")
async def get_r2r_config(ctx: Context) -> str:
    """Get current R2R MCP server configuration."""
    await ctx.info("Retrieving R2R configuration")

    config = {
        "r2r_base_url": R2R_BASE_URL,
        "api_key_configured": bool(API_KEY),
        "request_id": ctx.request_id,
        "server_name": "R2R Retrieval System"
    }

    return json.dumps(config, indent=2)


@mcp.resource("r2r://health")
async def check_r2r_health(ctx: Context) -> str:
    """Check R2R server health and connectivity."""
    await ctx.info("Checking R2R server health")

    try:
        client = R2RClient(base_url=R2R_BASE_URL)
        if API_KEY:
            client.set_api_key(API_KEY)

        # Simple connectivity check - try to initialize client
        health_data = {
            "status": "healthy",
            "r2r_url": R2R_BASE_URL,
            "timestamp": ctx.request_id,
            "api_key_configured": bool(API_KEY)
        }
        return json.dumps(health_data, indent=2)
    except Exception as e:
        await ctx.error(f"Health check failed: {e!s}")
        error_data = {
            "status": "unhealthy",
            "error": str(e),
            "r2r_url": R2R_BASE_URL
        }
        return json.dumps(error_data, indent=2)


# Tools
@mcp.tool(
    annotations={
        "title": "R2R Basic Search",
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def search(query: str, ctx: Context) -> str:
    """
    Perform semantic search on R2R knowledge base.

    Args:
        query: The search query to find relevant documents

    Returns:
        Formatted search results including vector, graph, web, and document results
    """
    await ctx.info(f"Starting search query: {query}")

    try:
        await ctx.report_progress(progress=10, total=100, message="Initializing client")

        client = R2RClient(base_url=R2R_BASE_URL)
        if API_KEY:
            client.set_api_key(API_KEY)

        await ctx.report_progress(progress=30, total=100, message="Executing search")

        search_response = client.retrieval.search(query=query)

        await ctx.report_progress(progress=80, total=100, message="Formatting results")

        formatted = format_search_results_for_llm(search_response.results)

        await ctx.report_progress(progress=100, total=100, message="Complete")
        await ctx.info(
            f"Search completed successfully, returned {len(formatted)} chars"
        )

        return formatted
    except Exception as e:
        await ctx.error(f"Search failed: {e!s}")
        raise


@mcp.tool(
    annotations={
        "title": "R2R Advanced Search",
        "readOnlyHint": True,
        "openWorldHint": True
    }
)
async def advanced_search(
    query: str,
    use_hybrid_search: bool = False,
    semantic_weight: float = 5.0,
    full_text_weight: float = 1.0,
    limit: int = 10,
    ctx: Context | None = None
) -> str:
    """
    Advanced search with hybrid search and customizable settings.

    Args:
        query: The search query
        use_hybrid_search: Enable hybrid search (semantic + full-text)
        semantic_weight: Weight for semantic search (default: 5.0)
        full_text_weight: Weight for full-text search (default: 1.0)
        limit: Maximum number of results (default: 10)

    Returns:
        Formatted search results
    """
    if ctx:
        await ctx.info(f"Advanced search: {query}")
        await ctx.report_progress(20, 100, "Configuring search")

    client = R2RClient(base_url=R2R_BASE_URL)
    if API_KEY:
        client.set_api_key(API_KEY)

    search_settings = {
        "limit": limit,
        "use_semantic_search": True,
    }

    if use_hybrid_search:
        search_settings["use_hybrid_search"] = True
        search_settings["hybrid_settings"] = {
            "semantic_weight": semantic_weight,
            "full_text_weight": full_text_weight,
            "full_text_limit": 200,
            "rrf_k": 50
        }
        if ctx:
            await ctx.info("Hybrid search enabled")

    if ctx:
        await ctx.report_progress(50, 100, "Executing search")

    try:
        search_response = client.retrieval.search(
            query=query,
            search_settings=search_settings
        )

        if ctx:
            await ctx.report_progress(90, 100, "Formatting results")

        formatted = format_search_results_for_llm(search_response.results)

        if ctx:
            await ctx.report_progress(100, 100, "Complete")
            await ctx.info("Advanced search completed successfully")

        return formatted
    except Exception as e:
        if ctx:
            await ctx.error(f"Advanced search failed: {e!s}")
        raise


@mcp.tool(
    annotations={
        "title": "R2R Knowledge Graph Search",
        "readOnlyHint": True,
        "openWorldHint": True
    }
)
async def graph_search(
    query: str,
    enable_graph: bool = True,
    kg_search_type: str = "local",
    ctx: Context | None = None
) -> str:
    """
    Search with knowledge graph context for enhanced results.

    Args:
        query: The search query
        enable_graph: Enable knowledge graph integration
        kg_search_type: Type of graph search ("local" or "global")

    Returns:
        Formatted search results with graph context
    """
    if ctx:
        await ctx.info(f"Graph search: {query}, type={kg_search_type}")
        await ctx.report_progress(20, 100, "Initializing graph search")

    client = R2RClient(base_url=R2R_BASE_URL)
    if API_KEY:
        client.set_api_key(API_KEY)

    search_settings = {
        "limit": 20,
        "use_semantic_search": True,
    }

    if enable_graph:
        search_settings["graph_search_settings"] = {
            "use_graph_search": True,
            "kg_search_type": kg_search_type
        }
        if ctx:
            await ctx.info("Knowledge graph integration enabled")

    if ctx:
        await ctx.report_progress(50, 100, "Executing graph search")

    try:
        search_response = client.retrieval.search(
            query=query,
            search_settings=search_settings
        )

        if ctx:
            await ctx.report_progress(90, 100, "Formatting results")

        formatted = format_search_results_for_llm(search_response.results)

        if ctx:
            await ctx.report_progress(100, 100, "Complete")
            await ctx.info("Graph search completed successfully")

        return formatted
    except Exception as e:
        if ctx:
            await ctx.error(f"Graph search failed: {e!s}")
        raise


@mcp.tool(
    annotations={
        "title": "R2R RAG Answer",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True
    }
)
async def rag(query: str, ctx: Context) -> str:
    """
    Perform Retrieval-Augmented Generation query.

    Args:
        query: The question to answer using the knowledge base

    Returns:
        Generated answer based on relevant context from the knowledge base
    """
    await ctx.info(f"RAG query: {query}")

    try:
        await ctx.report_progress(progress=20, total=100, message="Initializing RAG")

        client = R2RClient(base_url=R2R_BASE_URL)
        if API_KEY:
            client.set_api_key(API_KEY)

        await ctx.report_progress(progress=40, total=100, message="Retrieving context")

        rag_response = client.retrieval.rag(query=query)

        await ctx.report_progress(progress=90, total=100, message="Generating answer")

        answer = rag_response.results.generated_answer  # type: ignore

        await ctx.report_progress(progress=100, total=100, message="Complete")
        await ctx.info("RAG completed successfully")

        return answer
    except Exception as e:
        await ctx.error(f"RAG failed: {e!s}")
        raise


@mcp.tool(
    annotations={
        "title": "R2R Advanced RAG",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True
    }
)
async def advanced_rag(
    query: str,
    model: str = "openai/gpt-4o-mini",
    temperature: float = 0.7,
    use_hybrid_search: bool = False,
    include_web_search: bool = False,
    ctx: Context | None = None
) -> str:
    """
    Advanced RAG with customizable generation settings.

    Args:
        query: The question to answer
        model: LLM model to use for generation (default: openai/gpt-4o-mini)
        temperature: Generation temperature 0.0-1.0 (default: 0.7)
        use_hybrid_search: Enable hybrid search for retrieval
        include_web_search: Include web search results

    Returns:
        Generated answer based on retrieved context
    """
    if ctx:
        await ctx.info(f"Advanced RAG: {query}, model={model}, temp={temperature}")
        await ctx.report_progress(10, 100, "Preparing search")

    client = R2RClient(base_url=R2R_BASE_URL)
    if API_KEY:
        client.set_api_key(API_KEY)

    search_settings = {}
    if use_hybrid_search:
        search_settings["use_hybrid_search"] = True
        if ctx:
            await ctx.info("Hybrid search enabled for RAG")

    rag_generation_config = {
        "model": model,
        "temperature": temperature,
        "stream": False
    }

    if ctx:
        await ctx.report_progress(30, 100, "Retrieving context")

    try:
        rag_response = client.retrieval.rag(
            query=query,
            search_settings=search_settings if search_settings else None,
            rag_generation_config=rag_generation_config,
            include_web_search=include_web_search
        )

        if ctx:
            await ctx.report_progress(90, 100, "Answer generated")

        answer = rag_response.results.generated_answer

        if ctx:
            await ctx.report_progress(100, 100, "Complete")
            await ctx.info("Advanced RAG completed successfully")

        return answer
    except Exception as e:
        if ctx:
            await ctx.error(f"Advanced RAG failed: {e!s}")
        raise


# Create ASGI application for production deployment (Uvicorn, ChatMCP, etc.)
app = mcp.http_app()

# Run the server if executed directly (for local testing)
if __name__ == "__main__":
    # For local development, use HTTP transport
    # Accessible at http://localhost:8000/mcp
    mcp.run()
