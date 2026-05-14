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
```

## Configuration

Configuration is read from environment variables. Secrets must not be committed or logged.

Useful local variables:

- `SHORTS_FACTORY_ENV`
- `SHORTS_FACTORY_LOG_LEVEL`
- `SHORTS_FACTORY_MEDIA_ROOT`
- `DATABASE_URL`
- `SHORTS_FACTORY_API_KEY`

Local, test, and development environments use `sqlite+pysqlite:///var/shorts_factory.db`
when `DATABASE_URL` is not set. `DATABASE_URL` and `SHORTS_FACTORY_API_KEY` are
required for production settings.
