from shorts_factory.jobs.retry_policy import RetryAction, retry_action_for_error


def test_retry_policy_retries_recoverable_errors() -> None:
    assert retry_action_for_error("OpenAI timeout", retry_count=0) == RetryAction.RETRY


def test_retry_policy_sends_non_retryable_errors_to_manual_review() -> None:
    assert retry_action_for_error("invalid credentials", retry_count=0) == RetryAction.MANUAL_REVIEW


def test_retry_policy_fails_after_max_retries() -> None:
    assert retry_action_for_error("render failed", retry_count=3) == RetryAction.FAIL
