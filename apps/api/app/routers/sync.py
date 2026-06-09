from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sync"])
settings = get_settings()


def _require_sync_secret(x_sync_secret: Annotated[str | None, Header()] = None) -> None:
    if x_sync_secret != settings.sync_trigger_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid sync secret")


class SyncRequest(BaseModel):
    lookback_days: int = 3


@router.post("/meta-ads", dependencies=[Depends(_require_sync_secret)])
async def trigger_meta_ads_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from workers.meta_ads_worker import run_meta_ads_sync
    background_tasks.add_task(run_meta_ads_sync, body.lookback_days)
    logger.info("Meta Ads sync triggered lookback_days=%d", body.lookback_days)
    return {"triggered": True, "lookback_days": body.lookback_days}


@router.post("/rezdy", dependencies=[Depends(_require_sync_secret)])
async def trigger_rezdy_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from workers.rezdy_reconciliation_worker import run_rezdy_reconciliation
    background_tasks.add_task(run_rezdy_reconciliation, body.lookback_days)
    logger.info("Rezdy reconciliation triggered lookback_days=%d", body.lookback_days)
    return {"triggered": True, "lookback_days": body.lookback_days}
