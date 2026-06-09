from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.kpi_schemas import (
    BookingsKPI,
    FunnelKPI,
    MetaAdsKPI,
    OverviewKPI,
    SyncHealthResponse,
)
from ..services.kpi_service import KPIService

router = APIRouter(tags=["kpis"])


def _date_params(
    date_start: date = Query(default=None, description="YYYY-MM-DD"),
    date_end: date = Query(default=None, description="YYYY-MM-DD"),
) -> tuple[date | None, date | None]:
    return date_start, date_end


@router.get("/overview", response_model=OverviewKPI)
async def kpi_overview(
    dates: Annotated[tuple, Depends(_date_params)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = KPIService(db)
    return await svc.get_overview(*dates)


@router.get("/meta-ads", response_model=MetaAdsKPI)
async def kpi_meta_ads(
    dates: Annotated[tuple, Depends(_date_params)],
    account_id: str | None = Query(default=None),
    campaign_id: str | None = Query(default=None),
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = KPIService(db)
    return await svc.get_meta_ads(*dates, account_id=account_id, campaign_id=campaign_id)


@router.get("/bookings", response_model=BookingsKPI)
async def kpi_bookings(
    dates: Annotated[tuple, Depends(_date_params)],
    product_code: str | None = Query(default=None),
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = KPIService(db)
    return await svc.get_bookings(*dates, product_code=product_code)


@router.get("/funnel", response_model=FunnelKPI)
async def kpi_funnel(
    dates: Annotated[tuple, Depends(_date_params)],
    campaign_id: str | None = Query(default=None),
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = KPIService(db)
    return await svc.get_funnel(*dates, campaign_id=campaign_id)


@router.get("/sync-health", response_model=SyncHealthResponse)
async def sync_health(db: Annotated[AsyncSession, Depends(get_db)]):
    svc = KPIService(db)
    return await svc.get_sync_health()
