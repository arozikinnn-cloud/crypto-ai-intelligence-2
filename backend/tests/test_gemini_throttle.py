import app.services.analysis.gemini_throttle as throttle
from app.services.analysis.gemini_throttle import (
    is_retryable_provider_error,
    retry_after_seconds,
)


class FakeGeminiError(Exception):
    status_code = 429


class FakeUnavailableError(Exception):
    status_code = 503


def test_detects_gemini_resource_exhausted():
    assert is_retryable_provider_error(FakeGeminiError("RESOURCE_EXHAUSTED"))
    assert not is_retryable_provider_error(ValueError("invalid request"))
    assert is_retryable_provider_error(FakeUnavailableError("503 UNAVAILABLE"))


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


def test_call_with_throttle_retries_429_with_bounded_backoff(monkeypatch):
    monkeypatch.setattr(throttle, "_LAST_REQUEST_AT", 0.0)
    clock = [100.0]
    sleeps = []
    attempts = []

    def fake_monotonic():
        return clock[0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    def flaky_call():
        attempts.append(1)
        if len(attempts) == 1:
            raise FakeGeminiError("429 RESOURCE_EXHAUSTED. retry in 2s")
        return "ok"

    result = throttle._call_with_throttle(
        flaky_call,
        min_interval=13.0,
        max_retries=1,
        sleep=fake_sleep,
        monotonic=fake_monotonic,
    )

    assert result == "ok"
    assert len(attempts) == 2
    assert sleeps == [26.0]

def test_retries_transient_503_provider_error(monkeypatch):
    monkeypatch.setattr(throttle, "_LAST_REQUEST_AT", 0.0)
    clock = [100.0]
    sleeps = []
    attempts = []

    def fake_monotonic():
        return clock[0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    def flaky_call():
        attempts.append(1)
        if len(attempts) == 1:
            raise FakeUnavailableError("503 UNAVAILABLE: high demand")
        return "ok"

    result = throttle._call_with_throttle(
        flaky_call,
        min_interval=13.0,
        max_retries=1,
        sleep=fake_sleep,
        monotonic=fake_monotonic,
    )

    assert result == "ok"
    assert len(attempts) == 2
    assert sleeps == [26.0]



def test_retries_transient_read_timeout(monkeypatch):
    monkeypatch.setattr(throttle, "_LAST_REQUEST_AT", 0.0)
    clock = [100.0]
    sleeps = []
    attempts = []

    def fake_monotonic():
        return clock[0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    def flaky_call():
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("The read operation timed out")
        return "ok"

    result = throttle._call_with_throttle(
        flaky_call,
        min_interval=13.0,
        max_retries=1,
        sleep=fake_sleep,
        monotonic=fake_monotonic,
    )

    assert result == "ok"
    assert len(attempts) == 2
    assert sleeps == [26.0]


def test_does_not_retry_unrelated_timeout_word_in_validation_error():
    assert not is_retryable_provider_error(ValueError("timeout setting is invalid"))
