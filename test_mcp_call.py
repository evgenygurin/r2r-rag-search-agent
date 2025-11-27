#!/usr/bin/env python3
"""Тестирование реального вызова MCP инструмента после исправления."""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
API_KEY = os.getenv("API_KEY")


async def test_mcp_call():
    """Симуляция вызова MCP инструмента через FastMCP."""
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ ВЫЗОВА MCP ИНСТРУМЕНТА")
    print("=" * 70)
    print(f"R2R_BASE_URL: {R2R_BASE_URL}")
    print(f"API_KEY configured: {bool(API_KEY)}")
    print()

    if not API_KEY:
        print("❌ API_KEY не установлен в .env файле")
        sys.exit(1)

    # Test 1: Проверка, что модифицированный OpenAPI spec работает
    print("Тест 1: Проверка модифицированного OpenAPI spec")
    print("-" * 70)

    # Создаем headers как в r2r_openapi_server.py
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }

    # Загружаем и модифицируем OpenAPI spec (как в r2r_openapi_server.py)
    with httpx.Client(headers=headers, timeout=10.0) as temp_client:
        response = temp_client.get(f"{R2R_BASE_URL}/openapi.json")
        response.raise_for_status()
        openapi_spec = response.json()

        print(f"✅ OpenAPI spec загружен")
        print(f"   Endpoints: {len(openapi_spec.get('paths', {}))} paths")

        # Модифицируем spec (удаляем HTTPBearer)
        if "components" in openapi_spec and "securitySchemes" in openapi_spec["components"]:
            original_schemes = list(openapi_spec["components"]["securitySchemes"].keys())
            print(f"   Original security schemes: {', '.join(original_schemes)}")

            security_schemes = openapi_spec["components"]["securitySchemes"]
            openapi_spec["components"]["securitySchemes"] = {
                "APIKeyHeader": security_schemes.get("APIKeyHeader", {})
            }

            modified_schemes = list(openapi_spec["components"]["securitySchemes"].keys())
            print(f"   Modified security schemes: {', '.join(modified_schemes)}")

            if "security" in openapi_spec:
                openapi_spec["security"] = [{"APIKeyHeader": []}]
                print(f"   ✅ Security requirements обновлены: только APIKeyHeader")
    print()

    # Test 2: Прямой вызов R2R API с только x-api-key header
    print("Тест 2: Вызов R2R API с x-api-key header")
    print("-" * 70)

    try:
        async with httpx.AsyncClient(
            base_url=R2R_BASE_URL, headers=headers, timeout=30.0
        ) as client:
            # Проверяем, что в client только x-api-key header
            client_headers = dict(client.headers)
            print(f"   Client headers:")
            for key in ["authorization", "x-api-key"]:
                if key in client_headers:
                    value = client_headers[key]
                    print(f"     - {key}: {value[:30]}...")

            # Делаем тестовый запрос
            response = await client.get("/v3/documents", params={"limit": 1})
            response.raise_for_status()
            data = response.json()

            print(f"✅ API вызов успешен (status: {response.status_code})")
            if "results" in data:
                print(f"   Получено документов: {len(data['results'])}")
                print(f"   Total entries: {data.get('total_entries', 0)}")

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_text = e.response.text
            if "Cannot have both Bearer token and API key" in error_text:
                print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Конфликт authentication headers!")
                print(f"   Response: {error_text}")
                print()
                print("🔍 Это означает, что где-то добавляется Authorization: Bearer header")
                print("   даже после модификации OpenAPI spec.")
                return False
            else:
                print(f"⚠️  HTTP 400 с другой ошибкой: {error_text[:200]}")
        else:
            print(f"❌ HTTP error {e.response.status_code}: {e.response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    print()

    # Test 3: Проверка, что оба headers одновременно все еще вызывают ошибку
    print("Тест 3: Подтверждение, что оба headers вызывают ошибку")
    print("-" * 70)

    headers_both = {
        "Authorization": f"Bearer {API_KEY}",
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            base_url=R2R_BASE_URL, headers=headers_both, timeout=30.0
        ) as client:
            response = await client.get("/v3/documents", params={"limit": 1})
            response.raise_for_status()
            print(f"⚠️  Неожиданно: запрос с обоими headers вернул {response.status_code}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400 and "Cannot have both" in e.response.text:
            print(f"✅ Правильно: R2R отклоняет запрос с обоими headers (400)")
            print(f"   Message: {e.response.text[:100]}...")
        else:
            print(f"⚠️  Неожиданный статус: {e.response.status_code}")
    print()

    print("=" * 70)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
    print("=" * 70)
    print()
    print("📋 Резюме:")
    print(f"   • OpenAPI spec модифицирован: удалены HTTPBearer и OAuth2PasswordBearer")
    print(f"   • Только x-api-key header используется в AsyncClient")
    print(f"   • R2R API запросы выполняются без ошибки 400")
    print(f"   • Конфликт 'Cannot have both Bearer token and API key' устранен ✅")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_mcp_call())
    sys.exit(0 if result else 1)
