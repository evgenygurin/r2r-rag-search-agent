import os

# Enable new OpenAPI parser FIRST - before any imports
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get configuration from environment
R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
API_KEY = os.getenv("API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from fastmcp import Client, FastMCP  # noqa: E402
from google import genai  # noqa: E402


def create_mcp_server() -> FastMCP:
    """Create and configure MCP server with OpenAPI spec."""
    # Warn if API_KEY is not set (optional for R2R instances without auth)
    if not API_KEY:
        import warnings

        warnings.warn(
            "API_KEY is not set. R2R API requests may fail with 401 "
            "Unauthorized if the R2R server requires authentication. "
            "Configure API_KEY in environment variables if needed.",
            stacklevel=2,
        )

    # Prepare headers for authentication (same format as R2R SDK)
    # Only include x-api-key if API_KEY is set
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if API_KEY:
        headers["x-api-key"] = API_KEY

    # Create authenticated async HTTP client for API requests
    client = httpx.AsyncClient(
        base_url=R2R_BASE_URL,
        headers=headers,
        timeout=30.0,
    )

    # Load OpenAPI spec synchronously for module-level initialization
    with httpx.Client(headers=headers, timeout=10.0) as temp_client:
        # Load OpenAPI spec - this also validates server connectivity and auth
        try:
            response = temp_client.get(f"{R2R_BASE_URL}/openapi.json")
            response.raise_for_status()
            openapi_spec = response.json()

            # Validate OpenAPI spec structure
            if "paths" not in openapi_spec:
                raise ValueError("Invalid OpenAPI specification: missing 'paths' field")

            # ВАЖНО: Удаляем HTTPBearer и OAuth2PasswordBearer схемы из OpenAPI spec
            # Оставляем только APIKeyHeader (x-api-key), чтобы избежать конфликта
            # "Cannot have both Bearer token and API key"
            if (
                "components" in openapi_spec
                and "securitySchemes" in openapi_spec["components"]
            ):
                security_schemes = openapi_spec["components"]["securitySchemes"]
                # Сохраняем только APIKeyHeader схему
                openapi_spec["components"]["securitySchemes"] = {
                    "APIKeyHeader": security_schemes.get("APIKeyHeader", {})
                }

            # Устанавливаем security requirements на уровне спецификации
            # Используем только APIKeyHeader для всех endpoints (всегда, не только если есть)
            openapi_spec["security"] = [{"APIKeyHeader": []}]

            # КРИТИЧНО: УДАЛЯЕМ все security requirements на уровне операций
            # Оставляем только глобальный security, чтобы избежать конфликтов
            removed_count = 0
            if "paths" in openapi_spec:
                for path_item in openapi_spec["paths"].values():
                    for method, operation in path_item.items():
                        if (
                            method
                            in [
                                "get",
                                "post",
                                "put",
                                "patch",
                                "delete",
                                "options",
                                "head",
                            ]
                            and isinstance(operation, dict)
                            and "security" in operation
                        ):
                            # Полностью удаляем security на уровне операции
                            # Операция будет использовать глобальный security
                            del operation["security"]
                            removed_count += 1

            import sys

            print(
                f"[OpenAPI] Removed security from {removed_count} operations",
                file=sys.stderr,
            )
            print(
                f"[OpenAPI] Global security: {openapi_spec.get('security', [])}",
                file=sys.stderr,
            )
            schemes = openapi_spec.get("components", {}).get("securitySchemes", {})
            print(
                f"[OpenAPI] Security schemes: {list(schemes.keys())}",
                file=sys.stderr,
            )

        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot connect to R2R server at {R2R_BASE_URL}.\n"
                "Please ensure R2R is running. To start R2R:\n"
                "  docker run -d -p 7272:7272 ragtoriches/prod:latest\n"
                f"Or follow: https://r2r-docs.sciphi.ai/installation\n"
                f"Error details: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ConnectionError(
                    f"Authentication failed: 401 Unauthorized.\n"
                    f"Please check your API_KEY in .env file.\n"
                    f"Current R2R_BASE_URL: {R2R_BASE_URL}"
                ) from e
            else:
                raise ConnectionError(
                    f"R2R server returned error {e.response.status_code}.\n"
                    f"URL: {R2R_BASE_URL}/openapi.json\n"
                    f"Response: {e.response.text[:200]}"
                ) from e

    # Create MCP server from OpenAPI spec with authenticated client
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
