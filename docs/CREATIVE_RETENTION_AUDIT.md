# Creative / Retention Audit

Статус: audit-only.

Scope:

- Перевірено current video flow для короткої вірусної German quiz-механіки.
- Код не змінювався.
- OpenAI generation не запускалась.
- Quiz facts, answers, explanations не змінювались.

Джерела аудиту:

- `shorts_factory/rendering/render_plan.py`
- `shorts_factory/rendering/text_overlay.py`
- `shorts_factory/rendering/ffmpeg_renderer.py`
- `shorts_factory/rendering/qa_probe.py`
- `shorts_factory/generation/schemas.py`
- `shorts_factory/generation/script_generator.py`
- `shorts_factory/generation/voice_generator.py`
- `shorts_factory/generation/image_prompt_builder.py`
- `shorts_factory/jobs/worker.py`
- `shorts_factory/dev/offline_providers.py`
- `shorts_factory/db/models.py`
- `docs/PRODUCT_VISION.md`

## Executive Decision

GO / NO-GO:

- GO: переходити до наступної coding-фази для retention improvements.
- NO-GO: вважати поточний flow готовим саме як вірусну Telegram acquisition-вікторину.

Факт: поточний backend має сильну технічну основу: immutable Quiz Bank facts, backend-rendered text, FFmpeg assembly, QA gate, Telegram publishing guardrails.

Висновок: current flow більше схожий на стабільний quiz-video renderer, ніж на production viral quiz template. Йому бракує гарантованого hook, countdown/tension, answer reveal pacing, final CTA і metrics attribution.

Рекомендація: не міняти quiz facts. Міняти тільки creative structure, timing, overlay templates, CTA, audio cues і metrics model.

## Current Flow Summary

### Video Structure

Факт:

- `FrameType` підтримує `hook`, `question`, `options`, `pause`, `answer`, `cta`.
- `GeneratedScript.frames` дозволяє 3-5 кадрів.
- Required frames: `question`, `options`, `answer`.
- `hook`, `pause`, `cta` не є обов'язковими.
- Full six-stage flow `hook -> question -> options -> pause -> answer -> cta` зараз неможливий у межах `max_length=5`.

Фактичні duration rules:

| Frame | Duration |
|---|---:|
| `hook` | 2.0s |
| `question` | 4.0s |
| `options` | 5.0s |
| `pause` | 3.0s |
| `answer` | 3.0s |
| `cta` | 1.0s |

Факт: final video duration рахується як сума наявних frames, а не як завжди 18 секунд.

Приклади фактичної довжини:

| Frame sequence | Duration | Notes |
|---|---:|---|
| `question -> options -> answer` | 12s | Мінімально валідний script. Немає hook, pause, CTA. |
| `question -> options -> answer -> cta` | 13s | Є CTA, але немає hook і thinking pause. |
| `hook -> question -> options -> answer` | 14s | Offline fixture. Є hook, але немає pause і CTA. |
| `hook -> question -> options -> answer -> cta` | 15s | Є hook і CTA, але немає countdown/tension pause. |
| `hook -> question -> options -> pause -> answer` | 17s | Є tension pause, але немає final CTA. |

Факт: `docs/PRODUCT_VISION.md` описує standard 18-second template, але implementation не гарантує 18 секунд.

Висновок: поточний flow не має стабільного production timing для retention. Ролики можуть бути 12-17 секунд залежно від OpenAI script frames.

### When Key Moments Appear

Факт: порядок кадрів береться з `script.frames`. Schema перевіряє наявність required frame types, але не фіксує порядок.

Якщо використовується типовий порядок `hook -> question -> options -> pause -> answer`:

| Time | Event |
|---|---|
| 0.0-2.0s | Hook |
| 2.0-6.0s | Question |
| 6.0-11.0s | Options |
| 11.0-14.0s | Pause / thinking |
| 14.0-17.0s | Answer reveal |

Якщо використовується offline fixture `hook -> question -> options -> answer`:

| Time | Event |
|---|---|
| 0.0-2.0s | Hook |
| 2.0-6.0s | Question |
| 6.0-11.0s | Options |
| 11.0-14.0s | Answer reveal |

Висновок: answer reveal може бути достатньо швидким, але tension pause не гарантована. CTA несумісний з повним hook + pause + answer flow через current 5-frame limit.

