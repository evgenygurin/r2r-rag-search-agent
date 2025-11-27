# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 Обзор проекта

MCP-сервер для интеграции R2R (Retrieval-Augmented Generation) с Claude Desktop через Model Context Protocol.

**Доступные реализации серверов:**
- `server.py` — Кастомный MCP сервер с 5 специализированными инструментами и ресурсами
- `r2r_openapi_server.py` — Автогенерация из OpenAPI спецификации R2R (114 маршрутов из полного R2R API)

### Доступные инструменты (Tools)

**Базовые:**
- `search` — векторный поиск по базе знаний R2R с логированием и progress tracking
- `rag` — полноценный RAG-запрос с генерацией ответа

**Расширенные:**
- `advanced_search` — поиск с hybrid search (семантический + full-text), настраиваемыми весами и фильтрами
- `graph_search` — поиск с интеграцией knowledge graph для улучшенных результатов
- `advanced_rag` — RAG с настройками модели, температуры, hybrid search и веб-поиском

### Доступные ресурсы (Resources)

- `r2r://config` — текущая конфигурация сервера (URL, API key status)
- `r2r://health` — проверка здоровья и доступности R2R сервера

### Ключевые особенности

- **Context-aware logging**: Все инструменты используют FastMCP Context для логирования и отслеживания прогресса
- **Error handling middleware**: Централизованная обработка ошибок с детальным логированием
- **Tool annotations**: Метаданные для клиентов (readOnlyHint, idempotentHint, etc.)
- **Progress reporting**: Визуальное отслеживание выполнения длительных операций

### Структура проекта

```text
r2r-rag-search-agent/
├── server.py              # Кастомный MCP сервер с 5 инструментами (FastMCP)
├── r2r_openapi_server.py  # OpenAPI-based MCP сервер (114 маршрута, автогенерация)
├── pyproject.toml         # Конфигурация проекта и зависимости (uv)
├── uv.lock               # Lock-файл зависимостей
├── .python-version       # Версия Python (3.12)
├── Makefile              # Команды для разработки
├── .env                  # Переменные окружения (не в git)
├── .env.example          # Шаблон для .env
├── .gitignore            # Исключения для git
├── CLAUDE.md             # Документация для Claude Code
└── README.md             # Основная документация
```

### Архитектурные решения

**Почему FastMCP вместо низкоуровневого MCP SDK:**
- FastMCP упрощает регистрацию инструментов через декораторы
- Автоматическая валидация параметров и типизация
- Поддержка нескольких транспортов (HTTP, stdio, streamable-http) через единый API
- server.py:105 — инициализация FastMCP сервера
- server.py:154 — экспорт ASGI приложения для production (`app = mcp.http_app(transport="streamable-http", path="/mcp")`)

**Структура форматирования результатов (server.py:22-91):**
- `format_search_results_for_llm()` агрегирует 4 типа результатов:
  - Chunk search (векторный поиск по фрагментам)
  - Graph search (граф сущностей/отношений)
  - Web search (поиск в интернете)
  - Document search (локальные документы с чанками)
- Короткие ID через `id_to_shorthand()` для экономии токенов (первые 7 символов)

**Error Handling Middleware (server.py:105-133):**
- `R2RErrorHandlingMiddleware` перехватывает все ошибки в MCP операциях
- Логирует ошибки с контекстом (тип ошибки, метод, детали)
- Отслеживает статистику ошибок по типам
- Специальная обработка R2R connection errors с понятными сообщениями

**Context Integration (server.py:136+):**
- Все tools используют `Context` для:
  - Логирования (`ctx.info()`, `ctx.error()`, `ctx.debug()`)
  - Progress reporting (`ctx.report_progress(progress, total, message)`)
  - Request tracking (`ctx.request_id`)
- Context автоматически инжектится через type hint `ctx: Context`

