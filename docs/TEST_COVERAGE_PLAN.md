# Test Coverage Plan

## Поточний стан

- Baseline command: `uv run pytest`
- Coverage source: `shorts_factory`
- Branch coverage: enabled
- Current gate: `85%`
- Current result: `96 passed`, total coverage `85.65%`
- XML artifact: `coverage.xml`, ignored by git

## Цільові пороги

1. Stage 1: підняти gate до `80%` - done.
2. Stage 2: підняти gate до `85%` - done.
3. Stage 3: підняти gate до `90%`.

Поріг піднімати тільки після додавання тестів, які стабільно проходять локально.

## Пріоритет 1: критичні production boundaries - done

- `shorts_factory/generation/script_generator.py`
  - fake OpenAI client returns parsed `GeneratedScript`;
  - `output_parsed is None`;
  - generated answer frame lacks correct label and text.
- `shorts_factory/generation/image_generator.py`
  - missing `OPENAI_API_KEY`;
  - fake image response writes decoded PNG bytes through `LocalStorage`;
  - image response without `b64_json`.
- `shorts_factory/generation/voice_generator.py`
  - missing `OPENAI_API_KEY`;
  - fake streaming response writes audio file to expected path.

## Пріоритет 2: publishing safety - done

- `shorts_factory/publishing/publish_service.py`
  - duplicate Telegram publish is rejected;
  - duplicate YouTube publish is rejected;
  - missing video path is rejected;
  - missing script metadata is rejected.
- `shorts_factory/publishing/telegram_publisher.py`
  - missing token;
  - missing chat id;
  - missing video file;
  - Telegram payload with `ok=false`;
  - private chat without username returns `url=None`.
- `shorts_factory/publishing/youtube_publisher.py`
  - HTTP status failure;
  - transport failure;
  - response without video id;
  - non-MP4 file;
  - empty title;
  - fallback privacy status.

## Пріоритет 3: API and worker failures

- `shorts_factory/api/jobs.py`
  - API key not configured;
  - database not configured;
  - list jobs;
  - get job not found;
  - assets endpoint;
  - retry endpoint;
  - Telegram publish 404 and 409 paths.
- `shorts_factory/jobs/worker.py`
  - script generation failure reports delivery failure;
  - renderer failure records render log and marks job failed;
  - QA failure records render log and marks job failed;
  - YouTube failure keeps Telegram path and reports delivery outcome as failed;
  - delivery outcome reporting failure writes `delivery_outcome` render log.

## Пріоритет 4: rendering and storage - partially done

- `shorts_factory/rendering/ffmpeg_renderer.py`
  - `FFmpegRenderer.render` success with monkeypatched `subprocess.run` - done;
  - non-zero FFmpeg result raises `RenderError` - done.
- `shorts_factory/rendering/qa_probe.py`
  - `FFprobeVideoProbe.probe` success and failure with monkeypatched `subprocess.run` - done;
  - missing video stream - done;
  - missing duration - done;
  - non-MP4 file - done;
  - missing overlays - done;
  - mismatched answer label/text - done;
  - missing Telegram caption - done;
  - missing YouTube title - done;
  - wrong dimensions, too long duration, missing audio - done.
- `shorts_factory/storage/local_storage.py`
  - `write_bytes` creates parent directory - done through image adapter tests;
  - checksum matches written content - done through image adapter tests.

## Пріоритет 5: schema, repository, migrations

- `shorts_factory/quiz_bank/adapter.py`
  - duplicate option ids;
  - too many options;
  - correct answer id not found;
  - empty feedback and option fields.
- `shorts_factory/db/session.py`
  - `session_scope` commits on success;
  - `session_scope` rolls back and closes on exception.
- `alembic/`
  - upgrade a temporary SQLite database to head;
  - verify expected tables and `publish_logs.metadata_json`.
