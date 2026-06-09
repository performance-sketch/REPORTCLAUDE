from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ....connectors.rezdy.webhooks import compute_payload_hash, parse_webhook
from ..config import get_settings
from ..database import get_db
from ..models.raw_events import RawEvent

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])
settings = get_settings()


async def _process_rezdy_event(raw_event_id: str, db: AsyncSession) -> None:
    """Processamento assíncrono após resposta 202. Popula fact_rezdy_bookings."""
    from ..services.kpi_service import upsert_rezdy_booking_from_raw
    try:
        await upsert_rezdy_booking_from_raw(raw_event_id, db)
    except Exception as exc:
        logger.error("Failed to process raw_event %s: %s", raw_event_id, exc)
        from sqlalchemy import update
        await db.execute(
            update(RawEvent)
            .where(RawEvent.id == raw_event_id)
            .values(processing_status="error", error_message=str(exc)[:500])
        )
        await db.commit()


@router.post("/rezdy", status_code=status.HTTP_202_ACCEPTED)
async def rezdy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_rezdy_signature: Annotated[str | None, Header()] = None,
):
    body = await request.body()

    try:
        payload_obj = parse_webhook(
            body,
            secret=settings.rezdy_webhook_secret or None,
            signature=x_rezdy_signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to parse Rezdy webhook: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid payload")

    import json
    raw_dict = json.loads(body)
    event_type = payload_obj.event or "unknown"
    external_id = payload_obj.effective_order_number
    payload_hash = compute_payload_hash("rezdy", event_type, raw_dict)

    stmt = (
        insert(RawEvent)
        .values(
            source="rezdy",
            event_type=event_type,
            external_id=external_id,
            payload=raw_dict,
            payload_hash=payload_hash,
            processing_status="pending",
        )
        .on_conflict_do_nothing(constraint="uq_raw_events_dedup")
        .returning(RawEvent.id)
    )
    result = await db.execute(stmt)
    await db.commit()

    row = result.fetchone()
    if row:
        background_tasks.add_task(_process_rezdy_event, row[0], db)
        logger.info("Rezdy webhook queued event_type=%s order=%s", event_type, external_id)
    else:
        logger.info("Rezdy webhook duplicate skipped event_type=%s order=%s", event_type, external_id)

    return {"accepted": True}