**OpenAPI Server Architecture (r2r_openapi_server.py):**
- **Автогенерация инструментов:** FastMCP.from_openapi() создаёт MCP tools из OpenAPI спецификации
- **Новый парсер:** `os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"` устанавливается ДО импортов (r2r_openapi_server.py:4)
- **Синхронная инициализация:** OpenAPI spec загружается синхронно для совместимости с uvicorn (r2r_openapi_server.py:18-40)
- **Единый HTTP client:** httpx.AsyncClient с базовым URL и `x-api-key` header для всех запросов
- **114 маршрутов:** Полный R2R REST API доступен через MCP инструменты
- **ASGI экспорт:** `app = mcp.http_app(transport="streamable-http", path="/mcp")` для production деплоя (r2r_openapi_server.py:47)
- **Uvicorn compatibility:** Использует синхронную загрузку спецификации, чтобы избежать `asyncio.run()` конфликта с event loop

**Аутентификация и Security Schemes (r2r_openapi_server.py:32-70):**
- **R2R SDK совместимость:** Используется `x-api-key` header вместо `Authorization: Bearer` (как в R2R SDK)
- **Причина:** R2R SDK использует два взаимоисключающих метода аутентификации:
  - `x-api-key: <key>` для API ключей (наш случай)
  - `Authorization: Bearer <token>` для OAuth access tokens
- **OpenAPI spec модификация:** OpenAPI spec от R2R содержит 3 security schemes (HTTPBearer, APIKeyHeader, OAuth2PasswordBearer)
- **Решение конфликта:** Перед передачей в FastMCP.from_openapi() удаляются HTTPBearer и OAuth2PasswordBearer схемы, остается только APIKeyHeader
- **Код исправления (r2r_openapi_server.py:57-70):**
  ```python
  # Удаляем конфликтующие security schemes
  if "components" in openapi_spec and "securitySchemes" in openapi_spec["components"]:
      security_schemes = openapi_spec["components"]["securitySchemes"]
      openapi_spec["components"]["securitySchemes"] = {
          "APIKeyHeader": security_schemes.get("APIKeyHeader", {})
      }

  # Обновляем security requirements
  if "security" in openapi_spec:
      openapi_spec["security"] = [{"APIKeyHeader": []}]
  ```
- **Ошибка без исправления:** `HTTP 400: Cannot have both Bearer token and API key` при вызове MCP инструментов
- **Проверка:** Тесты в `test_mcp_call.py` подтверждают, что конфликт устранен

## 🛠️ Команды разработки

### Makefile команды (предпочтительный способ)

```bash
# Установка и управление зависимостями
make install      # Установка всех зависимостей (production + dev) через uv
make sync         # Синхронизация зависимостей из pyproject.toml
make dev          # Установка только dev зависимостей

# Проверка качества кода
make lint         # Полная проверка (format + typecheck)
make fix          # Автоисправление ruff проблем
make format       # Форматирование кода ruff
make typecheck    # Проверка типов mypy

# Запуск серверов
make run          # Запуск custom MCP server (server.py)
make run-openapi  # Запуск OpenAPI MCP server в stdio режиме
make run-http     # Запуск OpenAPI MCP server в HTTP режиме (порт 8000)
make run-gemini   # Запуск Gemini интеграции (интерактивный режим)
make run-inspector # Запуск MCP Inspector (GUI для тестирования инструментов)

# Утилиты
make clean        # Очистка кэша и виртуального окружения
make help         # Справка по командам
```

**Важно:** Проект использует `uv` для управления зависимостями и виртуальным окружением. Все команды запускаются через `uv run`.

### Запуск сервера

**Локальная разработка:**
```bash
# Через Makefile (streamable HTTP на порту 8000)
make run

# Прямой запуск (streamable HTTP на порту 8000)
# Доступен по адресу http://localhost:8000/mcp
python server.py
```

**Production деплой (ChatMCP, Uvicorn):**

