# R2R FastMCP Server
# Install: mcp install server.py -v R2R_BASE_URL=http://localhost:7272
import json
import logging
import os
from enum import Enum
from typing import Any, Literal

from dotenv import load_dotenv
from r2r import R2RClient  # type: ignore[import-untyped]

# Load environment variables from .env file
load_dotenv()

# Configuration
R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
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


# Preset configurations for different use cases
class SearchPreset(str, Enum):
    """Preset configurations for search operations."""

    DEFAULT = "default"
    DEVELOPMENT = "development"
    REFACTORING = "refactoring"
    DEBUG = "debug"
    RESEARCH = "research"
    PRODUCTION = "production"


class RAGPreset(str, Enum):
    """Preset configurations for RAG operations."""

    DEFAULT = "default"
    DEVELOPMENT = "development"
    REFACTORING = "refactoring"
    DEBUG = "debug"
    RESEARCH = "research"
    PRODUCTION = "production"


def get_search_preset_config(preset: str) -> dict[str, Any]:
    """
    Get search configuration for a preset.

    Args:
        preset: Preset name (default, development, refactoring, debug, research, production)

    Returns:
        Dictionary with search settings
    """
    presets = {
        "default": {
            "use_semantic_search": True,
            "use_hybrid_search": False,
            "use_graph_search": False,
            "limit": 10,
        },
        "development": {
            "use_semantic_search": True,
            "use_hybrid_search": True,
            "use_graph_search": False,
            "limit": 15,
            "hybrid_settings": {
                "semantic_weight": 5.0,
                "full_text_weight": 1.0,
                "full_text_limit": 200,
                "rrf_k": 50,
            },
        },
        "refactoring": {
            "use_semantic_search": True,
            "use_hybrid_search": True,
            "use_graph_search": True,
            "limit": 20,
            "kg_search_type": "local",
            "hybrid_settings": {
                "semantic_weight": 7.0,
                "full_text_weight": 3.0,
                "full_text_limit": 300,
                "rrf_k": 50,
            },
        },
        "debug": {
            "use_semantic_search": True,
            "use_hybrid_search": False,
            "use_graph_search": True,
            "limit": 5,
            "kg_search_type": "local",
        },
        "research": {
            "use_semantic_search": True,
            "use_hybrid_search": True,
            "use_graph_search": True,
            "limit": 30,
            "kg_search_type": "global",
            "hybrid_settings": {
                "semantic_weight": 6.0,
                "full_text_weight": 2.0,
                "full_text_limit": 400,
                "rrf_k": 60,
            },
        },
        "production": {
            "use_semantic_search": True,
            "use_hybrid_search": True,
            "use_graph_search": False,
            "limit": 10,
            "hybrid_settings": {
                "semantic_weight": 5.0,
                "full_text_weight": 1.0,
                "full_text_limit": 200,
                "rrf_k": 50,
            },
        },
    }
    return presets.get(preset.lower(), presets["default"]).copy()


def get_rag_preset_config(preset: str) -> dict[str, Any]:
    """
    Get RAG configuration for a preset.

    Args:
        preset: Preset name (default, development, refactoring, debug, research, production)

    Returns:
        Dictionary with RAG settings (search_settings and rag_generation_config)
    """
    presets = {
        "default": {
            "search_settings": {
                "use_semantic_search": True,
                "use_hybrid_search": False,
                "limit": 10,
            },
            "rag_generation_config": {
                "model": "vertex_ai/gemini-2.5-flash",
                "temperature": 0.7,
            },
        },
        "development": {
            "search_settings": {
                "use_semantic_search": True,
                "use_hybrid_search": True,
                "limit": 15,
                "hybrid_settings": {
                    "semantic_weight": 5.0,
                    "full_text_weight": 1.0,
                    "full_text_limit": 200,
                    "rrf_k": 50,
                },
            },
            "rag_generation_config": {
                "model": "vertex_ai/gemini-2.5-flash",
                "temperature": 0.8,
            },
        },
        "refactoring": {
            "search_settings": {
                "use_semantic_search": True,
                "use_hybrid_search": True,
                "use_graph_search": True,
                "limit": 20,
                "kg_search_type": "local",
                "hybrid_settings": {
                    "semantic_weight": 7.0,
                    "full_text_weight": 3.0,
                    "full_text_limit": 300,
                    "rrf_k": 50,
                },
            },
            "rag_generation_config": {
                "model": "vertex_ai/gemini-2.5-pro",
                "temperature": 0.5,
            },
        },
        "debug": {
            "search_settings": {
                "use_semantic_search": True,
                "use_hybrid_search": False,
                "use_graph_search": True,
                "limit": 5,
                "kg_search_type": "local",
            },
            "rag_generation_config": {
                "model": "vertex_ai/gemini-2.5-flash",
                "temperature": 0.3,
            },
        },
        "research": {
            "search_settings": {
                "use_semantic_search": True,
                "use_hybrid_search": True,
                "use_graph_search": True,
                "limit": 30,
                "kg_search_type": "global",
                "hybrid_settings": {
                    "semantic_weight": 6.0,
                    "full_text_weight": 2.0,
                    "full_text_limit": 400,
                    "rrf_k": 60,
                },
            },
            "rag_generation_config": {
                "model": "vertex_ai/gemini-2.5-pro",
                "temperature": 0.7,
            },
        },
        "production": {
            "search_settings": {
                "use_semantic_search": True,
                "use_hybrid_search": True,
                "limit": 10,
                "hybrid_settings": {
                    "semantic_weight": 5.0,
                    "full_text_weight": 1.0,
                    "full_text_limit": 200,
                    "rrf_k": 50,
                },
            },
            "rag_generation_config": {
                "model": "vertex_ai/gemini-2.5-flash",
                "temperature": 0.6,
            },
        },
    }
    config = presets.get(preset.lower(), presets["default"])
    return {
        "search_settings": config["search_settings"].copy(),
        "rag_generation_config": config["rag_generation_config"].copy(),
    }


