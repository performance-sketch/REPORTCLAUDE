"""
Meta Ads Worker
===============
Busca dados de performance via Insights API e faz upsert em
fact_meta_ad_performance_daily. Roda via APScheduler ou trigger manual.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Garante que o monorepo raiz está no PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.app.config import get_settings
from apps.api.app.models.facts import FactMetaAdPerformanceDaily, FactSyncHealth
from connectors.meta_ads.client import MetaAdsClient
from connectors.meta_ads.insights import fetch_insights, last_n_days
from connectors.meta_ads.schemas import MetaInsightRow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


async def _upsert_row(session: AsyncSession, row: MetaInsightRow, attribution_window: str = "") -> None:
    values = dict(
        date=row.date_start,
        account_id=row.account_id,
        account_name=row.account_name,
        campaign_id=row.campaign_id or "",
        campaign_name=row.campaign_name,
        adset_id=row.adset_id or "",
        adset_name=row.adset_name,
        ad_id=row.ad_id or "",
        ad_name=row.ad_name,
        impressions=row.impressions,
        reach=row.reach,
        frequency=row.frequency,
        clicks=row.clicks,
        link_clicks=row.inline_link_clicks,
        landing_page_views=row.landing_page_views,
        spend=row.spend,
        leads=row.leads,
        purchases=row.purchases,
        conversions=row.conversions,
        conversion_value=row.conversion_value,
        cpc=row.cpc,
        cpm=row.cpm,
        ctr=row.ctr,
        attribution_window=attribution_window,
        raw_payload={
            "actions": [a.model_dump() for a in row.actions],
            "action_values": [a.model_dump() for a in row.action_values],
        },
        updated_at=datetime.now(tz=timezone.utc),
    )
    stmt = (
        pg_insert(FactMetaAdPerformanceDaily)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_meta_perf_daily",
            set_={k: v for k, v in values.items() if k not in ("date", "account_id", "campaign_id", "adset_id", "ad_id", "attribution_window")},
        )
    )
    await session.execute(stmt)


async def run_meta_ads_sync(lookback_days: int | None = None) -> None:
    lookback = lookback_days or settings.meta_ads_lookback_days
    date_start, date_end = last_n_days(lookback)
    account_ids = settings.meta_account_id_list

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    client = MetaAdsClient(
        access_token=settings.meta_access_token,
        api_version=settings.meta_api_version,
    )

    async with SessionLocal() as session:
        sync_record = FactSyncHealth(
            source="meta_ads",
            sync_type=f"incremental_{lookback}d",
            started_at=datetime.now(tz=timezone.utc),
            status="running",
        )
        session.add(sync_record)
        await session.commit()

        total_processed = total_failed = 0

        try:
            for account_id in account_ids:
                logger.info("Syncing account=%s %s → %s", account_id, date_start, date_end)
                async for row in fetch_insights(client, account_id, date_start, date_end, level="ad"):
                    try:
                        await _upsert_row(session, row)
                        total_processed += 1
                    except Exception as exc:
                        logger.error("Failed to upsert row %s: %s", row.ad_id, exc)
                        total_failed += 1

                if total_processed % 200 == 0 and total_processed > 0:
                    await session.commit()

            await session.commit()
            sync_record.status = "success"
        except Exception as exc:
            logger.exception("Meta Ads sync failed: %s", exc)
            sync_record.status = "error"
            sync_record.error_message = str(exc)[:500]
        finally:
            sync_record.finished_at = datetime.now(tz=timezone.utc)
            sync_record.records_processed = total_processed
            sync_record.records_failed = total_failed
            await session.commit()

    await engine.dispose()
    logger.info("Meta Ads sync done processed=%d failed=%d", total_processed, total_failed)


async def run_full_backfill() -> None:
    """Reprocessa os últimos 30 dias para corrigir atrasos de atribuição."""
    logger.info("Starting full backfill (%d days)", settings.meta_ads_full_lookback_days)
    await run_meta_ads_sync(lookback_days=settings.meta_ads_full_lookback_days)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-backfill", action="store_true")
    parser.add_argument("--lookback-days", type=int, default=None)
    args = parser.parse_args()

    if args.full_backfill:
        asyncio.run(run_full_backfill())
    else:
        asyncio.run(run_meta_ads_sync(args.lookback_days))