Сервер экспортирует ASGI приложение через `app = mcp.http_app(transport="streamable-http", path="/mcp")` (server.py:154).
**Важно:**
- Используется Streamable HTTP transport - рекомендуемый для production деплоев
- `path="/mcp"` — явно указан endpoint путь, ожидаемый MCP клиентами
- `http_app()` вместо `streamable_http_app()` для совместимости с разными версиями FastMCP

```bash
# Через uvicorn напрямую
uvicorn server:app --host 0.0.0.0 --port 8000

# Production с несколькими workers
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

**Claude Desktop интеграция (stdio):**

Для Claude Desktop используй `mcp install` (не для веб-деплоя):
```bash
mcp install server.py -v R2R_BASE_URL=http://localhost:7272
```

**OpenAPI сервер (автогенерация из R2R API):**

Для доступа ко всем 114 маршрутам R2R API используй `r2r_openapi_server.py`:

```bash
# Локальная разработка (stdio)
python r2r_openapi_server.py

# Production деплой (HTTP)
uvicorn r2r_openapi_server:app --host 0.0.0.0 --port 8000

# Claude Desktop установка
mcp install r2r_openapi_server.py -v R2R_BASE_URL=http://localhost:7272
```

**Важно:**
- OpenAPI сервер использует экспериментальный парсер (`FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER=true`)
- Загружает OpenAPI спецификацию синхронно для совместимости с uvicorn
- Поддерживает все операции R2R API через автогенерацию инструментов
- r2r_openapi_server.py:4 — включение нового парсера через `os.environ` ДО импортов
- r2r_openapi_server.py:18-40 — синхронная загрузка OpenAPI spec и создание сервера

### Gemini интеграция

**Описание:**
`r2r_openapi_server.py` поддерживает прямую интеграцию с Google Gemini SDK через FastMCP Client. Gemini использует упрощённый `server.py` с 2 базовыми инструментами (search, rag), которые поддерживают все параметры включая пресеты.

**Архитектура:**
- Gemini SDK напрямую взаимодействует с MCP Client session (r2r_openapi_server.py:54-89)
- FastMCP Client подключается к `server.py` (2 инструмента: search, rag)
- **Почему server.py, а не r2r_openapi_server.py?** OpenAPI сервер имеет 114 инструмента с сложными схемами, которые Gemini API не может обработать. Упрощённый server.py предоставляет 2 мощных инструмента с пресетами
- Gemini автоматически вызывает MCP tools при необходимости
- Поддержка всех Gemini моделей (gemini-2.0-flash, gemini-1.5-pro и т.д.)

**Запуск через CLI:**

```bash
# Базовый запрос
python r2r_openapi_server.py --gemini "Search for information about neural networks"

# Пример вывода:
# Gemini Response:
# Based on the R2R knowledge base search, neural networks are...
```

**Программное использование:**

```python
import asyncio
from r2r_openapi_server import run_with_gemini

# Базовый запрос с дефолтной моделью (gemini-2.0-flash)
result = asyncio.run(run_with_gemini(
    "Search for information about quantum computing"
))

