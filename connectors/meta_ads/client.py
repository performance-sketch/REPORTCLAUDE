from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class MetaAdsAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Meta Ads API {status_code}: {message}")


class MetaAdsRateLimitError(MetaAdsAPIError):
    pass


class MetaAdsClient:
    def __init__(
        self,
        access_token: str,
        api_version: str = "v19.0",
        timeout: float = 30.0,
    ) -> None:
        self._token = access_token
        self._base = f"https://graph.facebook.com/{api_version}"
        self._timeout = timeout

    @retry(
        retry=retry_if_exception_type((MetaAdsRateLimitError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        merged = {"access_token": self._token, **(params or {})}
        url = f"{self._base}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            logger.debug("GET %s params=%s", url, {k: v for k, v in merged.items() if k != "access_token"})
            resp = await client.get(url, params=merged)

        if resp.status_code == 429:
            raise MetaAdsRateLimitError(429, "Rate limit exceeded")

        if resp.status_code in _RETRYABLE_STATUS:
            raise MetaAdsAPIError(resp.status_code, resp.text[:300])

        if not resp.is_success:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            error = body.get("error", {})
            raise MetaAdsAPIError(resp.status_code, error.get("message", resp.text[:300]))

        return resp.json()

    async def get_paginated(
        self, endpoint: str, params: dict[str, Any] | None = None, max_pages: int = 200
    ):
        """Yields each page dict. Follows cursor-based pagination."""
        current_params = dict(params or {})
        page_count = 0

        while page_count < max_pages:
            page = await self.get(endpoint, current_params)
            yield page
            page_count += 1

            paging = page.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break

            # Extract `after` cursor from next URL to avoid re-passing full URL
            cursors = paging.get("cursors", {})
            after = cursors.get("after")
            if after:
                current_params = {**current_params, "after": after}
            else:
                break

        if page_count >= max_pages:
            logger.warning("Reached max_pages=%d for endpoint %s", max_pages, endpoint)