### Quiz Facts Integrity

Факт:

- Question overlay береться напряму з `quiz.question`.
- Options overlay збирається напряму з `quiz.options`.
- Answer overlay збирається як `Richtig ist: {label} {text}` з Quiz Bank correct option.
- QA перевіряє correct answer label/text проти Quiz Bank.

Висновок: integrity layer сильний. Creative changes потрібно робити навколо фактів, не всередині фактів.

## Problems

### 1. Hook Is Not Guaranteed

Факт:

- Top-level `hook` у `GeneratedScript` required.
- Але frame type `hook` не required.
- Offline fixture завжди використовує `Kannst du das lösen?`.
- OpenAI system prompt не вимагає hook variation, template family або anti-repetition.

Висновок:

- За 1 секунду ролик не завжди пояснює, що це German quiz.
- Hook може повторюватися однаково в кожному відео.
- Hook не прив'язаний до level/topic/trap.

Рекомендація:

- Зробити `hook` required frame для viral templates.
- Додати hook families:
  - `Kannst du das richtig beantworten?`
  - `90% machen hier einen Fehler`
  - `Welche Antwort ist richtig?`
  - `A1 oder B1? Teste dich!`
  - `Nur 5 Sekunden: Was passt?`
- Ротувати hook variants і зберігати `hook_variant_id`.

### 2. Tension Is Optional

Факт:

- `pause` frame існує, але не required.
- Немає countdown render logic.
- Немає visual timer.
- Немає sound effects для countdown або reveal.

Висновок:

- Вікторина не завжди створює pressure to guess.
- User може побачити question/options/answer як звичайний informational card, а не як challenge.

Рекомендація:

- Для production templates зробити thinking segment обов'язковим: 2.5-3.0s.
- Додати countdown overlay `3 -> 2 -> 1` або progress ring.
- Reveal answer після countdown, не одразу після options.

### 3. CTA Is Not Guaranteed And Too Short

Факт:

- `cta` frame існує, але не required.
- `cta` duration = 1.0s.
- Full flow з hook, question, options, pause, answer, CTA зараз неможливий через `max_length=5`.
- Telegram caption існує, але це не заміна visible final CTA в самому відео.

Висновок:

- Поточний ролик може не вести користувача в Telegram-канал.
- Навіть якщо CTA є, 1 секунда занадто коротка для читання і дії.

Рекомендація:

- Виділити CTA 1.5-2.0s.
- CTA має бути короткий, без spam-подачі:
  - `Mehr Deutsch-Quiz im Telegram-Kanal`
  - `Täglich neue Deutsch-Tests im Kanal`
  - `Link im Profil - teste dein Deutsch weiter`

### 4. Explanation Is Not Visible

Факт:

- Answer overlay показує тільки correct label + answer text.
- Quiz explanation не додається в answer overlay.
- Voiceover може містити explanation, але contract не гарантує коротке пояснення після answer.

Висновок:

- Після reveal бракує learning payoff.
- Коментарі й повторні перегляди можуть бути нижчими, бо user не отримує коротке "чому".

Рекомендація:

- Після answer додавати 1-line explanation з Quiz Bank explanation.
- Не змінювати explanation, тільки стисло показувати approved source text або його backend-controlled safe excerpt, якщо це буде окремо дозволено product rules.

### 5. Overlay Has One Template For Every Moment

Факт:

- Усі frame types використовують один `TextOverlay` style:
  - `font_size=64`
  - `x=(w-text_w)/2`
  - `y=h*0.68`
  - `boxcolor=black@0.65`
  - `max_line_chars=28`
- Немає окремих overlay templates для hook/question/options/answer/CTA.
- `wrap(..., break_long_words=False)` не ламає довгі German compounds.

Висновок:

- Текст загалом великий, але layout не адаптується до довгих questions/options.
- Options можуть займати забагато vertical space в lower third.
- CTA і answer не отримують окрему visual hierarchy.

Рекомендація:

- Ввести overlay templates:
  - `hook`: large centered/top badge, максимум 1-2 lines.
  - `question`: readable question card, 2-3 lines.
  - `options`: structured A/B/C rows.
  - `pause`: countdown digits or timer.
  - `answer`: green reveal + correct option emphasis.
  - `cta`: compact final card, Telegram/channel-focused.