# С кастомной моделью
result = asyncio.run(run_with_gemini(
    "Analyze machine learning trends",
    model="gemini-1.5-pro"
))
```

**Конфигурация:**

1. Получи Gemini API ключ: https://aistudio.google.com/apikey
2. Добавь в `.env` файл:
   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
3. Убедись, что `R2R_BASE_URL` и `API_KEY` также настроены

**Особенности:**

- **Автоматический вызов tools:** Gemini самостоятельно решает, когда использовать R2R инструменты
- **2 мощных инструмента:** search и rag с поддержкой всех параметров и пресетов (default, development, refactoring, debug, research, production)
- **Температура настраивается:** Дефолт 0.7, можно изменить в `run_with_gemini()`
- **Async-native:** Вся интеграция построена на asyncio для производительности

**Workflow:**

1. Gemini получает запрос пользователя
2. Анализирует, нужны ли данные из R2R
3. Автоматически вызывает нужные MCP tools (search, rag и т.д.)
4. Получает результаты и формирует финальный ответ
5. Возвращает сгенерированный текст пользователю

**Важно:**
- Требуется google-genai>=0.2.0 (добавлена в pyproject.toml)
- MCP Client подключается к `server.py` (не к `r2r_openapi_server.py`!), чтобы избежать сложных схем из 114 инструментов OpenAPI
- Доступны 2 инструмента: `search` и `rag` с полной поддержкой параметров и пресетов
- Gemini SDK требует `GEMINI_API_KEY` в переменных окружения
- r2r_openapi_server.py:73-75 — создание MCP Client для server.py
- r2r_openapi_server.py:54-89 — реализация `run_with_gemini()`
- r2r_openapi_server.py:92-105 — CLI интерфейс для Gemini режима

### MCP Inspector (GUI для тестирования)

**Описание:**
MCP Inspector - официальный инструмент от Anthropic для визуального тестирования MCP серверов. Предоставляет веб-интерфейс для вызова инструментов, просмотра ресурсов и отладки.

**Установка:**

MCP Inspector работает через npx без установки:
```bash
npx @modelcontextprotocol/inspector
```

Или установи глобально:
```bash
npm install -g @modelcontextprotocol/inspector
```

**Запуск:**

```bash
# Через Makefile (рекомендуется)
make run-inspector

# Или напрямую
npx @modelcontextprotocol/inspector uv run python r2r_openapi_server.py
```

**Что происходит:**

1. Запускается веб-сервер на `http://localhost:5173`
2. Автоматически открывается браузер с GUI интерфейсом
3. MCP сервер запускается в фоне и подключается к Inspector

**Возможности Inspector:**

