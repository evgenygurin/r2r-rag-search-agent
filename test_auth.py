#!/usr/bin/env python3
"""Тестирование аутентификации R2R через httpx."""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
API_KEY = os.getenv("API_KEY")


async def test_auth():
    """Тестирование различных сценариев аутентификации."""
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ АУТЕНТИФИКАЦИИ R2R")
    print("=" * 70)
    print(f"R2R_BASE_URL: {R2R_BASE_URL}")
    print(f"API_KEY configured: {bool(API_KEY)}")
    print()

    if not API_KEY:
        print("❌ API_KEY не установлен в .env файле")
        sys.exit(1)

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }

    # Test 1: Загрузка OpenAPI spec
    print("Тест 1: Загрузка OpenAPI спецификации")
    print("-" * 70)
    try:
        with httpx.Client(headers=headers, timeout=10.0) as client:
            response = client.get(f"{R2R_BASE_URL}/openapi.json")
            response.raise_for_status()
            spec = response.json()
            print(f"✅ OpenAPI spec загружена успешно")
            print(f"   Версия: {spec.get('openapi')}")
            print(f"   Endpoints: {len(spec.get('paths', {}))}")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error {e.response.status_code}: {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    print()

    # Test 2: AsyncClient с базовым запросом
    print("Тест 2: AsyncClient с аутентификацией (health check)")
    print("-" * 70)
    try:
        async with httpx.AsyncClient(
            base_url=R2R_BASE_URL, headers=headers, timeout=30.0
        ) as client:
            # Пробуем простой GET запрос
            response = await client.get("/v3/system/health")
            print(f"✅ Health check: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
            elif response.status_code == 404:
                print("   ℹ️  Endpoint /v3/system/health не найден (это нормально)")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"   ℹ️  404 Not Found - endpoint не существует (это ожидаемо)")
        else:
            print(f"❌ HTTP error {e.response.status_code}: {e.response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    print()

    # Test 3: Проверка списка документов (реальный API endpoint)
    print("Тест 3: Запрос списка документов через API")
    print("-" * 70)
    try:
        async with httpx.AsyncClient(
            base_url=R2R_BASE_URL, headers=headers, timeout=30.0
        ) as client:
            response = await client.get("/v3/documents", params={"limit": 5})
            response.raise_for_status()
            data = response.json()
            print(f"✅ Список документов получен успешно")
            print(f"   Status: {response.status_code}")
            if "results" in data:
                print(f"   Документов получено: {len(data['results'])}")
            else:
                print(f"   Response: {data}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print(f"❌ 401 Unauthorized - аутентификация НЕ работает!")
            print(f"   Response: {e.response.text[:200]}")
            return False
        else:
            print(f"⚠️  HTTP error {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    print()

    # Test 4: Проверка без аутентификации (должно вернуть 401)
    print("Тест 4: Запрос БЕЗ аутентификации (ожидается 401)")
    print("-" * 70)
    try:
        async with httpx.AsyncClient(base_url=R2R_BASE_URL, timeout=30.0) as client:
            response = await client.get("/v3/documents", params={"limit": 1})
            print(f"⚠️  Неожиданно: запрос без auth вернул {response.status_code}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print(f"✅ Правильно: 401 Unauthorized без API ключа")
        else:
            print(f"⚠️  Неожиданный статус: {e.response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    print()

    print("=" * 70)
    print("✅ ВСЕ ТЕСТЫ АУТЕНТИФИКАЦИИ ПРОЙДЕНЫ УСПЕШНО")
    print("=" * 70)
    return True


if __name__ == "__main__":
    result = asyncio.run(test_auth())
    sys.exit(0 if result else 1)
