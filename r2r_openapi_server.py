import asyncio
import os
import sys

# Enable new OpenAPI parser FIRST - before any imports
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

import httpx
from dotenv import load_dotenv
from fastmcp import Client, FastMCP
from google import genai

# Load environment variables
load_dotenv()

# Get configuration from environment
R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://localhost:7272")
API_KEY = os.getenv("API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def create_mcp_server() -> FastMCP:
    """Create and configure MCP server with OpenAPI spec."""
    # Create HTTP client for API requests
    headers: dict[str, str] = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    client = httpx.AsyncClient(base_url=R2R_BASE_URL, headers=headers)

    # Load OpenAPI spec synchronously for module-level initialization
    with httpx.Client() as temp_client:
        response = temp_client.get(f"{R2R_BASE_URL}/openapi.json")
        response.raise_for_status()
        openapi_spec = response.json()

    # Create MCP server from OpenAPI spec
    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name="R2R OpenAPI Server",
    )

    return mcp


# Create server instance (synchronous for uvicorn compatibility)
mcp = create_mcp_server()

# Export ASGI app for production deployment
app = mcp.http_app(transport="streamable-http", path="/mcp")


async def run_with_gemini(query: str, model: str = "gemini-2.0-flash") -> str:
    """
    Run query through Gemini with R2R MCP tools integration.

    Args:
        query: User query to process
        model: Gemini model to use (default: gemini-2.0-flash)

    Returns:
        Generated response from Gemini

    Example:
        >>> asyncio.run(run_with_gemini("Search for information about neural networks"))
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY not set. Please configure it in .env file or environment."
        )

    # Create MCP client pointing to this server
    mcp_client = Client(__file__)

    # Create Gemini client
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # Execute query with MCP tools
    async with mcp_client:
        response = await gemini_client.aio.models.generate_content(
            model=model,
            contents=query,
            config=genai.types.GenerateContentConfig(
                temperature=0.7,
                tools=[mcp_client.session],  # Pass MCP client session
            ),
        )
        return response.text or ""


if __name__ == "__main__":
    # Check if running in Gemini mode
    if len(sys.argv) > 1 and sys.argv[1] == "--gemini":
        # Gemini mode: run query through Gemini with MCP tools
        if len(sys.argv) < 3:
            print("Usage: python r2r_openapi_server.py --gemini 'your query here'")
            sys.exit(1)

        query = sys.argv[2]
        result = asyncio.run(run_with_gemini(query))
        print(f"\nGemini Response:\n{result}\n")
    else:
        # MCP server mode (default)
        mcp.run()
