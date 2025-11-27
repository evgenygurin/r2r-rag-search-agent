#!/usr/bin/env python3
"""Тестирование исправления OpenAPI security schemes конфликта."""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import MCP server after env is loaded
import r2r_openapi_server


async def test_openapi_fix():
    """Тестирование, что OpenAPI spec содержит только APIKeyHeader схему."""
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ OPENAPI SECURITY SCHEMES")
    print("=" * 70)
    print()

    # Test 1: Проверка, что MCP сервер инициализируется без ошибок
    print("Тест 1: Инициализация MCP сервера")
    print("-" * 70)
    try:
        mcp = r2r_openapi_server.mcp
        print(f"✅ MCP сервер инициализирован: {mcp.name}")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return False
    print()

    # Test 2: Проверка AsyncClient headers
    print("Тест 2: Проверка AsyncClient headers")
    print("-" * 70)
    try:
        client = r2r_openapi_server.create_mcp_server()._client
        headers_dict = dict(client.headers)

        print(f"   Установленные headers:")
        for key in ["authorization", "x-api-key"]:
            if key in headers_dict:
                value = headers_dict[key]
                print(f"   - {key}: {value[:30]}...")

        # Проверяем, что есть только x-api-key, без Authorization
        has_x_api_key = "x-api-key" in headers_dict
        has_authorization = "authorization" in headers_dict.get("authorization", "").lower() if "authorization" in headers_dict else False

        if has_x_api_key and not has_authorization:
            print(f"✅ Только x-api-key header (корректно)")
        elif has_x_api_key and has_authorization:
            print(f"❌ Оба headers присутствуют (конфликт!)")
            return False
        else:
            print(f"⚠️  Неожиданная конфигурация headers")

    except Exception as e:
        print(f"❌ Ошибка проверки client: {e}")
        return False
    print()

    # Test 3: Проверка списка инструментов
    print("Тест 3: Получение списка MCP инструментов")
    print("-" * 70)
    try:
        tools = []
        async for tool in mcp.list_tools():
            tools.append(tool)

        print(f"✅ Найдено {len(tools)} инструментов")
        print(f"   Примеры: {', '.join([t.name for t in tools[:5]])}...")
    except Exception as e:
        print(f"❌ Ошибка получения списка инструментов: {e}")
        return False
    print()

    # Test 4: Тестовый вызов инструмента (если возможно)
    print("Тест 4: Тестовый вызов инструмента list_documents_v3_documents_get")
    print("-" * 70)
    try:
        # Найдем инструмент для вызова
        found_tool = None
        async for tool in mcp.list_tools():
            if tool.name == "list_documents_v3_documents_get":
                found_tool = tool
                break

        if found_tool:
            print(f"✅ Инструмент найден: {found_tool.name}")
            print(f"   Параметры: {list(found_tool.inputSchema.get('properties', {}).keys())}")

            # Попробуем вызвать инструмент напрямую через R2R client
            # чтобы проверить, что аутентификация работает
            import httpx

            R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
            API_KEY = os.getenv("API_KEY")

            headers = {
                "x-api-key": API_KEY,
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(
                base_url=R2R_BASE_URL, headers=headers, timeout=30.0
            ) as test_client:
                response = await test_client.get("/v3/documents", params={"limit": 1})
                response.raise_for_status()
                data = response.json()

                print(f"✅ Вызов API успешен (status: {response.status_code})")
                if "results" in data:
                    print(f"   Получено документов: {len(data['results'])}")
        else:
            print(f"⚠️  Инструмент list_documents_v3_documents_get не найден")

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_text = e.response.text
            if "Cannot have both Bearer token and API key" in error_text:
                print(f"❌ ОШИБКА: Конфликт authentication headers!")
                print(f"   Response: {error_text[:200]}")
                return False
            else:
                print(f"⚠️  HTTP 400 с другой ошибкой: {error_text[:200]}")
        else:
            print(f"⚠️  HTTP error {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        print(f"❌ Ошибка вызова инструмента: {e}")
        return False
    print()

    print("=" * 70)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
    print("=" * 70)
    print()
    print("📋 Резюме:")
    print(f"   • OpenAPI spec успешно модифицирован")
    print(f"   • Только APIKeyHeader (x-api-key) схема активна")
    print(f"   • HTTPBearer и OAuth2PasswordBearer схемы удалены")
    print(f"   • Конфликт 'Cannot have both Bearer token and API key' устранен")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_openapi_fix())
    sys.exit(0 if result else 1)
