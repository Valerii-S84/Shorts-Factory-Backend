# PRODUCT_VISION

## 1. Product Essence

Shorts Factory Backend is a standalone backend service that turns one quiz from the Quiz Bank API into a short vertical German video for Telegram and YouTube Shorts.

Target video format:

- Aspect ratio: 9:16
- Container: MP4
- Resolution: 1080x1920
- Duration: 15-20 seconds, optimized for 18 seconds
- Language: German
- Media: AI images without text, German voice-over, backend-rendered text overlays
- Motion: Ken Burns zoom/pan effect
- Publishing: Telegram first, YouTube Shorts after the Telegram stage is stable

Core flow:

```text
Quiz Bank -> Backend -> OpenAI -> Images + Voice -> FFmpeg Render -> QA -> Telegram + YouTube
```

## 2. Non-Negotiable Principle

The quiz from Quiz Bank is the only source of truth.

OpenAI must not change:

- question
- correct answer
- answer options
- explanation
- level
- topic

OpenAI may only:

- reformat the short script
- create a short hook
- create image prompts
- generate German voice-over
- prepare title, caption, and description

Exact video text is rendered only by the backend. Image generation must never be asked to draw text.

## 3. Product Quality Bar

Shorts Factory Backend is not a throwaway prototype. Every implementation decision must support a full production product that can be demonstrated at a high professional standard.

The product is delivered in two stable stages:

1. Telegram-first production stage: one quiz becomes one fully QA-checked German short video and is published to Telegram reliably.
2. YouTube expansion stage: YouTube Shorts publishing is added only after the Telegram flow is stable, observable, repeatable, and clear enough to operate without manual fixes.

Stage 1 is not allowed to use shortcuts that would make Stage 2 harder, such as weak data models, unverifiable rendering, missing QA gates, duplicate-prone publishing, or unstructured logs.

## 4. End-To-End Behavior

The service must:

1. Start a job manually or on schedule.
2. Load one quiz from Quiz Bank API.
3. Validate the quiz.
4. Create a short German script.
5. Generate 3-5 text-free images.
6. Generate German voice-over.
7. Create a render plan.
8. Assemble MP4 with FFmpeg.
9. Add Ken Burns zoom/pan.
10. Render exact text overlays.
11. QA-check the final video.
12. Publish to Telegram in Stage 1.
13. Publish to YouTube Shorts in Stage 2.
14. Store logs, statuses, assets, and external links.
15. Retry recoverable failures or mark the job as failed.

## 5. Explicit Non-Goals

The product must not:

- use n8n;
- generate full AI videos;
- ask AI to write text inside images;
- publish without QA;
- change the correct answer;
- use quizzes that are not `approved` or `published`;
- store secrets as plaintext in the database;
- create chaotic content without a stable template.
- treat the first Telegram stage as disposable code.

## 6. Planned Backend Modules

```text
shorts_factory/
|
+-- api/
|   +-- jobs.py
|   +-- health.py
|   +-- admin.py
|
+-- quiz_bank/
|   +-- client.py
|   +-- schemas.py
|
+-- generation/
|   +-- script_generator.py
|   +-- image_generator.py
|   +-- voice_generator.py
|   +-- metadata_generator.py
|
+-- rendering/
|   +-- render_plan.py
|   +-- ffmpeg_renderer.py
|   +-- text_overlay.py
|   +-- qa_probe.py
|
+-- publishing/
|   +-- telegram_publisher.py
|   +-- youtube_publisher.py
|   +-- publish_service.py
|
+-- jobs/
|   +-- scheduler.py
|   +-- worker.py
|   +-- retry_policy.py
|
+-- storage/
|   +-- local_storage.py
|   +-- asset_paths.py
|
+-- db/
|   +-- models.py
|   +-- repositories.py
|
+-- settings.py
```

## 7. Job Lifecycle

Happy path:

```text
created
quiz_loaded
quiz_validated
script_ready
images_ready
audio_ready
render_plan_ready
rendered
qa_passed
telegram_published
youtube_published
done
```

Failure and review states:

```text
failed
retry_pending
manual_review_required
```

## 8. Data Model Fields

### `video_jobs`

- `id`
- `quiz_id`
- `status`
- `locale`
- `level`
- `topic`
- `target_platforms`
- `script_json`
- `render_plan_json`
- `video_path`
- `duration_sec`
- `error_message`
- `retry_count`
- `created_at`
- `updated_at`
- `finished_at`

### `video_assets`

- `id`
- `job_id`
- `type`: `image`, `audio`, `video`, `subtitle`
- `path`
- `checksum`
- `metadata_json`
- `created_at`

### `publish_logs`

- `id`
- `job_id`
- `platform`: `telegram`, `youtube`
- `status`
- `external_id`
- `url`
- `error_message`
- `published_at`
- `created_at`