- **Tools tab:** Просмотр всех 114 инструментов с документацией
- **Test tools:** Вызов любого инструмента с параметрами через GUI
- **Resources tab:** Просмотр доступных ресурсов (r2r://config, r2r://health)
- **Logs:** Реалтайм логи всех операций MCP сервера
- **JSON inspector:** Просмотр сырых JSON ответов от инструментов

**Workflow тестирования:**

1. Запусти `make run-inspector`
2. Открой браузер на `http://localhost:5173`
3. Выбери инструмент в списке (например, `retrieval_search`)
4. Заполни параметры в форме (query, settings и т.д.)
5. Нажми "Call Tool"
6. Просмотри результат в JSON или форматированном виде
7. Проверь логи на наличие ошибок

**Пример тестирования search:**

1. Tools → `retrieval_search`
2. Параметры:
   ```json
   {
     "query": "neural networks",
     "search_settings": {
       "use_vector_search": true,
       "filters": {},
       "limit": 10
     }
   }
   ```
3. Call Tool
4. Результат покажет vector search results из R2R

**Важно:**
- Требует Node.js и npm/npx в системе
- MCP Inspector работает только с stdio транспортом
- Для тестирования HTTP сервера используй Postman или curl
- Inspector автоматически обнаруживает все инструменты из OpenAPI spec
- Логи в реальном времени помогают отладить ошибки

### Настройка окружения

Создай `.env` файл с переменными:
```bash
# R2R конфигурация
R2R_BASE_URL=http://your-r2r-instance:7272
API_KEY=your_r2r_api_key

# Gemini конфигурация (для Gemini интеграции)
# Получи API ключ на https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# FastMCP настройки (для r2r_openapi_server.py)
FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER=true

# Python настройки
PYTHONWARNINGS=ignore::DeprecationWarning
```

**Важно:**
- Не используй кавычки в .env файле для PYTHONWARNINGS - это вызовет ошибку "Invalid -W option"
- `FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER` включает новый парсер для OpenAPI сервера (рекомендуется, станет дефолтным в будущих версиях FastMCP)

**ВАЖНО:** `.env` содержит чувствительные данные и исключен из git

### Установка зависимостей

```bash
# Через Makefile (рекомендуется) - создаст .venv и установит все зависимости
make install

# Или напрямую через uv
uv sync --all-extras

# Только production зависимости
uv sync

# Только dev зависимости
uv sync --extra dev
```

**Структура зависимостей (pyproject.toml):**
- **Production:** fastmcp==2.13.1 (закреплена версия для production), r2r>=3.6.0, google-genai>=0.2.0
- **Dev:** ruff>=0.8.0, mypy>=1.14.0

**ВАЖНО:** FastMCP использует закреплённую версию (==2.13.1) по рекомендациям из документации FastMCP, т.к. breaking changes могут происходить в minor версиях. uv.lock включён в git для воспроизводимости зависимостей в production окружении.

Виртуальное окружение создаётся в `.venv/` и управляется автоматически через `uv`.

### Проверка качества кода

```bash
# Полная проверка (форматирование + типы)
make lint

# Только форматирование
make format

# Только типы
make typecheck

# Автоматическое исправление проблем
make fix
```

### Тестирование инструментов

После установки в Claude Desktop, проверь доступность:
1. Открой Claude Desktop
2. Проверь Tools → должны появиться 5 инструментов и 2 ресурса
3. Тестовые запросы:
   - "Search for information about X"
   - "Use advanced search with hybrid mode for Y"
   - "Search knowledge graph for connections between A and B"

## 📚 Документация инструментов

### Базовые инструменты

#### `search(query: str) -> str`
**Описание:** Базовый семантический поиск по R2R knowledge base
**Annotations:** readOnlyHint=True, idempotentHint=True, openWorldHint=True
**Progress tracking:** 10% → 30% → 80% → 100%

```python
# Пример использования
result = await search("What is deep learning?")
```

**Возвращает:** Форматированные результаты включая vector, graph, web и document results

#### `rag(query: str) -> str`
**Описание:** Полноценный RAG-запрос с генерацией ответа
**Annotations:** readOnlyHint=False, destructiveHint=False, openWorldHint=True
**Progress tracking:** 20% → 40% → 90% → 100%

```python
# Пример использования
answer = await rag("Explain the concept of neural networks")
```

**Возвращает:** Сгенерированный ответ на основе релевантного контекста

### Расширенные инструменты

#### `advanced_search(query, use_hybrid_search=False, semantic_weight=5.0, full_text_weight=1.0, limit=10) -> str`
**Описание:** Поиск с hybrid search и настраиваемыми параметрами
**Annotations:** readOnlyHint=True, openWorldHint=True

**Параметры:**
- `use_hybrid_search` (bool): Включить hybrid search (semantic + full-text)
- `semantic_weight` (float): Вес для semantic search (default: 5.0)
- `full_text_weight` (float): Вес для full-text search (default: 1.0)
- `limit` (int): Максимальное количество результатов (default: 10)

```python
# Пример с hybrid search
result = await advanced_search(
    query="quantum computing applications",
    use_hybrid_search=True,
    semantic_weight=7.0,
    full_text_weight=3.0,
    limit=15
)
```

**Конфигурация hybrid_settings:**
- `full_text_limit`: 200 (количество full-text результатов для обработки)
- `rrf_k`: 50 (параметр Reciprocal Rank Fusion)

#### `graph_search(query, enable_graph=True, kg_search_type="local", use_hybrid_search=False, semantic_weight=5.0, full_text_weight=1.0, limit=20) -> str`
**Описание:** Поиск с интеграцией knowledge graph и опциональным hybrid search
**Annotations:** readOnlyHint=True, openWorldHint=True

**Параметры:**
- `enable_graph` (bool): Включить knowledge graph integration
- `kg_search_type` (str): Тип graph search ("local" или "global")
- `use_hybrid_search` (bool): Включить hybrid search (semantic + full-text)
- `semantic_weight` (float): Вес для semantic search (default: 5.0)
- `full_text_weight` (float): Вес для full-text search (default: 1.0)
- `limit` (int): Максимальное количество результатов (default: 20)

```python
# Пример с knowledge graph и hybrid search
result = await graph_search(
    query="relationships between machine learning concepts",
    enable_graph=True,
    kg_search_type="local",
    use_hybrid_search=True,
    semantic_weight=7.0,
    limit=25
)
```

**Особенности:**
- Комбинирует knowledge graph с hybrid search для максимальной точности
- Возвращает entities, relationships и communities из knowledge graph
- Поддерживает все параметры hybrid search из `advanced_search`

#### `advanced_rag(query, model="openai/gpt-4o-mini", temperature=0.7, use_hybrid_search=False, include_web_search=False) -> str`
**Описание:** RAG с настраиваемой генерацией
**Annotations:** readOnlyHint=False, destructiveHint=False, openWorldHint=True

**Параметры:**
- `model` (str): LLM модель для генерации (default: "openai/gpt-4o-mini")
- `temperature` (float): Температура генерации 0.0-1.0 (default: 0.7)
- `use_hybrid_search` (bool): Включить hybrid search для retrieval
- `include_web_search` (bool): Включить web search results

```python
# Пример с Claude и веб-поиском
answer = await advanced_rag(
    query="Latest developments in AI safety",
    model="anthropic/claude-3-haiku-20240307",
    temperature=0.5,
    use_hybrid_search=True,
    include_web_search=True
)
```

**Доступные модели:**
- OpenAI: `openai/gpt-4o-mini`, `openai/gpt-4o`, `openai/gpt-4-turbo`
- Anthropic: `anthropic/claude-3-haiku-20240307`, `anthropic/claude-3-sonnet-20240229`
- И другие LLM провайдеры, поддерживаемые R2R

### Ресурсы

#### `r2r://config`
**Описание:** Текущая конфигурация сервера

**Возвращает:**
```json
{
  "r2r_base_url": "http://localhost:7272",
  "api_key_configured": true,
  "request_id": "req-123...",
  "server_name": "R2R Retrieval System"
}
```

#### `r2r://health`
**Описание:** Проверка здоровья R2R сервера

**Возвращает (healthy):**
```json
{
  "status": "healthy",
  "r2r_url": "http://localhost:7272",
  "timestamp": "req-123...",
  "api_key_configured": true
}
```

**Возвращает (unhealthy):**
```json
{
  "status": "unhealthy",
  "error": "connection refused",
  "r2r_url": "http://localhost:7272"
}
```

## 🔧 Интеграция с R2R

### R2RClient настройки

- Клиент инициализируется для каждого запроса
- Использует переменные окружения из `.env`
- Базовый URL: `R2R_BASE_URL` (по умолчанию http://localhost:7272)
- API Key аутентификация: `client.set_api_key(API_KEY)` если API_KEY установлен

### Context Integration

Все инструменты используют FastMCP Context для:
- **Логирования:** `await ctx.info()`, `await ctx.error()`, `await ctx.debug()`
- **Progress reporting:** `await ctx.report_progress(progress, total, message)`
- **Request tracking:** `ctx.request_id` для отслеживания запросов

**Пример из search():**
```python
await ctx.info(f"Starting search query: {query}")
await ctx.report_progress(progress=30, total=100, message="Executing search")
await ctx.info(f"Search completed successfully, returned {len(formatted)} chars")
```

### Типы поисковых результатов

**Vector Search (chunk_search_results):**
- Возвращает фрагменты текста с ID и содержимым
- Формат: `Source ID [краткий_id]: текст`

**Graph Search (graph_search_results):**
- Три типа объектов:
  - Communities (id, name, summary)
  - Entities (name, description)
  - Relationships (subject-predicate-object)

**Web Search (web_search_results):**
- Структура: title, link, snippet
- Форматируется как веб-источники

**Document Search (document_search_results):**
- Документы с метаданными (title, summary)
- Вложенные chunks с ID и текстом
- Полезно для локального контекста

## ⚠️ Важные нюансы

### Подавление DeprecationWarning

server.py:5-7 явно отключает предупреждения перед импортом:
```python
os.environ["PYTHONWARNINGS"] = "ignore::DeprecationWarning"
warnings.filterwarnings("ignore", category=DeprecationWarning)
```

**Причина:** R2R SDK или зависимости генерируют deprecation warnings, которые засоряют логи MCP

### Обработка ошибок

**R2RErrorHandlingMiddleware:**
- Централизованная обработка всех ошибок на уровне middleware
- Логирование ошибок с полным контекстом (метод, тип ошибки, детали)
- Отслеживание статистики ошибок по типам
- Специальная обработка R2R connection errors:
  ```python
  ConnectionError(
      f"Failed to connect to R2R server at {R2R_BASE_URL}. "
      "Please check R2R_BASE_URL and ensure R2R is running."
  )
  ```

**Tool-level error handling:**
- Все tools используют `try/except` с Context логированием
- Ошибки перебрасываются после логирования для обработки клиентом
- Пример:
  ```python
  except Exception as e:
      await ctx.error(f"Search failed: {e!s}")
      raise
  ```

### Типизация и async

- Все инструменты MCP объявлены как `async` (server.py:114, 135)
- R2RClient методы синхронные, но вызываются внутри async функций
- FastMCP обрабатывает это автоматически

## 🔍 Отладка

### Проверка подключения к R2R

```python
from r2r import R2RClient
client = R2RClient()
result = client.retrieval.search(query="test")
print(result)
```

### Логирование MCP

FastMCP автоматически логирует вызовы инструментов в stderr Claude Desktop

### Типичные проблемы

1. **`'FastMCP' object has no attribute 'http_app'` или `got an unexpected keyword argument 'path'`**
   - **Причина:** Несовместимость версий FastMCP между локальной разработкой и production окружением
   - **Решение:** Используй универсальный метод `app = mcp.http_app(transport="streamable-http", path="/mcp")`
   - **Проверка:** Убедись, что версия fastmcp==2.13.1 в pyproject.toml

2. **`POST /mcp 400 Bad Request`** при деплое на ChatMCP/Uvicorn
   - **Причина:** Неправильный путь endpoint'а или сервер не экспортирует ASGI приложение
   - **Решение:** Убедись, что в server.py есть `app = mcp.http_app(transport="streamable-http", path="/mcp")` на уровне модуля
   - **Проверка:** В логах должен быть `INFO: Application startup complete` и запросы к `/mcp` должны возвращать 200

3. **`RuntimeError: Type not yet supported: str | None`** при `mcp install`
   - **Причина:** Старая версия typer (0.9.0) несовместима с текущим MCP CLI
   - **Решение:** `pip install --upgrade 'mcp[cli]'` (обновит typer до 0.20.0+)

4. **"R2R connection refused"** → проверь `R2R_BASE_URL` в `.env` или переменной окружения

5. **"MCP tool not appearing"** в Claude Desktop → перезапусти Claude Desktop (Cmd+Q, затем открой)

6. **Empty search results** → проверь, что R2R база проиндексирована и доступна

7. **Invalid -W option ignored: invalid action: '"ignore'**
   - **Причина:** Лишние кавычки в `.env` файле вокруг PYTHONWARNINGS
   - **Решение:** Используй `PYTHONWARNINGS=ignore::DeprecationWarning` без кавычек

8. **"Using legacy OpenAPI parser"** при запуске r2r_openapi_server.py
   - **Причина:** Переменная окружения `FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER` устанавливается после импорта FastMCP
   - **Решение:**
     - Убедись, что r2r_openapi_server.py:4 устанавливает переменную ДО всех импортов
     - Строка `os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"` должна быть между `import os` и `from fastmcp import FastMCP`
     - Новый парсер рекомендуется и станет дефолтным в будущих версиях FastMCP

9. **`RuntimeError: asyncio.run() cannot be called from a running event loop`** при запуске через uvicorn
   - **Причина:** uvicorn создаёт свой event loop, а код пытается вызвать `asyncio.run()` на уровне модуля
   - **Решение:**
     - Используй синхронную инициализацию: `httpx.Client()` вместо `httpx.AsyncClient()` для загрузки OpenAPI spec
     - Создавай server instance через обычную функцию, а не через `asyncio.run(async_function())`
     - r2r_openapi_server.py:18-40 показывает правильный подход с синхронной загрузкой

10. **`HTTP 400: Cannot have both Bearer token and API key`** при вызове MCP инструментов
   - **Причина:** OpenAPI spec от R2R содержит 3 security schemes (HTTPBearer, APIKeyHeader, OAuth2PasswordBearer). FastMCP может автоматически добавлять headers для всех схем, вызывая конфликт
   - **Решение:**
     - Модифицировать OpenAPI spec перед передачей в `FastMCP.from_openapi()`
     - Удалить HTTPBearer и OAuth2PasswordBearer схемы, оставив только APIKeyHeader
     - Обновить security requirements на глобальном уровне: `openapi_spec["security"] = [{"APIKeyHeader": []}]`
     - **КРИТИЧНО:** Обновить security requirements на уровне каждой операции (endpoint), т.к. FastMCP использует operation-level security
     - См. r2r_openapi_server.py:57-82 для полного кода исправления
   - **Проверка:** После деплоя проверь, что вызовы MCP инструментов не возвращают 400 с этой ошибкой
   - **Важно:** R2R SDK использует `x-api-key` header для API ключей (не `Authorization: Bearer`)

11. **`litellm.BadRequestError: VertexAIException - Unable to submit request because at least one contents field is required`**
   - **Причина:** R2R сервер настроен использовать VertexAI/Gemini для поиска, но что-то не так с конфигурацией LiteLLM или VertexAI credentials
   - **Симптомы:**
     - HTTP 500 Internal Server Error при вызове search/rag инструментов
     - Ошибка происходит на стороне R2R сервера, не MCP сервера
     - Особенно проявляется при использовании пресетов (research, development и т.д.)
   - **Решение:**
     - Проверь конфигурацию R2R сервера: `r2r.toml` или переменные окружения
     - Убедись, что VertexAI credentials настроены корректно (GOOGLE_APPLICATION_CREDENTIALS)
     - Проверь, что LiteLLM router в R2R правильно сконфигурирован для VertexAI
     - Альтернатива: переключи R2R на использование OpenAI или другого провайдера
     - Логи R2R сервера покажут детали ошибки конфигурации
   - **Важно:** Это проблема конфигурации R2R, а не MCP сервера. MCP сервер корректно делает запросы к R2R API

## 📝 Workflow разработки

### Добавление нового инструмента

1. Добавь функцию с декоратором `@mcp.tool()`
2. Укажи docstring с описанием (используется в UI Claude)
3. Добавь типы аргументов и возвращаемого значения
4. Перезапусти MCP сервер

### Модификация форматирования результатов

При изменении `format_search_results_for_llm()`:
- Сохраняй структуру "Source ID [shorthand]:"
- Используй `id_to_shorthand()` для консистентности
- Тестируй на всех 4 типах результатов

## ⛔️ Запрещенные практики

- **НЕ коммить .env файл** — содержит API ключи
- **НЕ хардкодить R2R_BASE_URL** — всегда через переменные окружения
- **НЕ использовать синхронный код** в инструментах MCP — только async
- **НЕ удалять suppression warnings** без понимания последствий

Always use context7 when I need code generation, setup or
configuration steps, or library/API documentation. This means
you should automatically use the Context7 MCP tools to resolve
library id and get library docs without me having to
explicitly ask.