- Додати dynamic font sizing and safe-area checks.

### 6. Audio Is Voiceover-Only

Факт:

- `OpenAIVoiceGenerator` генерує один voiceover audio file.
- FFmpeg trims/pads audio to render duration.
- Немає background music mix.
- Немає SFX channels.
- Немає per-frame voice timing alignment.

Висновок:

- Voiceover корисний для German learning, але retention moment weak без ticks/reveal.
- Якщо voiceover довший за plan duration, він може бути обрізаний.
- Silent autoplay має бути зрозумілим тільки з overlay, і це частково виконується.

Рекомендація:

- Залишити відео fully understandable без звуку.
- Додати optional low-volume music bed.
- Додати короткі SFX:
  - countdown tick;
  - answer reveal;
  - correct moment.
- Voiceover має бути короткий і синхронізований із frame timings.

### 7. Metrics Are Not Part Of Creative Loop

Факт:

- Current DB зберігає jobs, assets, publish logs, render logs.
- Немає model або import flow для retention analytics, views, profile clicks, Telegram joins.
- Немає variant naming convention.

Висновок:

- Неможливо системно зрозуміти, який hook/template/CTA веде до retention або Telegram joins.

Рекомендація:

- Зберігати template/variant metadata перед publish.
- Збирати platform metrics після публікації.
- Використовувати trackable Telegram invite/profile links для CTA variants.

## Recommended Viral Video Structure

Target: 16-18 секунд.

Production sequence:

| Time | Segment | Goal | Overlay |
|---|---|---|---|
| 0.0-1.5s | Hook | Зупинити swipe | `90% machen hier einen Fehler` / `A1 oder B1?` |
| 1.5-4.0s | Question | Зрозумілий quiz setup | Exact Quiz Bank question |
| 4.0-9.0s | Options | Дати шанс вгадати | A/B/C rows from Quiz Bank |
| 9.0-12.0s | Countdown | Створити tension | `3`, `2`, `1` or progress timer |
| 12.0-15.5s | Answer + Why | Reward | Correct answer + short explanation |
| 15.5-18.0s | CTA | Telegram conversion | `Mehr Deutsch-Quiz im Telegram-Kanal` |

Creative principles:

- First second must say this is a German quiz or level test.
- Correct answer should not appear before the reveal segment.
- Options should stay long enough for a guess, but not feel like dead air.
- CTA should be one short action, not a paragraph.
- Video should work muted.
- Audio should improve tension, not carry essential facts.

Implementation implication:

- Current `max_length=5` blocks this full structure.
- Either allow 6 frames for production templates or model `countdown` as timed sub-overlay inside options/answer.

## Five Reusable Production Templates

### 1. Mistake-Based Quiz

Use case: grammar/article/vocabulary traps where many learners choose the wrong option.

Hook examples:

- `90% machen hier einen Fehler`
- `Vorsicht: Das ist eine Falle`
- `Welche Antwort klingt falsch, ist aber richtig?`

Timing:

| Time | Segment |
|---|---|
| 0.0-1.5s | Mistake hook |
| 1.5-4.0s | Question |
| 4.0-9.0s | Options |
| 9.0-12.0s | Countdown |
| 12.0-15.5s | Correct answer + explanation |
| 15.5-18.0s | CTA |

CTA:

- `Mehr Deutsch-Fallen im Telegram-Kanal`

Retention hypothesis:

- Mistake framing increases comments because users want to defend or compare answers.

### 2. Level Test Quiz

Use case: A1/A2/B1/B2 self-assessment.

Hook examples:

- `A1 oder B1? Teste dich!`
- `Welches Deutsch-Level hast du?`
- `Schaffst du diese A2-Frage?`

Timing:

| Time | Segment |
|---|---|
| 0.0-1.5s | Level badge + hook |
| 1.5-4.5s | Question |
| 4.5-9.5s | Options |
| 9.5-12.0s | Thinking pause |
| 12.0-15.5s | Answer + explanation |
| 15.5-18.0s | CTA |

CTA:

- `Täglich neue Deutsch-Tests im Kanal`

Retention hypothesis:

- Level identity gives users a reason to complete and share.

### 3. Speed Challenge

Use case: simple facts or short vocabulary questions.

Hook examples:

- `5 Sekunden - welche Antwort?`
- `Schnell: A, B oder C?`
- `Antwortest du schneller als andere?`

Timing:

| Time | Segment |
|---|---|
| 0.0-1.0s | Speed hook |
| 1.0-3.5s | Question |
| 3.5-8.5s | Options with visible timer |
| 8.5-10.5s | Fast countdown |
| 10.5-14.0s | Answer + explanation |
| 14.0-16.0s | CTA |

CTA:

- `Mehr schnelle Deutsch-Quiz im Kanal`

Retention hypothesis:

- Shorter loop can improve completion rate and rewatch rate.

### 4. Grammar Trap

Use case: cases, articles, prepositions, word order.

Hook examples:

- `Der, die oder das?`
- `Akkusativ oder Dativ?`
- `Diese Grammatik-Falle ist gemein`

Timing:

| Time | Segment |
|---|---|
| 0.0-1.5s | Trap hook |
| 1.5-4.5s | Question |
| 4.5-10.0s | Options |
| 10.0-12.5s | Countdown |
| 12.5-16.0s | Answer + rule explanation |
| 16.0-18.0s | CTA |

CTA:

- `Mehr Grammatik-Quiz im Telegram-Kanal`

Retention hypothesis:

- Grammar trap content creates strong "I know this" participation.

### 5. Alltagssituation Quiz

Use case: practical German phrases and everyday contexts.

Hook examples:

- `Im Supermarkt: Was sagst du?`
- `Beim Arzt: Welche Antwort passt?`
- `Alltagsdeutsch in 10 Sekunden`

Timing:

| Time | Segment |
|---|---|
| 0.0-2.0s | Situation hook |
| 2.0-4.5s | Question |
| 4.5-9.5s | Options |
| 9.5-12.0s | Thinking pause |
| 12.0-15.5s | Answer + short context explanation |
| 15.5-18.0s | CTA |

CTA:

- `Link im Profil - teste dein Deutsch weiter`

Retention hypothesis:

- Scenario framing makes the quiz feel useful, not abstract.

## CTA Recommendations

CTA rules:

- One CTA per video.
- Maximum 1 short sentence.
- No generic spam phrases like `Abonnieren!!!`.
- CTA should name the benefit: more tests, daily quiz, grammar traps, level practice.
- CTA should be visible in final frame and optionally repeated in caption.

Recommended CTA pool:

- `Mehr Deutsch-Quiz im Telegram-Kanal`
- `Täglich neue Deutsch-Tests im Kanal`
- `Link im Profil - teste dein Deutsch weiter`
- `Mehr Grammatik-Fallen im Kanal`
- `Teste dein Deutsch jeden Tag im Kanal`

Telegram caption examples:

- `Wie viele hattest du richtig? Mehr Deutsch-Quiz im Kanal.`
- `Heute: Artikel-Quiz. Täglich neue Deutsch-Tests im Kanal.`
- `Schreib deine Antwort in die Kommentare und teste weiter im Kanal.`

CTA variant IDs:

- `cta_more_quiz`
- `cta_daily_tests`
- `cta_link_profile`
- `cta_grammar_traps`
- `cta_daily_channel`

## Metrics Plan

### Metrics To Collect

Platform metrics:

- views;
- average view duration;
- retention curve;
- swipe-away / drop-off points;
- likes;
- comments;
- shares, if available;
- saves, if available;
- profile clicks;
- channel clicks;
- Telegram channel joins.

Creative metadata:

- `video_id`;
- `quiz_id`;
- `topic`;
- `level`;
- `template_id`;
- `hook_variant_id`;
- `cta_variant_id`;
- `duration_sec`;
- `frame_sequence`;
- `answer_reveal_at_sec`;
- `has_countdown`;
- `has_voiceover`;
- `has_music`;
- `has_sfx`;
- `published_at`;
- `platform`;
- `publish_url`;
- `telegram_invite_link_id`, if used.

Derived metrics:

- 1-second hold rate;
- 3-second hold rate;
- completion rate;
- answer reveal reach rate;
- CTA reach rate;
- comment rate per 1,000 views;
- Telegram join rate per 1,000 views;
- joins per CTA reach;
- retention drop before answer reveal;
- retention drop after answer reveal.

### Drop-Off Diagnosis

Interpretation guide:

