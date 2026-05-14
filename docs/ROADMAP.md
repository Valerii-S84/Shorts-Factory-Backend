# ROADMAP

## 1. Головне правило

Shorts Factory Backend будується як повноцінний production-продукт, а не як тимчасова демо-версія.

Кожен етап має залишати після себе код, дані, логи, тести й операційні правила, які можна розвивати далі без переписування основи.

Якість цільового результату: продукт має бути достатньо стабільним, зрозумілим і презентабельним для сильної технічної презентації, включно з рівнем демонстрації для Stanford-style аудиторії.

## 2. Стратегія релізів

Продукт будується у два великі етапи:

1. Telegram production stage.
2. YouTube expansion stage.

Telegram етап не є чернеткою. Це перший повноцінний production-slice продукту:

```text
one command or scheduled job
-> one approved Quiz Bank quiz
-> validated German script
-> generated images without text
-> generated German voice-over
-> FFmpeg render with Ken Burns and exact backend text overlays
-> QA gate
-> Telegram publish
-> logs, assets, statuses, links
```

YouTube додається тільки після того, як Telegram flow стабільний, повторюваний, спостережуваний і не потребує ручного виправлення кожного запуску.

## 3. Stage 0 - Product Foundation

Ціль: створити основу, яку не доведеться викидати перед production.

Результат:

- Python/FastAPI service scaffold.
- Typed settings and secrets loading.
- Database connection and migrations.
- Structured project layout under `shorts_factory/`.
- Health and readiness endpoints.
- Base logging without secrets.
- Test and lint commands.
- Local development command.

Exit criteria:

- Service starts locally.
- `/health` and `/ready` work.
- Settings fail clearly when required configuration is missing.
- Tests and lint can be run with documented commands.

## 4. Stage 1 - Telegram Production Flow

Ціль: повний Telegram-ready продукт для автоматичного створення і публікації German Quiz Shorts.

### 1. Quiz Intake

- Quiz Bank API client.
- Approved/published quiz selection.
- Strict quiz schema validation.
- Correct answer integrity checks.
- No AI mutation of quiz facts.

### 2. Generation

- Strict OpenAI JSON contract.
- Script generator for German short format.
- Image prompts without text.
- Image generation pipeline.
- German voice generation.
- Metadata generation for Telegram.

### 3. Rendering

- Render plan model.
- FFmpeg renderer.
- 1080x1920 MP4 output.
- Ken Burns zoom/pan.
- Backend text overlays.
- Voice-over alignment.
- Asset checksums and stored paths.

### 4. QA Gate

- MP4 existence and format check.
- 9:16 aspect ratio check.
- Duration check under 20 seconds.
- Audio presence check.
- Text overlay presence strategy.
- Correct answer match against Quiz Bank.
- Telegram caption check.
- Corrupted file detection.

### 5. Telegram Publishing

- Telegram `sendVideo` integration.
- Publish logs.
- External message ID and URL storage.
- Retry without duplicate publication.
- Manual publish endpoint.

### 6. Worker and Operations

- Manual job creation.
- Scheduled job creation.
- Job lifecycle transitions.
- Retry policy.
- Render logs.
- Admin job endpoints.
- Structured error reporting.

Stage 1 exit criteria:

- One command or scheduled job creates one finished 18-second German MP4 from one approved quiz.
- The video has images, voice, Ken Burns effect, exact backend-rendered text, and QA pass.
- The video is published to Telegram.
- The job record contains status, assets, logs, retry count, and publish link.
- A failed recoverable step can retry without duplicate posts.
- A non-recoverable failure stops with a clear status and error.

## 5. Stage 2 - YouTube Expansion

Ціль: додати YouTube Shorts як другий production publishing target без ламання Telegram flow.

Результат:

- YouTube OAuth credential loading from secrets.
- YouTube Data API `videos.insert` integration.
- YouTube metadata validation.
- `private` or `unlisted` first publishing mode.
- YouTube publish logs.
- Platform-specific retry handling.
- Separate Telegram and YouTube publish status.
- Idempotency for repeated publish attempts.

Stage 2 exit criteria:

- The same QA-passed video can be published to YouTube Shorts.
- YouTube publishing can fail without corrupting Telegram status.
- External YouTube ID, URL, privacy status, and publish timestamp are stored.
- Public publishing is allowed only after quality has been proven.

## 6. Cross-Cutting Rules

- Quiz Bank remains the only source of truth.
- LLM output is always untrusted until validated.
- Image generation never receives instructions to draw text.
- Backend renders all visible text.
- No publishing without QA.
- No duplicate publications on retry.
- No plaintext secrets in database or logs.
- Every external service boundary has timeout, retry, and clear error handling.
- Each milestone must leave tests or explicit verification commands.
