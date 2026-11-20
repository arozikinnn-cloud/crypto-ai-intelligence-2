"""Process-wide Gemini pacing for low-quota scheduled TradingAgents runs.

The upstream graph fans out analyst nodes concurrently. Free-tier Gemini projects
may only allow a handful of requests per minute, so serialize and pace actual
provider calls rather than allowing a burst of parallel requests.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0
_RETRY_IN_SECONDS = re.compile(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)
_RETRY_DELAY = re.compile(r'"retryDelay"\s*:\s*"([0-9]+(?:\.[0-9]+)?)s"', re.IGNORECASE)


def is_retryable_provider_error(error: BaseException) -> bool:
    """Recognize rate limits and transient Google API availability failures."""
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    message = str(error).lower()
    return (
        status in {429, 500, 502, 503, 504}
        or any(
            marker in message
            for marker in (
                "resource_exhausted",
                "unavailable",
                "429",
                "500",
                "502",
                "503",
                "504",
                "timed out",
                "readtimeout",
                "connecttimeout",
                "write timeout",
                "pool timeout",
                "temporarily unavailable",
            )
        )
    )


def retry_after_seconds(error: BaseException) -> float:
    """Extract Google's suggested retry delay when it is present."""
    message = str(error)
    for pattern in (_RETRY_IN_SECONDS, _RETRY_DELAY):
        match = pattern.search(message)
        if match:
            return max(0.0, float(match.group(1)))
    return 0.0


def _call_with_throttle(
    call: Callable[[], Any],
    *,
    min_interval: float,
    max_retries: int = 4,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> Any:
    """Serialize requests and retry rate limits or transient transport failures."""
    global _LAST_REQUEST_AT
    with _REQUEST_LOCK:
        for attempt in range(max_retries + 1):
            wait = min_interval - (monotonic() - _LAST_REQUEST_AT)
            if wait > 0:
                sleep(wait)
            _LAST_REQUEST_AT = monotonic()
            try:
                return call()
            except Exception as error:
                if not is_retryable_provider_error(error) or attempt >= max_retries:
                    raise
                backoff = max(
                    min_interval,
                    retry_after_seconds(error) + 1.0,
                    min(60.0, min_interval * (2 ** (attempt + 1))),
                )
                logger.warning(
                    "Gemini transient provider error; retrying after %.1fs (%d/%d).",
                    backoff,
                    attempt + 1,
                    max_retries,
                )
                sleep(backoff)
    raise RuntimeError("Gemini throttle exhausted without returning a response.")


def install_gemini_free_tier_throttle() -> None:
    """Patch the upstream Gemini chat model once per worker process."""
    from tradingagents.llm_clients.google_client import NormalizedChatGoogleGenerativeAI

    model_class = NormalizedChatGoogleGenerativeAI
    if getattr(model_class, "_v8_rate_throttle_installed", False):
        return

    original_generate = model_class._generate
    min_interval = max(
        1.0,
        float(os.getenv("TRADINGAGENTS_GEMINI_MIN_INTERVAL_SECONDS", "13")),
    )
    max_retries = max(0, int(os.getenv("TRADINGAGENTS_GEMINI_RATE_LIMIT_RETRIES", "5")))

    def throttled_generate(self, *args, **kwargs):
        return _call_with_throttle(
            lambda: original_generate(self, *args, **kwargs),
            min_interval=min_interval,
            max_retries=max_retries,
        )

    model_class._generate = throttled_generate
    model_class._v8_rate_throttle_installed = True
    logger.info(
        "Gemini request pacing enabled: one request every %.1fs; %d transient-error retries.",
        min_interval,
        max_retries,
    )
