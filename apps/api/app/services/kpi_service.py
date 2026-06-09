from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.facts import FactMetaAdPerformanceDaily, FactRezdyBooking, FactSyncHealth
from ..models.raw_events import RawEvent
from ..schemas.kpi_schemas import (
    BookingsKPI,
    CampaignRow,
    DailyBookingRow,
    DailyMetaRow,
    FunnelKPI,
    MetaAdsKPI,
    OverviewKPI,
    ProductRow,
    SyncHealthResponse,
    SyncRecord,
)

logger = logging.getLogger(__name__)


def _safe_div(num: float, den: float) -> float | None:
    return round(num / den, 4) if den else None


def _default_dates(start: date | None, end: date | None) -> tuple[date, date]:
    today = date.today()
    return start or (today - timedelta(days=30)), end or today


class KPIService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_overview(self, date_start: date | None, date_end: date | None) -> OverviewKPI:
        ds, de = _default_dates(date_start, date_end)

        meta = await self._meta_aggregates(ds, de)
        bookings = await self._booking_aggregates(ds, de)
        daily_meta = await self._daily_meta(ds, de)
        daily_bookings = await self._daily_bookings(ds, de)
        top_campaigns = await self._top_campaigns(ds, de, limit=10)
        top_products = await self._top_products(ds, de, limit=10)

        spend = meta.get("spend", 0) or 0
        confirmed_rev = bookings.get("confirmed_revenue", 0) or 0
        confirmed_cnt = bookings.get("confirmed_count", 0) or 0
        created_cnt = bookings.get("created_count", 0) or 0
        cancelled_cnt = bookings.get("cancelled_count", 0) or 0
        clicks = meta.get("clicks", 0) or 0

        return OverviewKPI(
            date_start=ds,
            date_end=de,
            meta_spend=round(spend, 2),
            confirmed_revenue=round(confirmed_rev, 2),
            roas_real=_safe_div(confirmed_rev, spend),
            bookings_created=created_cnt,
            bookings_confirmed=confirmed_cnt,
            bookings_cancelled=cancelled_cnt,
            cancellation_rate=_safe_div(cancelled_cnt, created_cnt),
            cac=_safe_div(spend, confirmed_cnt),
            avg_ticket=_safe_div(confirmed_rev, confirmed_cnt),
            clicks=clicks,
            ctr=_safe_div(clicks, meta.get("impressions", 0) or 0),
            cpc=_safe_div(spend, clicks),
            cpm=_safe_div(spend * 1000, meta.get("impressions", 0) or 0),
            click_to_booking_rate=_safe_div(created_cnt, clicks),
            revenue_per_click=_safe_div(confirmed_rev, clicks),
            daily_meta=daily_meta,
            daily_bookings=daily_bookings,
            top_campaigns=top_campaigns,
            top_products=top_products,
        )

    async def get_meta_ads(
        self,
        date_start: date | None,
        date_end: date | None,
        account_id: str | None = None,
        campaign_id: str | None = None,
    ) -> MetaAdsKPI:
        ds, de = _default_dates(date_start, date_end)
        meta = await self._meta_aggregates(ds, de, account_id=account_id, campaign_id=campaign_id)
        campaigns = await self._top_campaigns(ds, de, account_id=account_id, limit=50)

        spend = meta.get("spend", 0) or 0
        clicks = meta.get("clicks", 0) or 0
        impressions = meta.get("impressions", 0) or 0
        purchases = meta.get("purchases", 0) or 0
        conv_value = meta.get("conversion_value", 0) or 0

        return MetaAdsKPI(
            date_start=ds,
            date_end=de,
            spend=round(spend, 2),
            impressions=impressions,
            reach=meta.get("reach", 0) or 0,
            frequency=_safe_div(impressions, meta.get("reach", 0) or 0),
            clicks=clicks,
            link_clicks=meta.get("link_clicks", 0) or 0,
            landing_page_views=meta.get("landing_page_views", 0) or 0,
            ctr=_safe_div(clicks, impressions),
            cpc=_safe_div(spend, clicks),
            cpm=_safe_div(spend * 1000, impressions),
            leads=meta.get("leads", 0) or 0,
            purchases=purchases,
            conversion_value=round(conv_value, 2),
            cpa=_safe_div(spend, purchases),
            roas_meta=_safe_div(conv_value, spend),
            campaigns=campaigns,
        )

    async def get_bookings(
        self, date_start: date | None, date_end: date | None, product_code: str | None = None
    ) -> BookingsKPI:
        ds, de = _default_dates(date_start, date_end)
        agg = await self._booking_aggregates(ds, de, product_code=product_code)
        daily = await self._daily_bookings(ds, de)
        by_product = await self._top_products(ds, de)
        by_status = await self._bookings_by_status(ds, de)

        confirmed_rev = agg.get("confirmed_revenue", 0) or 0
        confirmed_cnt = agg.get("confirmed_count", 0) or 0
        created_cnt = agg.get("created_count", 0) or 0
        cancelled_cnt = agg.get("cancelled_count", 0) or 0

        return BookingsKPI(
            date_start=ds,
            date_end=de,
            bookings_created=created_cnt,
            bookings_confirmed=confirmed_cnt,
            bookings_cancelled=cancelled_cnt,
            cancellation_rate=_safe_div(cancelled_cnt, created_cnt),
            gross_revenue=round(agg.get("gross_revenue", 0) or 0, 2),
            net_revenue=round(agg.get("net_revenue", 0) or 0, 2),
            avg_ticket=_safe_div(confirmed_rev, confirmed_cnt),
            total_pax=agg.get("total_pax", 0) or 0,
            daily=daily,
            by_product=by_product,
            by_status=by_status,
        )

    async def get_funnel(
        self, date_start: date | None, date_end: date | None, campaign_id: str | None = None
    ) -> FunnelKPI:
        ds, de = _default_dates(date_start, date_end)
        meta = await self._meta_aggregates(ds, de, campaign_id=campaign_id)
        bookings = await self._booking_aggregates(ds, de)
        campaigns = await self._top_campaigns(ds, de)

        spend = meta.get("spend", 0) or 0
        impressions = meta.get("impressions", 0) or 0
        clicks = meta.get("clicks", 0) or 0
        lpv = meta.get("landing_page_views", 0) or 0
        created = bookings.get("created_count", 0) or 0
        confirmed = bookings.get("confirmed_count", 0) or 0
        confirmed_rev = bookings.get("confirmed_revenue", 0) or 0

        return FunnelKPI(
            date_start=ds,
            date_end=de,
            impressions=impressions,
            clicks=clicks,
            landing_page_views=lpv,
            bookings_created=created,
            bookings_confirmed=confirmed,
            confirmed_revenue=round(confirmed_rev, 2),
            imp_to_click_rate=_safe_div(clicks, impressions),
            click_to_booking_rate=_safe_div(created, clicks),
            booking_to_confirmed_rate=_safe_div(confirmed, created),
            cost_per_booking_created=_safe_div(spend, created),
            cost_per_booking_confirmed=_safe_div(spend, confirmed),
            revenue_per_click=_safe_div(confirmed_rev, clicks),
            roas_real=_safe_div(confirmed_rev, spend),
            by_campaign=campaigns,
        )

    async def get_sync_health(self) -> SyncHealthResponse:
        pending = await self.db.scalar(
            select(func.count()).where(RawEvent.processing_status == "pending")
        )
        errors = await self.db.scalar(
            select(func.count()).where(RawEvent.processing_status == "error")
        )
        result = await self.db.execute(
            select(FactSyncHealth)
            .order_by(FactSyncHealth.started_at.desc())
            .limit(20)
        )
        syncs = [
            SyncRecord(
                source=r.source,
                sync_type=r.sync_type,
                started_at=r.started_at,
                finished_at=r.finished_at,
                status=r.status,
                records_processed=r.records_processed,
                records_failed=r.records_failed,
                error_message=r.error_message,
            )
            for r in result.scalars()
        ]
        return SyncHealthResponse(
            pending_events=pending or 0,
            error_events=errors or 0,
            recent_syncs=syncs,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _meta_aggregates(
        self,
        ds: date,
        de: date,
        account_id: str | None = None,
        campaign_id: str | None = None,
    ) -> dict[str, Any]:
        q = (
            select(
                func.sum(FactMetaAdPerformanceDaily.spend).label("spend"),
                func.sum(FactMetaAdPerformanceDaily.impressions).label("impressions"),
                func.sum(FactMetaAdPerformanceDaily.reach).label("reach"),
                func.sum(FactMetaAdPerformanceDaily.clicks).label("clicks"),
                func.sum(FactMetaAdPerformanceDaily.link_clicks).label("link_clicks"),
                func.sum(FactMetaAdPerformanceDaily.landing_page_views).label("landing_page_views"),
                func.sum(FactMetaAdPerformanceDaily.leads).label("leads"),
                func.sum(FactMetaAdPerformanceDaily.purchases).label("purchases"),
                func.sum(FactMetaAdPerformanceDaily.conversion_value).label("conversion_value"),
            )
            .where(FactMetaAdPerformanceDaily.date.between(ds, de))
        )
        if account_id:
            q = q.where(FactMetaAdPerformanceDaily.account_id == account_id)
        if campaign_id:
            q = q.where(FactMetaAdPerformanceDaily.campaign_id == campaign_id)

        row = (await self.db.execute(q)).fetchone()
        return dict(row._mapping) if row else {}

    async def _booking_aggregates(
        self, ds: date, de: date, product_code: str | None = None
    ) -> dict[str, Any]:
        base = select(FactRezdyBooking).where(
            func.date(FactRezdyBooking.booking_created_at).between(ds, de)
        )
        if product_code:
            base = base.where(FactRezdyBooking.product_code == product_code)

        result = await self.db.execute(base)
        rows = result.scalars().all()

        confirmed = [r for r in rows if r.order_status == "CONFIRMED"]
        cancelled = [r for r in rows if r.order_status in ("CANCELLED", "ABANDONED_CART")]

        return {
            "created_count": len(rows),
            "confirmed_count": len(confirmed),
            "cancelled_count": len(cancelled),
            "gross_revenue": sum(r.gross_revenue for r in rows),
            "net_revenue": sum(r.net_revenue for r in rows),
            "confirmed_revenue": sum(r.gross_revenue for r in confirmed),
            "total_pax": int(sum(r.quantity for r in rows)),
        }

    async def _daily_meta(self, ds: date, de: date) -> list[DailyMetaRow]:
        q = (
            select(
                FactMetaAdPerformanceDaily.date,
                func.sum(FactMetaAdPerformanceDaily.spend).label("spend"),
                func.sum(FactMetaAdPerformanceDaily.impressions).label("impressions"),
                func.sum(FactMetaAdPerformanceDaily.clicks).label("clicks"),
                func.sum(FactMetaAdPerformanceDaily.leads).label("leads"),
                func.sum(FactMetaAdPerformanceDaily.purchases).label("purchases"),
                func.sum(FactMetaAdPerformanceDaily.conversion_value).label("conversion_value"),
            )
            .where(FactMetaAdPerformanceDaily.date.between(ds, de))
            .group_by(FactMetaAdPerformanceDaily.date)
            .order_by(FactMetaAdPerformanceDaily.date)
        )
        result = await self.db.execute(q)
        return [DailyMetaRow(**dict(r._mapping)) for r in result]

    async def _daily_bookings(self, ds: date, de: date) -> list[DailyBookingRow]:
        q = text("""
            SELECT
                date(booking_created_at) AS date,
                COUNT(*) AS bookings_created,
                COUNT(*) FILTER (WHERE order_status = 'CONFIRMED') AS bookings_confirmed,
                COUNT(*) FILTER (WHERE order_status IN ('CANCELLED','ABANDONED_CART')) AS bookings_cancelled,
                COALESCE(SUM(gross_revenue), 0) AS gross_revenue
            FROM fact_rezdy_bookings
            WHERE date(booking_created_at) BETWEEN :ds AND :de
            GROUP BY 1
            ORDER BY 1
        """)
        result = await self.db.execute(q, {"ds": ds, "de": de})
        return [DailyBookingRow(**dict(r._mapping)) for r in result]

    async def _top_campaigns(
        self, ds: date, de: date, account_id: str | None = None, limit: int = 10
    ) -> list[CampaignRow]:
        q = (
            select(
                FactMetaAdPerformanceDaily.campaign_id,
                FactMetaAdPerformanceDaily.campaign_name,
                func.sum(FactMetaAdPerformanceDaily.spend).label("spend"),
                func.sum(FactMetaAdPerformanceDaily.impressions).label("impressions"),
                func.sum(FactMetaAdPerformanceDaily.clicks).label("clicks"),
                func.sum(FactMetaAdPerformanceDaily.leads).label("leads"),
                func.sum(FactMetaAdPerformanceDaily.purchases).label("purchases"),
                func.sum(FactMetaAdPerformanceDaily.conversion_value).label("conversion_value"),
            )
            .where(FactMetaAdPerformanceDaily.date.between(ds, de))
            .group_by(
                FactMetaAdPerformanceDaily.campaign_id,
                FactMetaAdPerformanceDaily.campaign_name,
            )
            .order_by(func.sum(FactMetaAdPerformanceDaily.spend).desc())
            .limit(limit)
        )
        if account_id:
            q = q.where(FactMetaAdPerformanceDaily.account_id == account_id)

        result = await self.db.execute(q)
        rows = []
        for r in result:
            d = dict(r._mapping)
            spend = float(d.get("spend") or 0)
            clicks = float(d.get("clicks") or 0)
            impressions = float(d.get("impressions") or 0)
            conv_value = float(d.get("conversion_value") or 0)
            rows.append(CampaignRow(
                campaign_id=d.get("campaign_id"),
                campaign_name=d.get("campaign_name"),
                spend=round(spend, 2),
                impressions=impressions,
                clicks=clicks,
                ctr=_safe_div(clicks, impressions),
                cpc=_safe_div(spend, clicks),
                cpm=_safe_div(spend * 1000, impressions),
                leads=float(d.get("leads") or 0),
                purchases=float(d.get("purchases") or 0),
                conversion_value=round(conv_value, 2),
                roas=_safe_div(conv_value, spend),
            ))
        return rows

    async def _top_products(self, ds: date, de: date, limit: int = 10) -> list[ProductRow]:
        q = text("""
            SELECT
                product_code,
                product_name,
                COUNT(*) FILTER (WHERE order_status = 'CONFIRMED') AS bookings_confirmed,
                COALESCE(SUM(gross_revenue) FILTER (WHERE order_status = 'CONFIRMED'), 0) AS revenue
            FROM fact_rezdy_bookings
            WHERE date(booking_created_at) BETWEEN :ds AND :de
            GROUP BY product_code, product_name
            ORDER BY revenue DESC
            LIMIT :limit
        """)
        result = await self.db.execute(q, {"ds": ds, "de": de, "limit": limit})
        rows = []
        for r in result:
            d = dict(r._mapping)
            cnt = int(d.get("bookings_confirmed") or 0)
            rev = float(d.get("revenue") or 0)
            rows.append(ProductRow(
                product_code=d.get("product_code"),
                product_name=d.get("product_name"),
                bookings_confirmed=cnt,
                revenue=round(rev, 2),
                avg_ticket=_safe_div(rev, cnt),
            ))
        return rows

    async def _bookings_by_status(self, ds: date, de: date) -> list[dict]:
        q = text("""
            SELECT order_status, COUNT(*) AS count, COALESCE(SUM(gross_revenue), 0) AS revenue
            FROM fact_rezdy_bookings
            WHERE date(booking_created_at) BETWEEN :ds AND :de
            GROUP BY order_status
            ORDER BY count DESC
        """)
        result = await self.db.execute(q, {"ds": ds, "de": de})
        return [dict(r._mapping) for r in result]

    async def upsert_rezdy_booking_from_raw(self, raw_event_id: str, db: AsyncSession) -> None:
        """Transforma um RawEvent pendente em FactRezdyBooking."""
        from sqlalchemy import update
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        raw = await db.get(RawEvent, raw_event_id)
        if not raw:
            return

        from connectors.rezdy.schemas import RezdyBooking
        try:
            booking = RezdyBooking.model_validate(raw.payload.get("booking") or raw.payload)
        except Exception as exc:
            await db.execute(
                update(RawEvent).where(RawEvent.id == raw_event_id).values(
                    processing_status="error", error_message=str(exc)[:500]
                )
            )
            await db.commit()
            return

        values = dict(
            order_number=booking.orderNumber,
            order_status=booking.status,
            product_code=booking.product_code,
            product_name=booking.product_name,
            customer_id=booking.customer.id if booking.customer else None,
            customer_name=booking.customer.full_name if booking.customer else None,
            customer_email=booking.customer.email if booking.customer else None,
            customer_phone=booking.customer.phone if booking.customer else None,
            booking_created_at=booking.created_at,
            booking_updated_at=booking.updated_at,
            session_start_at=booking.primary_item.session_start if booking.primary_item else None,
            session_end_at=booking.primary_item.session_end if booking.primary_item else None,
            quantity=booking.total_pax,
            gross_revenue=booking.totalAmount,
            net_revenue=booking.totalAmount - booking.totalDue + booking.totalDue,
            payment_status=booking.paymentOption,
            source_channel=booking.source,
            utm_source=booking.get_utm("utm_source"),
            utm_medium=booking.get_utm("utm_medium"),
            utm_campaign=booking.get_utm("utm_campaign"),
            utm_content=booking.get_utm("utm_content"),
            utm_term=booking.get_utm("utm_term"),
            raw_event_id=raw_event_id,
            raw_payload=raw.payload,
        )

        stmt = (
            pg_insert(FactRezdyBooking)
            .values(**values)
            .on_conflict_do_update(index_elements=["order_number"], set_=values)
        )
        await db.execute(stmt)
        await db.execute(
            update(RawEvent).where(RawEvent.id == raw_event_id).values(
                processing_status="processed",
                processed_at=datetime.now(tz=timezone.utc),
            )
        )
        await db.commit()


async def upsert_rezdy_booking_from_raw(raw_event_id: str, db: AsyncSession) -> None:
    svc = KPIService(db)
    await svc.upsert_rezdy_booking_from_raw(raw_event_id, db)
