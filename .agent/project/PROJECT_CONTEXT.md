# PROJECT_CONTEXT

Project-specific source of truth for Shorts Factory Backend.

## 1. Stack

- Project name: `Shorts Factory Backend`
- Primary languages: Python, SQL, Shell
- Runtime / platform: Backend service on Python 3.12+
- Main frameworks / libraries: FastAPI, Pydantic, SQLAlchemy, Alembic, OpenAI SDK, FFmpeg, Telegram Bot API client, YouTube Data API client, scheduler/worker stack to be selected during implementation
- Data stores: PostgreSQL preferred for production; local filesystem/object storage for rendered media assets
- Default user-facing language: German for generated videos and metadata; Ukrainian for internal project documentation unless a file already uses another language

## 2. Project structure

- Root entrypoints: Not created yet
- Source directories: planned `shorts_factory/`
- Test directories: planned `tests/`
- Config / infra directories: planned root config files; `.agent/` contains agent rules and project context
- Read-only or protected paths: `.agent/core/` is treated as universal rules; secrets and credentials files are never read or modified

## 3. Key commands

| Purpose | Command | Notes |
|---|---|---|
| Test | Not configured yet | Define after project scaffolding |
| Lint | Not configured yet | Define after Python tooling is selected |
| Build | Not configured yet | Define after packaging/deployment approach is selected |
| Dev / Run | Not configured yet | Define after FastAPI app entrypoint exists |

## 4. External dependencies

| System / service | Purpose | Access mode | Notes |
|---|---|---|---|
| Quiz Bank API | Source of approved/published quiz content | HTTP API | Single source of truth for question, answers, explanation, topic, and level |
| OpenAI API | Script formatting, image prompts, image generation, voice generation, publishing metadata | HTTPS API with env/secret key | LLM output is untrusted until schema-validated |
| FFmpeg / FFprobe | Video rendering and media QA | Local binary | Required for MP4 assembly, audio/video probing, overlays, and Ken Burns effect |
| Telegram Bot API | Telegram channel publishing | HTTPS API with bot token in secrets | Initial MVP publishing target |
| YouTube Data API | YouTube Shorts publishing | OAuth credentials in secrets | Planned after Telegram MVP |
| Local filesystem / object storage | Store generated images, audio, videos, subtitles, and logs | Controlled service paths | Must avoid untrusted paths and public secret exposure |

## 5. Project constraints

- Protected paths: `.agent/core/`, secrets files, generated production media storage outside approved asset directories
- Secrets / credentials locations: environment variables or secret manager only; never store OpenAI keys, Telegram tokens, YouTube OAuth credentials, `.env*`, `*.pem`, `*.key`, or credential files in readable logs or database plaintext
- Deploy / production boundaries: no production deploy, credential rotation, real channel publishing, or production data mutation without explicit user request and confirmation
- Approval-required operations: dependency changes, schema changes/migrations, real Telegram/YouTube publishing, production-like external calls, destructive file/database operations
- Restricted hosts / environments: production Telegram channels, YouTube channels, Quiz Bank production API, production storage
- Project-specific forbidden actions: changing quiz facts with AI, asking image generation to draw text, publishing before QA, publishing duplicate retries, using unapproved/unpublished quizzes, storing secrets in plaintext, using n8n as product orchestration

## 6. Git settings

- Default / protected branch: `main`
- Branching strategy: feature branches from `main`, named `type/short-description`
- Merge strategy: squash merge
- PR title format: Conventional Commits, for example `feat: add video job worker`
- PR requirements: focused scope, passing relevant checks, no secrets, no direct push to protected branch, review before merge when repository hosting is configured
