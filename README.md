# R2R FastMCP Server

MCP-сервер для интеграции R2R (Retrieval-Augmented Generation) с Claude Desktop.

**Доступные реализации:**
- `server.py` — Кастомный MCP сервер с 5 специализированными инструментами (search, rag, advanced_search, graph_search, advanced_rag)
- `r2r_openapi_server.py` — Автогенерация из OpenAPI спецификации R2R (полный доступ ко всем R2R API эндпоинтам)

## Быстрый старт

```bash
# Установка зависимостей через uv
make install

# Настройка окружения
cp .env.example .env
# Отредактируй .env с твоими настройками

# Проверка кода
make lint

# Запуск сервера
make run
```

> **Примечание:** Проект использует `uv` для управления зависимостями. Убедись, что uv установлен: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Установка в Claude Desktop

**Кастомный сервер (5 инструментов):**
```bash
# Если возникает ошибка с typer, сначала обнови зависимости:
# pip install --upgrade 'mcp[cli]'

mcp install server.py -v R2R_BASE_URL=http://localhost:7272
```

**OpenAPI сервер (полный R2R API):**
```bash
# Локальная разработка (stdio)
python r2r_openapi_server.py

# Production деплой (HTTP)
uvicorn r2r_openapi_server:app --host 0.0.0.0 --port 8000

# Claude Desktop установка
mcp install r2r_openapi_server.py -v R2R_BASE_URL=http://localhost:7272
```

## Доступные инструменты

- `search` — поиск по базе знаний R2R (vector, graph, web, document)
- `rag` — RAG-запрос с генерацией ответа

## Команды разработки

```bash
make help       # Список всех команд
make install    # Установка зависимостей
make lint       # Проверка кода (format + typecheck)
make fix        # Автоматическое исправление
make run        # Запуск сервера
make clean      # Очистка кэша
```

## Требования

- Python 3.12+
- uv 0.6+ ([инструкция по установке](https://docs.astral.sh/uv/getting-started/installation/))
- R2R instance (запущенный сервер)

## Документация

Полная документация находится в [CLAUDE.md](./CLAUDE.md)