| Signal | Likely issue |
|---|---|
| Drop before 1s | Hook or first frame unclear. |
| Drop before options | Question too slow or too text-heavy. |
| Drop during options | Pause too long, options unreadable, no timer. |
| Drop just before answer | Countdown too long or weak tension. |
| Drop immediately after answer | No explanation payoff or CTA appears too late. |
| Low clicks despite high completion | CTA weak, not specific, or not trackable. |

### Naming Convention For Variants

Use one internal variant key per published video:

```text
sf-de-{date}-{level}-{topic_slug}-{quiz_id}-{template_id}-{hook_id}-{timing_id}-{cta_id}-v{nn}
```

Example:

```text
sf-de-20260515-a1-artikel-qzb123-mistake-h90p-t18-cta_more_quiz-v01
```

Recommended IDs:

| Dimension | Example IDs |
|---|---|
| Template | `mistake`, `level_test`, `speed`, `grammar_trap`, `alltag` |
| Hook | `h90p`, `h_level`, `h_5sec`, `h_trap`, `h_situation` |
| Timing | `t16`, `t18`, `t18_countdown`, `t15_fast` |
| CTA | `cta_more_quiz`, `cta_daily_tests`, `cta_link_profile` |
| Audio | `a_vo`, `a_vo_sfx`, `a_silent_music` |

Public title/caption should stay user-facing. Internal variant IDs should live in metadata, filename, render plan, or analytics tables.

## Implementation Tasks For Next Coding Phase

1. Add a production template registry.
   - Store `template_id`, frame sequence, segment timings, hook family, CTA family, audio policy.

2. Enforce ordered frame sequence per selected template.
   - Current schema only requires frame presence.
   - Production templates should enforce `hook -> question -> options -> pause/countdown -> answer -> cta` or an approved compact variant.

3. Decide how to support full viral structure.
   - Option A: allow 6 frames.
   - Option B: keep 5 frames and model countdown/CTA as sub-overlays inside existing frames.
   - Recommendation: allow 6 frames for clarity and analytics.

4. Build backend-owned overlay templates.
   - Separate layouts for hook, question, options, countdown, answer, explanation, CTA.
   - Add dynamic font sizing and safe-area checks.

5. Add answer explanation rendering.
   - Show correct answer and a short explanation after reveal.
   - Do not change quiz facts, answers, or source explanation meaning.

6. Add hook and CTA variant rotation.
   - Prevent identical hook reuse across consecutive videos.
   - Store `hook_variant_id` and `cta_variant_id`.

7. Add countdown and reveal mechanics.
   - Countdown visual or progress ring.
   - Answer reveal emphasis.
   - Optional SFX: tick, reveal, correct.

8. Add audio mixing policy.
   - Keep text complete without sound.
   - Voiceover should be short and aligned to segment timings.
   - Optional background music and SFX must not hide voiceover.

9. Add creative QA gates.
   - Required CTA present.
   - Required hook present.
   - Answer reveal time within allowed range.
   - Duration in target range.
   - Explanation present after answer.
   - No text overflow risk for long options.

10. Add metrics storage/import.
    - Store creative variant metadata at render/publish time.
    - Add analytics snapshots for views, retention, engagement, profile clicks, Telegram joins.
    - Support trackable Telegram links per CTA variant.

11. Add tests for all production templates.
    - Frame order.
    - Duration.
    - answer reveal timing.
    - CTA presence.
    - Quiz facts unchanged.
    - Render plan contains expected creative metadata.

## Final Assessment

Факт:

- Current renderer can create vertical quiz videos with exact backend overlays and correct answer integrity.
- Current worker can run the technical generation/render/QA/publish pipeline.
- Current structure does not guarantee viral quiz mechanics.

Висновок:

- Technical foundation: strong enough.
- Creative retention layer: incomplete.
- Telegram acquisition layer: incomplete.

Рекомендація:

- Proceed with a focused implementation phase for templates, timing, CTA, countdown, overlay variants, audio cues, and metrics.
- Do not publish current flow as the final viral Telegram quiz format without these changes.

Недоведено:

- No real OpenAI output was generated during this audit.
- No real production video was rendered or visually inspected during this audit.
- No Telegram/YouTube analytics were available in the repository.
- Actual retention performance must be validated after publishing measured variants.
