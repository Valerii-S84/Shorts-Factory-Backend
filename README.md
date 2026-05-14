# Shorts Factory Backend

Production backend for turning approved Quiz Bank entries into German vertical quiz shorts.

Canonical product documents:

- `docs/PRODUCT_VISION.md`
- `docs/ROADMAP.md`

## Local Setup

```bash
uv sync --all-extras
```

## Development

```bash
uv run uvicorn shorts_factory.main:create_app --factory --reload
```

## Checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

## Database

Local, test, and development environments use SQLite at
`sqlite+pysqlite:///var/shorts_factory.db` when `DATABASE_URL` is not set.

Production uses Alembic migrations:

```bash
uv run alembic upgrade head
```

## Stage 1 API

Job endpoints require `X-API-Key` with the value from `SHORTS_FACTORY_API_KEY`.

```bash
curl -H "X-API-Key: $SHORTS_FACTORY_API_KEY" \
  -X POST http://127.0.0.1:8000/jobs/create \
  -H "Content-Type: application/json" \
  -d '{"target_platforms":["telegram"]}'
```

## Configuration

Configuration is read from environment variables. Secrets must not be committed or logged.

Useful local variables:

- `SHORTS_FACTORY_ENV`
- `SHORTS_FACTORY_LOG_LEVEL`
- `SHORTS_FACTORY_MEDIA_ROOT`
- `DATABASE_URL`
- `SHORTS_FACTORY_API_KEY`

`DATABASE_URL`, `SHORTS_FACTORY_API_KEY`, `QUIZ_BANK_BASE_URL`, `OPENAI_API_KEY`,
`TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` are required for production settings.
