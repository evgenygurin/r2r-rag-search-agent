#!/usr/bin/env python3
"""Отладка headers в FastMCP.from_openapi()."""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
API_KEY = os.getenv("API_KEY")

# Enable new OpenAPI parser
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

from fastmcp import FastMCP


def main():
    """Проверка headers в AsyncClient."""
    print("=" * 70)
    print("ОТЛАДКА FASTMCP HEADERS")
    print("=" * 70)
    print()

    # Test 1: Authorization Bearer
    print("Тест 1: Authorization: Bearer header")
    print("-" * 70)
    headers1 = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    client1 = httpx.AsyncClient(
        base_url=R2R_BASE_URL,
        headers=headers1,
        timeout=30.0,
    )
    print(f"Установленные headers:")
    for key, value in client1.headers.items():
        if key.lower() in ['authorization', 'x-api-key']:
            print(f"   {key}: {value[:30]}...")
    print()

    # Test 2: x-api-key
    print("Тест 2: x-api-key header")
    print("-" * 70)
    headers2 = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }
    client2 = httpx.AsyncClient(
        base_url=R2R_BASE_URL,
        headers=headers2,
        timeout=30.0,
    )
    print(f"Установленные headers:")
    for key, value in client2.headers.items():
        if key.lower() in ['authorization', 'x-api-key']:
            print(f"   {key}: {value[:30]}...")
    print()

    # Test 3: Проверка OpenAPI spec security schemes
    print("Тест 3: Проверка OpenAPI spec securitySchemes")
    print("-" * 70)
    with httpx.Client(headers=headers2, timeout=10.0) as temp_client:
        response = temp_client.get(f"{R2R_BASE_URL}/openapi.json")
        openapi_spec = response.json()

        if "components" in openapi_spec and "securitySchemes" in openapi_spec["components"]:
            print("SecuritySchemes в OpenAPI spec:")
            for scheme_name, scheme_config in openapi_spec["components"]["securitySchemes"].items():
                print(f"   {scheme_name}: {scheme_config}")
        else:
            print("   Нет securitySchemes в OpenAPI spec")
    print()

    print("=" * 70)


if __name__ == "__main__":
    main()
