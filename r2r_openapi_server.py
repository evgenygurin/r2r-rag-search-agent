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
R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
API_KEY = os.getenv("API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def create_mcp_server() -> FastMCP:
    """Create and configure MCP server with OpenAPI spec."""
    # Validate API_KEY is set
    if not API_KEY:
        raise ValueError(
            "API_KEY is not set. Please configure it in .env file or environment variables.\n"
            "Without API_KEY, all R2R API requests will fail with 401 Unauthorized."
        )

    # Create HTTP client for API requests
    headers: dict[str, str] = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    client = httpx.AsyncClient(base_url=R2R_BASE_URL, headers=headers)

    # Load OpenAPI spec synchronously for module-level initialization
    # Note: Use the same headers for authentication
    with httpx.Client(headers=headers, timeout=10.0) as temp_client:
        # Load OpenAPI spec - this also validates server connectivity and auth
        try:
            response = temp_client.get(f"{R2R_BASE_URL}/openapi.json")
            response.raise_for_status()
            openapi_spec = response.json()

            # Validate OpenAPI spec structure
            if "paths" not in openapi_spec:
                raise ValueError("Invalid OpenAPI specification: missing 'paths' field")

        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot connect to R2R server at {R2R_BASE_URL}.\n"
                "Please ensure R2R is running. To start R2R:\n"
                "  docker run -d -p 7272:7272 ragtoriches/prod:latest\n"
                f"Or follow: https://r2r-docs.sciphi.ai/installation\n"
                f"Error details: {e}"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ConnectionError(
                    f"Authentication failed: 401 Unauthorized.\n"
                    f"Please check your API_KEY in .env file.\n"
                    f"Current R2R_BASE_URL: {R2R_BASE_URL}"
                )
            else:
                raise ConnectionError(
                    f"R2R server returned error {e.response.status_code}.\n"
                    f"URL: {R2R_BASE_URL}/openapi.json\n"
                    f"Response: {e.response.text[:200]}"
                )

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
    mcp.run()
    # # Check if running in Gemini mode
    # if len(sys.argv) > 1 and sys.argv[1] == "--gemini":
    #     # Gemini mode: run query through Gemini with MCP tools
    #     if len(sys.argv) < 3:
    #         print("Usage: python r2r_openapi_server.py --gemini 'your query here'")
    #         sys.exit(1)

    #     query = sys.argv[2]
    #     result = asyncio.run(run_with_gemini(query))
    #     print(f"\nGemini Response:\n{result}\n")
    # else:
    #     # MCP server mode (default)
    #     mcp.run()
