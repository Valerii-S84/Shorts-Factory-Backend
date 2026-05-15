from shorts_factory.db.models import Base
from shorts_factory.db.repositories import VideoJobRepository
from shorts_factory.db.session import create_database_engine, create_session_factory
from shorts_factory.dev.offline_providers import OfflineQuizBankClient, OfflineScriptGenerator


def test_offline_script_uses_quiz_facts_without_text_image_prompts() -> None:
    quiz = OfflineQuizBankClient().fetch_next_approved_quiz()
    script = OfflineScriptGenerator().generate(quiz)

    combined_text = "\n".join(frame.text for frame in script.frames)

    assert quiz.question in combined_text
    assert f"{quiz.correct_option_label} {quiz.correct_option.text}" in combined_text
    assert [frame.type.value for frame in script.frames] == [
        "hook",
        "question",
        "options",
        "pause",
        "answer",
        "cta",
    ]
    assert all("text" not in frame.image_prompt.lower() for frame in script.frames)


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
