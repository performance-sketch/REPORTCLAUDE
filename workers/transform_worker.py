"""
Transform Worker
================
Processa raw_events pendentes e popula as tabelas fato.
Roda em loop contínuo ou pode ser invocado pontualmente.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.app.config import get_settings
from apps.api.app.models.raw_events import RawEvent
from apps.api.app.services.kpi_service import upsert_rezdy_booking_from_raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
BATCH_SIZE = 50
SLEEP_SECONDS = 10


async def process_pending_batch(session_factory) -> int:
    """Processa um lote de raw_events pendentes. Retorna quantos foram processados."""
    async with session_factory() as session:
        result = await session.execute(
            select(RawEvent)
            .where(RawEvent.processing_status == "pending")
            .order_by(RawEvent.received_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        events = result.scalars().all()

        if not events:
            return 0

        for event in events:
            try:
                if event.source == "rezdy":
                    await upsert_rezdy_booking_from_raw(event.id, session)
                else:
                    logger.warning("Unknown source %s for event %s", event.source, event.id)
                    await session.execute(
                        update(RawEvent)
                        .where(RawEvent.id == event.id)
                        .values(processing_status="skipped")
                    )
            except Exception as exc:
                logger.error("Error processing event %s: %s", event.id, exc)
                await session.execute(
                    update(RawEvent)
                    .where(RawEvent.id == event.id)
                    .values(
                        processing_status="error",
                        error_message=str(exc)[:500],
                        processed_at=datetime.now(tz=timezone.utc),
                    )
                )

        await session.commit()
        return len(events)


async def run_transform_loop() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    logger.info("Transform worker started, polling every %ds", SLEEP_SECONDS)
    while True:
        try:
            processed = await process_pending_batch(SessionLocal)
            if processed:
                logger.info("Processed %d raw_events", processed)
            else:
                await asyncio.sleep(SLEEP_SECONDS)
        except Exception as exc:
            logger.exception("Transform loop error: %s", exc)
            await asyncio.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_transform_loop())
