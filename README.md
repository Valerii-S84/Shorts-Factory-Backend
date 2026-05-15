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
Production secrets are configured on the deployment server or in its secret manager, not in
repository files and not in local development documentation.

Current server deployment:

- SSH: `ssh valerchik.de` (root user is configured in local SSH config)
- App checkout on server: `/opt/shorts-factory-backend/app`
- Runtime env file: `/opt/shorts-factory-backend/secrets/runtime.env`
- Docker container: `shorts-factory-backend`
- Local server port mapping: `127.0.0.1:8020 -> 8000`
- Data volume on server: `/opt/shorts-factory-backend/data -> /data`
- Runtime health checks on server: `curl -fsS http://127.0.0.1:8020/health`
  and `curl -fsS http://127.0.0.1:8020/ready`

Do not copy secret values from the server env file into the repository, terminal
output, docs, commits, or logs. When verifying configuration, print only env
variable names or health-check results.

Useful local variables:

- `SHORTS_FACTORY_ENV`
- `SHORTS_FACTORY_LOG_LEVEL`
- `SHORTS_FACTORY_MEDIA_ROOT`
- `DATABASE_URL`
- `SHORTS_FACTORY_API_KEY`
- `QUIZ_BANK_BASE_URL`
- `QUIZ_BANK_EDGE_API_KEY`
- `QUIZ_BANK_CONSUMER_ID`
- `QUIZ_BANK_API_KEY`
- `QUIZ_BANK_QUOTA_KEY`
- `QUIZ_BANK_NEXT_PATH`
- `QUIZ_BANK_DEFAULT_LEVELS`
- `QUIZ_BANK_DEFAULT_THEMES`
- `QUIZ_BANK_DEFAULT_LANGUAGE`
- `FFMPEG_PATH`
- `FFPROBE_PATH`

For the real Quiz Bank runtime, set `QUIZ_BANK_BASE_URL` to `https://api.valerchik.de`.
Leave `QUIZ_BANK_DEFAULT_LEVELS` and `QUIZ_BANK_DEFAULT_THEMES` empty to use the
allowed default item from the Quiz Bank entitlement. `QUIZ_BANK_DEFAULT_LANGUAGE`
defaults to `de`.

By default the service uses `ffmpeg` and `ffprobe` from `PATH`. On the current
local environment they resolve to `/usr/bin/ffmpeg` and `/usr/bin/ffprobe`.

`DATABASE_URL`, `SHORTS_FACTORY_API_KEY`, `QUIZ_BANK_BASE_URL`,
`QUIZ_BANK_EDGE_API_KEY`, `QUIZ_BANK_API_KEY`, `OPENAI_API_KEY`,
`TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` are required for production settings.
