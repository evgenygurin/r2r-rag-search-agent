import os

# Enable new OpenAPI parser FIRST - before any imports
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

from dotenv import load_dotenv
import httpx
from fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Get configuration from environment
R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://localhost:7272")
API_KEY = os.getenv("API_KEY")


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

if __name__ == "__main__":
    mcp.run()
