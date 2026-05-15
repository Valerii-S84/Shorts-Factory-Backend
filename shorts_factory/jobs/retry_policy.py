from __future__ import annotations

from enum import StrEnum


class RetryAction(StrEnum):
    RETRY = "retry"
    FAIL = "fail"
    MANUAL_REVIEW = "manual_review"


RECOVERABLE_MARKERS = (
    "timeout",
    "image generation failed",
    "audio generation failed",
    "render failed",
    "telegram 5xx",
    "youtube temporary error",
)

NON_RETRYABLE_MARKERS = (
    "invalid quiz schema",
    "missing correct answer",
    "policy fail",
    "missing publishing permission",
    "invalid credentials",
)


def retry_action_for_error(
    error_message: str, retry_count: int, max_retries: int = 3
) -> RetryAction:
    normalized = error_message.lower()
    if any(marker in normalized for marker in NON_RETRYABLE_MARKERS):
        return RetryAction.MANUAL_REVIEW
    if retry_count >= max_retries:
        return RetryAction.FAIL
    if any(marker in normalized for marker in RECOVERABLE_MARKERS):
        return RetryAction.RETRY
    return RetryAction.FAIL
