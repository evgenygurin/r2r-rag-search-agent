from fastmcp import Client
from google import genai
import asyncio
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://localhost:7272")
API_KEY = os.getenv("API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

mcp_client = Client("server.py")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

async def main():    
    async with mcp_client:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents="используй r2r mcp инструмент rag, для поиска всей документации по FastMCP с примерами кода 20 штук",
            config=genai.types.GenerateContentConfig(
                temperature=0.4,
                tools=[mcp_client.session],  # Pass the FastMCP client session
            ),
        )
        print(response.text)

if __name__ == "__main__":
    asyncio.run(main())
