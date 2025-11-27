#!/usr/bin/env python3
"""Отладка headers, отправляемых в R2R."""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

R2R_BASE_URL = os.getenv("R2R_BASE_URL", "http://127.0.0.1:7272")
API_KEY = os.getenv("API_KEY")


async def test_headers():
    """Тестирование различных форматов headers."""
    print("=" * 70)
    print("ОТЛАДКА HEADERS R2R")
    print("=" * 70)
    print(f"R2R_BASE_URL: {R2R_BASE_URL}")
    print(f"API_KEY: {API_KEY[:20]}..." if API_KEY else "API_KEY: None")
    print()

    # Test 1: Authorization Bearer (как в документации)
    print("Тест 1: Authorization: Bearer format (R2R документация)")
    print("-" * 70)
    headers1 = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(base_url=R2R_BASE_URL, headers=headers1, timeout=30.0) as client:
        try:
            response = await client.get("/v3/documents", params={"limit": 1})
            print(f"✅ Status: {response.status_code}")
            print(f"   Headers sent: {dict(client.headers)}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
        except httpx.HTTPStatusError as e:
            print(f"❌ Error {e.response.status_code}: {e.response.text[:200]}")
    print()

    # Test 2: x-api-key (как в SDK)
    print("Тест 2: x-api-key format (R2R SDK)")
    print("-" * 70)
    headers2 = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(base_url=R2R_BASE_URL, headers=headers2, timeout=30.0) as client:
        try:
            response = await client.get("/v3/documents", params={"limit": 1})
            print(f"✅ Status: {response.status_code}")
            print(f"   Headers sent: {dict(client.headers)}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
        except httpx.HTTPStatusError as e:
            print(f"❌ Error {e.response.status_code}: {e.response.text[:200]}")
    print()

    # Test 3: Оба header (ошибка)
    print("Тест 3: Оба headers одновременно (должна быть ошибка)")
    print("-" * 70)
    headers3 = {
        "Authorization": f"Bearer {API_KEY}",
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(base_url=R2R_BASE_URL, headers=headers3, timeout=30.0) as client:
        try:
            response = await client.get("/v3/documents", params={"limit": 1})
            print(f"⚠️  Status: {response.status_code}")
            print(f"   Headers sent: {dict(client.headers)}")
        except httpx.HTTPStatusError as e:
            print(f"✅ Ожидаемая ошибка {e.response.status_code}: {e.response.text[:200]}")
    print()

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_headers())