### `render_logs`

- `id`
- `job_id`
- `step`
- `status`
- `message`
- `created_at`

### `templates`

- `id`
- `name`
- `duration_sec`
- `frame_count`
- `style_json`
- `is_active`
- `created_at`

## 9. Standard 18-Second Template

```text
0-2 sec
Hook:
Kannst du das lösen?

2-6 sec
Question

6-11 sec
Options:
A ...
B ...
C ...

11-14 sec
Pause:
Denk kurz nach ...

14-17 sec
Answer:
Richtig ist: A ...

17-18 sec
CTA:
Mehr Deutsch-Quiz? Folge uns!
```

## 10. Visual Standard

Every video must use a consistent structure:

- vertical 1080x1920 frame;
- 3-5 AI images without text;
- smooth zoom and pan;
- large readable text overlays;
- consistent fonts;
- consistent question zone;
- consistent answer zone;
- consistent CTA zone;
- no visual chaos;
- no tiny text.

## 11. OpenAI Script Contract

Backend sends:

- question
- answer options
- correct answer
- explanation
- topic
- level

OpenAI returns strict JSON:

```json
{
  "hook": "Kannst du das lösen?",
  "voiceover": "...",
  "frames": [
    {
      "type": "hook",
      "text": "Kannst du das lösen?",
      "image_prompt": "..."
    },
    {
      "type": "question",
      "text": "...",
      "image_prompt": "..."
    }
  ],
  "telegram_caption": "...",
  "youtube_title": "...",
  "youtube_description": "..."
}
```

The backend must validate returned JSON before saving or rendering.

## 12. Image Generation Rule

Images are generated without text.

Valid prompt direction:

```text
German classroom, blackboard, person thinking, quiz atmosphere, clean illustration
```

Invalid prompt direction:

```text
draw the question and answer options on the image
```

All text must be added by backend overlay rendering.

## 13. Rendering Contract

FFmpeg rendering must:

- load generated images;
- fit media to 1080x1920;
- add smooth zoom;
- add pan motion;
- add fade transitions;
- overlay exact text;
- overlay voice-over;
- align duration;
- export MP4;
- verify the file.

## 14. QA Gate Before Publishing

The video must not be published if:

- video file is missing;
- file is not MP4;
- aspect ratio is not 9:16;
- duration is over 20 seconds;
- audio is missing;
- text overlay is missing;
- correct answer does not match Quiz Bank;
- Telegram caption is missing;
- YouTube title is missing;
- render failed;
- file is corrupted.

## 15. Publishing

### Telegram

Use Telegram Bot API:

```text
sendVideo
```

Store:

- `telegram_message_id`
- `telegram_chat_id`
- `published_at`

### YouTube

Use YouTube Data API:

```text
videos.insert
```

Store:

- `youtube_video_id`
- `youtube_url`
- `privacy_status`
- `published_at`

Initial YouTube publishing may use `private` or `unlisted`. Public publishing comes after Telegram-stage quality is proven and YouTube publishing has its own QA checks.

## 16. Admin API

Required backend endpoints:

- `POST /jobs/create`
- `POST /jobs/{id}/retry`
- `POST /jobs/{id}/publish/telegram`
- `POST /jobs/{id}/publish/youtube`
- `GET /jobs`
- `GET /jobs/{id}`
- `GET /jobs/{id}/assets`
- `GET /health`
- `GET /ready`

The backend must work without an admin panel.

## 17. Security Requirements

- OpenAI key only in env/secrets.
- Telegram token only in env/secrets.
- YouTube OAuth credentials only in secrets.
- API endpoints protected by an API key.
- Job creation is not public.
- Logs must not contain secrets.
- Video files need controlled access.
- Retry must not create duplicate publications.

## 18. Retry Policy

Retry is allowed for:

- OpenAI timeout
- image generation failed
- audio generation failed
- render failed
- Telegram 5xx
- YouTube temporary error

Retry is not allowed for:

- invalid quiz schema
- missing correct answer
- policy fail
- missing publishing permission
- invalid credentials

## 19. Stage 1 Production Goal

The first complete production result:

```text
one command or one scheduled job
creates one finished 18-second MP4
from one quiz
in German
with images
with voice
with Ken Burns effect
with exact text
and publishes it to a Telegram channel
```

This result must be reliable, observable, QA-gated, and suitable for a professional product presentation. YouTube publishing is added after this stage is stable.

## 20. Final Vision

Shorts Factory Backend is a production service that turns verified Quiz Bank content into a constant flow of German Quiz Shorts for audience growth, user engagement, and future monetization.

Final formula:

```text
verified Quiz Bank
+
OpenAI generation
+
controlled backend rendering
+
automatic publishing
=
continuous German Quiz Shorts
```
