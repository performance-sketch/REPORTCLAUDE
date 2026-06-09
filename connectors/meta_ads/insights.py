from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import AsyncIterator

from .client import MetaAdsClient
from .schemas import MetaInsightRow

logger = logging.getLogger(__name__)

FIELDS = ",".join([
    "date_start", "date_stop",
    "account_id", "account_name",
    "campaign_id", "campaign_name",
    "adset_id", "adset_name",
    "ad_id", "ad_name",
    "impressions", "reach", "frequency",
    "clicks", "inline_link_clicks", "landing_page_views",
    "spend", "cpc", "cpm", "ctr",
    "actions", "action_values",
])

LEVELS = ("account", "campaign", "adset", "ad")


async def fetch_insights(
    client: MetaAdsClient,
    account_id: str,
    date_start: date,
    date_stop: date,
    level: str = "ad",
    attribution_window: str = "",
    limit: int = 500,
) -> AsyncIterator[MetaInsightRow]:
    """Yields MetaInsightRow for each row returned by the Insights API."""
    params: dict = {
        "level": level,
        "fields": FIELDS,
        "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
        "time_increment": 1,
        "limit": limit,
    }
    if attribution_window:
        params["attribution_setting"] = attribution_window

    rows_yielded = 0
    async for page in client.get_paginated(f"{account_id}/insights", params):
        for raw in page.get("data", []):
            raw["account_id"] = raw.get("account_id") or account_id.replace("act_", "")
            try:
                yield MetaInsightRow.model_validate(raw)
                rows_yielded += 1
            except Exception as exc:
                logger.warning("Failed to parse insight row: %s — %s", exc, raw)

    logger.info(
        "fetch_insights account=%s %s–%s level=%s rows=%d",
        account_id, date_start, date_stop, level, rows_yielded,
    )


def date_range(start: date, end: date) -> tuple[date, date]:
    return start, end


def last_n_days(n: int) -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=n), today - timedelta(days=1)
