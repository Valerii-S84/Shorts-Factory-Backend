from shorts_factory.db.models import Base
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.dev.offline_providers import OfflineQuizBankClient, OfflineScriptGenerator
from shorts_factory.rendering.render_plan import build_render_plan
from shorts_factory.settings import Settings


def test_offline_script_uses_quiz_facts_without_text_image_prompts() -> None:
    quiz = OfflineQuizBankClient().fetch_next_approved_quiz()
    script = OfflineScriptGenerator().generate(quiz)

    combined_text = "\n".join(frame.text for frame in script.frames)

    assert quiz.question in combined_text
    assert f"{quiz.correct_option_label} {quiz.correct_option.text}" in combined_text
    assert [frame.type.value for frame in script.frames] == [
        "question",
        "options",
        "answer",
    ]
    assert quiz.question in script.voiceover
    assert "Optionen:" in script.voiceover
    assert (
        f"Richtig ist {quiz.correct_option_label}: {quiz.correct_option.text}" in script.voiceover
    )
    assert quiz.explanation in script.voiceover
    assert "Telegram" not in script.voiceover
    for option in quiz.options:
        assert f"{option.label}: {option.text}" in script.voiceover
    assert all("text" not in frame.image_prompt.lower() for frame in script.frames)


def test_offline_render_plan_uses_three_frame_15_5_flow(tmp_path) -> None:
    quiz = OfflineQuizBankClient().fetch_next_approved_quiz()
    script = OfflineScriptGenerator().generate(quiz)

    plan = build_render_plan(
        settings=Settings(environment="test", media_root=tmp_path),
        job_id=1,
        quiz=quiz,
        script=script,
        image_paths=[tmp_path / f"{index}.png" for index in range(1, 4)],
        audio_path=tmp_path / "voiceover.wav",
    )

    assert [frame.type.value for frame in plan.frames] == ["question", "options", "answer"]
    assert plan.duration_sec == 15.5
    assert plan.answer_reveal_at_sec == 10.0
    assert plan.image_count == 3
    assert not plan.has_countdown
    assert not plan.has_cta


def test_repository_allows_empty_target_platforms(tmp_path) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        job = VideoJobRepository(session).create(target_platforms=[])

        assert job.target_platforms == []
    finally:
        session.close()
        engine.dispose()