# Validation functions
def validate_limit(limit: int) -> None:
    """Validate limit parameter (1-100)."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")


def validate_temperature(temperature: float) -> None:
    """Validate temperature parameter (0.0-1.0)."""
    if not 0.0 <= temperature <= 1.0:
        raise ValueError("temperature must be between 0.0 and 1.0")


def validate_semantic_weight(weight: float) -> None:
    """Validate semantic weight parameter (0.0-10.0)."""
    if not 0.0 <= weight <= 10.0:
        raise ValueError("semantic_weight must be between 0.0 and 10.0")


def validate_full_text_weight(weight: float) -> None:
    """Validate full text weight parameter (0.0-10.0)."""
    if not 0.0 <= weight <= 10.0:
        raise ValueError("full_text_weight must be between 0.0 and 10.0")


def validate_full_text_limit(limit: int) -> None:
    """Validate full text limit parameter (1-1000)."""
    if not 1 <= limit <= 1000:
        raise ValueError("full_text_limit must be between 1 and 1000")


def validate_rrf_k(k: int) -> None:
    """Validate RRF k parameter (1-100)."""
    if not 1 <= k <= 100:
        raise ValueError("rrf_k must be between 1 and 100")


def validate_kg_search_type(kg_search_type: str) -> None:
    """Validate knowledge graph search type."""
    if kg_search_type not in ["local", "global"]:
        raise ValueError("kg_search_type must be 'local' or 'global'")


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
        "server_name": "R2R Retrieval System",
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
            "api_key_configured": bool(API_KEY),
        }
        return json.dumps(health_data, indent=2)
    except Exception as e:
        await ctx.error(f"Health check failed: {e!s}")
        error_data = {"status": "unhealthy", "error": str(e), "r2r_url": R2R_BASE_URL}
        return json.dumps(error_data, indent=2)


# Tools
@mcp.tool(
    annotations={
        "title": "R2R Search",
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def search(
    query: str,
    ctx: Context,
    preset: str = "default",
    use_semantic_search: bool = True,
    use_hybrid_search: bool = False,
    use_graph_search: bool = True,
    limit: int = 10,
    kg_search_type: Literal["local", "global"] = "local",
    semantic_weight: float = 5.0,
    full_text_weight: float = 1.0,
    full_text_limit: int = 200,
    rrf_k: int = 50,
    search_strategy: str | None = "rag_fusion",
    include_web_search: bool = False,
) -> str:
    """
    Perform comprehensive search on R2R knowledge base with full parameter control.

    This tool supports semantic search, hybrid search (semantic + full-text), knowledge graph search,
    and web search. Use presets for common scenarios or customize all parameters manually.

    Args:
        query: The search query to find relevant documents. Required.
        preset: Preset configuration for common use cases. Options:
            - "default": Basic semantic search, 10 results
            - "development": Hybrid search optimized for code development, 15 results
            - "refactoring": Hybrid + graph search for code refactoring, 20 results
            - "debug": Minimal graph search for debugging, 5 results
            - "research": Comprehensive search with global graph, 30 results
            - "production": Balanced hybrid search for production, 10 results
        use_semantic_search: Enable semantic/vector search (default: True)
        use_hybrid_search: Enable hybrid search combining semantic and full-text search (default: False)
        use_graph_search: Enable knowledge graph search for entity/relationship discovery (default: False)
        limit: Maximum number of results to return. Must be between 1 and 100 (default: 10)
        kg_search_type: Knowledge graph search type. "local" for local context, "global" for broader connections (default: "local")
        semantic_weight: Weight for semantic search in hybrid mode. Must be between 0.0 and 10.0 (default: 5.0)
        full_text_weight: Weight for full-text search in hybrid mode. Must be between 0.0 and 10.0 (default: 1.0)
        full_text_limit: Maximum full-text results to consider in hybrid search. Must be between 1 and 1000 (default: 200)
        rrf_k: Reciprocal Rank Fusion parameter for hybrid search. Must be between 1 and 100 (default: 50)
        search_strategy: Advanced search strategy (e.g., "hyde", "rag_fusion"). Optional.
        include_web_search: Include web search results from the internet (default: False)

    Returns:
        Formatted search results including:
        - Vector search results (chunks)
        - Graph search results (entities, relationships, communities)
        - Web search results (if enabled)
        - Document search results (local documents with chunks)

    Examples:
        # Simple search with default settings
        search("What is machine learning?")

        # Development preset for code search
        search("async function implementation", preset="development")

        # Custom hybrid search
        search("API documentation", use_hybrid_search=True, semantic_weight=7.0, limit=20)

        # Research with knowledge graph
        search("neural network architectures", preset="research")
    """
    await ctx.info(f"Starting search query: {query}, preset: {preset}")

    try:
        # Validate parameters
        validate_limit(limit)
        validate_semantic_weight(semantic_weight)
        validate_full_text_weight(full_text_weight)
        validate_full_text_limit(full_text_limit)
        validate_rrf_k(rrf_k)
        if use_graph_search:
            validate_kg_search_type(kg_search_type)

        await ctx.report_progress(progress=10, total=100, message="Initializing client")

        client = R2RClient(base_url=R2R_BASE_URL)
        if API_KEY:
            client.set_api_key(API_KEY)

        # Get preset configuration and merge with explicit parameters
        preset_config = get_search_preset_config(preset)

        # Apply preset values, but allow explicit parameters to override
        # For boolean flags: if preset enables it, use it unless explicitly disabled
        # For numeric: use preset if value is default, otherwise use explicit value
        final_use_hybrid = (
            use_hybrid_search
            if preset == "default"
            else (use_hybrid_search or preset_config.get("use_hybrid_search", False))
        )
        final_use_graph = (
            use_graph_search
            if preset == "default"
            else (use_graph_search or preset_config.get("use_graph_search", False))
        )

        search_settings: dict[str, Any] = {
            "use_semantic_search": use_semantic_search,
            "limit": limit,
        }

        # Apply hybrid search settings
        if final_use_hybrid:
            search_settings["use_hybrid_search"] = True
            hybrid_config = preset_config.get("hybrid_settings", {})
            search_settings["hybrid_settings"] = {
                "semantic_weight": semantic_weight
                if semantic_weight != 5.0 or preset == "default"
                else hybrid_config.get("semantic_weight", 5.0),
                "full_text_weight": full_text_weight
                if full_text_weight != 1.0 or preset == "default"
                else hybrid_config.get("full_text_weight", 1.0),
                "full_text_limit": full_text_limit
                if full_text_limit != 200 or preset == "default"
                else hybrid_config.get("full_text_limit", 200),
                "rrf_k": rrf_k
                if rrf_k != 50 or preset == "default"
                else hybrid_config.get("rrf_k", 50),
            }
            await ctx.info("Hybrid search enabled")

        # Apply graph search settings
        if final_use_graph:
            kg_type = (
                kg_search_type
                if kg_search_type != "local" or preset == "default"
                else preset_config.get("kg_search_type", "local")
            )
            search_settings["graph_search_settings"] = {
                "use_graph_search": True,
                "kg_search_type": kg_type,
            }
            await ctx.info(f"Knowledge graph search enabled (type: {kg_type})")

        # Apply search strategy if provided
        if search_strategy:
            search_settings["search_strategy"] = search_strategy
            await ctx.info(f"Search strategy: {search_strategy}")

        await ctx.report_progress(progress=30, total=100, message="Executing search")

        search_response = client.retrieval.search(
            query=query, search_settings=search_settings
        )

        await ctx.report_progress(progress=80, total=100, message="Formatting results")

        formatted = format_search_results_for_llm(search_response.results)

        await ctx.report_progress(progress=100, total=100, message="Complete")
        await ctx.info(
            f"Search completed successfully, returned {len(formatted)} chars"
        )

        return formatted
    except ValueError as e:
        await ctx.error(f"Validation error: {e!s}")
        raise
    except Exception as e:
        await ctx.error(f"Search failed: {e!s}")
        raise


@mcp.tool(
    annotations={
        "title": "R2R RAG",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    }
)
async def rag(
    query: str,
    ctx: Context,
    preset: str = "default",
    model: str = "vertex_ai/gemini-2.5-pro",
    temperature: float = 0.7,
    max_tokens: int | None = 8000,
    use_semantic_search: bool = True,
    use_hybrid_search: bool = False,
    use_graph_search: bool = True,
    limit: int = 100,
    kg_search_type: Literal["local", "global"] = "global",
    semantic_weight: float = 5.0,
    full_text_weight: float = 1.0,
    full_text_limit: int = 200,
    rrf_k: int = 50,
    search_strategy: str | None = None,
    include_web_search: bool = False,
    task_prompt_override: str | None = None,
) -> str:
    """
    Perform Retrieval-Augmented Generation (RAG) query with full parameter control.

    This tool retrieves relevant context from the knowledge base and generates an answer
    using a language model. Supports all search modes (semantic, hybrid, graph) and
    customizable generation parameters.

    Args:
        query: The question to answer using the knowledge base. Required.
        preset: Preset configuration for common use cases. Options:
            - "default": Basic RAG with gpt-4o-mini, temperature 0.7, 10 results
            - "development": Hybrid search with higher temperature for creative answers, 15 results
            - "refactoring": Hybrid + graph search with gpt-4o for code analysis, 20 results
            - "debug": Minimal graph search with low temperature for precise answers, 5 results
            - "research": Comprehensive search with gpt-4o for research questions, 30 results
            - "production": Balanced hybrid search optimized for production, 10 results
        model: LLM model to use for generation. Examples:
            - "vertex_ai/gemini-2.5-flash" (default, fast and cost-effective)
            - "vertex_ai/gemini-2.5-pro" (more capable, higher cost)
            - "openai/gpt-4-turbo" (high performance)
            - "anthropic/claude-3-haiku-20240307" (fast)
            - "anthropic/claude-3-sonnet-20240229" (balanced)
            - "anthropic/claude-3-opus-20240229" (most capable)
        temperature: Generation temperature controlling randomness. Must be between 0.0 and 1.0.
            Lower values (0.0-0.3) = more deterministic, precise answers
            Medium values (0.4-0.7) = balanced creativity and accuracy (default: 0.7)
            Higher values (0.8-1.0) = more creative, diverse answers
        max_tokens: Maximum number of tokens to generate. Optional, uses model default if not specified.
        use_semantic_search: Enable semantic/vector search for retrieval (default: True)
        use_hybrid_search: Enable hybrid search combining semantic and full-text search (default: False)
        use_graph_search: Enable knowledge graph search for entity/relationship context (default: False)
        limit: Maximum number of search results to retrieve. Must be between 1 and 100 (default: 10)
        kg_search_type: Knowledge graph search type. "local" for local context, "global" for broader connections (default: "local")
        semantic_weight: Weight for semantic search in hybrid mode. Must be between 0.0 and 10.0 (default: 5.0)
        full_text_weight: Weight for full-text search in hybrid mode. Must be between 0.0 and 10.0 (default: 1.0)
        full_text_limit: Maximum full-text results to consider in hybrid search. Must be between 1 and 1000 (default: 200)
        rrf_k: Reciprocal Rank Fusion parameter for hybrid search. Must be between 1 and 100 (default: 50)
        search_strategy: Advanced search strategy (e.g., "hyde", "rag_fusion"). Optional.
        include_web_search: Include web search results from the internet (default: False)
        task_prompt_override: Custom system prompt to override the default RAG task prompt.
            Useful for specializing AI behavior for specific domains or tasks. Optional.

    Returns:
        Generated answer based on relevant context from the knowledge base.

    Examples:
        # Simple RAG query
        rag("What is machine learning?")

        # Development preset for code questions
        rag("How to implement async/await in Python?", preset="development")

        # Custom RAG with specific model and temperature
        rag("Explain neural networks", model="vertex_ai/gemini-2.5-pro", temperature=0.5)

        # Research preset with comprehensive search
        rag("Latest developments in transformer architectures", preset="research")

        # Debug preset for precise technical answers
        rag("What causes this error?", preset="debug")
    """
    await ctx.info(f"RAG query: {query}, preset: {preset}, model: {model}")

    try:
        # Validate parameters
        validate_limit(limit)
        validate_temperature(temperature)
        validate_semantic_weight(semantic_weight)
        validate_full_text_weight(full_text_weight)
        validate_full_text_limit(full_text_limit)
        validate_rrf_k(rrf_k)
        if use_graph_search:
            validate_kg_search_type(kg_search_type)

        await ctx.report_progress(progress=10, total=100, message="Initializing RAG")

        client = R2RClient(base_url=R2R_BASE_URL)
        if API_KEY:
            client.set_api_key(API_KEY)

        # Get preset configuration and merge with explicit parameters
        preset_config = get_rag_preset_config(preset)

        # Apply preset values, but allow explicit parameters to override
        final_use_hybrid = (
            use_hybrid_search
            if preset == "default"
            else (
                use_hybrid_search
                or preset_config["search_settings"].get("use_hybrid_search", False)
            )
        )
        final_use_graph = (
            use_graph_search
            if preset == "default"
            else (
                use_graph_search
                or preset_config["search_settings"].get("use_graph_search", False)
            )
        )

        search_settings: dict[str, Any] = {
            "use_semantic_search": use_semantic_search,
            "limit": limit,
        }

        # Apply hybrid search settings
        if final_use_hybrid:
            search_settings["use_hybrid_search"] = True
            hybrid_config = preset_config["search_settings"].get("hybrid_settings", {})
            search_settings["hybrid_settings"] = {
                "semantic_weight": semantic_weight
                if semantic_weight != 5.0 or preset == "default"
                else hybrid_config.get("semantic_weight", 5.0),
                "full_text_weight": full_text_weight
                if full_text_weight != 1.0 or preset == "default"
                else hybrid_config.get("full_text_weight", 1.0),
                "full_text_limit": full_text_limit
                if full_text_limit != 200 or preset == "default"
                else hybrid_config.get("full_text_limit", 200),
                "rrf_k": rrf_k
                if rrf_k != 50 or preset == "default"
                else hybrid_config.get("rrf_k", 50),
            }
            await ctx.info("Hybrid search enabled for RAG")

        # Apply graph search settings
        if final_use_graph:
            kg_type = (
                kg_search_type
                if kg_search_type != "local" or preset == "default"
                else preset_config["search_settings"].get("kg_search_type", "local")
            )
            search_settings["graph_search_settings"] = {
                "use_graph_search": True,
                "kg_search_type": kg_type,
            }
            await ctx.info(f"Knowledge graph search enabled (type: {kg_type})")

        # Apply search strategy if provided
        if search_strategy:
            search_settings["search_strategy"] = search_strategy
            await ctx.info(f"Search strategy: {search_strategy}")

        # Build RAG generation config
        rag_model = (
            model
            if model != "vertex_ai/gemini-2.5-flash"
            else preset_config["rag_generation_config"].get(
                "model", "vertex_ai/gemini-2.5-flash"
            )
        )
        rag_temp = (
            temperature
            if temperature != 0.7
            else preset_config["rag_generation_config"].get("temperature", 0.7)
        )
        rag_generation_config: dict[str, Any] = {
            "model": rag_model,
            "temperature": rag_temp,
            "stream": False,
        }
        if max_tokens is not None:
            rag_generation_config["max_tokens"] = max_tokens

        await ctx.report_progress(progress=30, total=100, message="Retrieving context")

        try:
            rag_kwargs: dict[str, Any] = {
                "query": query,
                "search_settings": search_settings if search_settings else None,
                "rag_generation_config": rag_generation_config,
                "include_web_search": include_web_search,
            }
            if task_prompt_override:
                rag_kwargs["task_prompt"] = task_prompt_override

            rag_response = client.retrieval.rag(**rag_kwargs)

            await ctx.report_progress(
                progress=90, total=100, message="Generating answer"
            )

            answer = rag_response.results.generated_answer  # type: ignore

            await ctx.report_progress(progress=100, total=100, message="Complete")
            await ctx.info("RAG completed successfully")

            return answer
        except Exception as e:
            await ctx.error(f"RAG generation failed: {e!s}")
            raise
    except ValueError as e:
        await ctx.error(f"Validation error: {e!s}")
        raise
    except Exception as e:
        await ctx.error(f"RAG failed: {e!s}")
        raise


# Create ASGI application for production deployment (Uvicorn, ChatMCP, etc.)
app = mcp.http_app()

# Run the server if executed directly (for local testing)
if __name__ == "__main__":
    # For local development, use HTTP transport
    # Accessible at http://localhost:8000/mcp
    mcp.run()
