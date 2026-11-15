import asyncio

import httpx

from app.services.market_data.base import MarketDataError


async def get_json_with_retry(
    client: httpx.AsyncClient,
    path: str,
    params: dict,
    source_name: str,
    attempts: int = 3,
) -> object:
    """Retry transient network, rate-limit and 5xx failures with bounded backoff."""
    if not 1 <= attempts <= 5:
        raise ValueError("attempts must be between 1 and 5.")
    for attempt in range(attempts):
        try:
            response = await client.get(path, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < attempts:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(max(float(retry_after), 0.25), 5.0)
                    except (TypeError, ValueError):
                        delay = min(0.5 * (2 ** attempt), 2.0)
                    await asyncio.sleep(delay)
                    continue
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                raise MarketDataError(
                    f"{source_name} returned invalid JSON."
                ) from exc
        except httpx.RequestError as exc:
            if attempt + 1 < attempts:
                await asyncio.sleep(min(0.5 * (2 ** attempt), 2.0))
                continue
            raise MarketDataError(f"{source_name} request failed.") from exc
        except httpx.HTTPStatusError as exc:
            raise MarketDataError(
                f"{source_name} request failed with HTTP {exc.response.status_code}."
            ) from exc
    raise MarketDataError(f"{source_name} request failed after retries.")
