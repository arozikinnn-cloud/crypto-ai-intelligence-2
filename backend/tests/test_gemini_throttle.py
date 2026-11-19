from app.services.analysis.gemini_throttle import (
    is_rate_limit_error,
    retry_after_seconds,
)


class FakeGeminiError(Exception):
    status_code = 429


def test_detects_gemini_resource_exhausted():
    assert is_rate_limit_error(FakeGeminiError("RESOURCE_EXHAUSTED"))
    assert not is_rate_limit_error(ValueError("invalid request"))


def test_parses_retry_in_seconds():
    assert retry_after_seconds(
        FakeGeminiError("429 RESOURCE_EXHAUSTED. Please retry in 3.95s.")
    ) == 3.95


def test_parses_google_retry_delay():
    assert retry_after_seconds(
        FakeGeminiError('details: {"retryDelay":"7s"}')
    ) == 7.0


def test_missing_retry_delay_returns_zero():
    assert retry_after_seconds(FakeGeminiError("quota exceeded")) == 0.0
