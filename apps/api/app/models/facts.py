from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class FactMetaAdPerformanceDaily(Base):
    __tablename__ = "fact_meta_ad_performance_daily"
    __table_args__ = (
        UniqueConstraint(
            "date", "account_id", "campaign_id", "adset_id", "ad_id", "attribution_window",
            name="uq_meta_perf_daily",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    account_name: Mapped[str | None] = mapped_column(String(255))
    campaign_id: Mapped[str | None] = mapped_column(String(100), index=True)
    campaign_name: Mapped[str | None] = mapped_column(String(500))
    adset_id: Mapped[str | None] = mapped_column(String(100))
    adset_name: Mapped[str | None] = mapped_column(String(500))
    ad_id: Mapped[str | None] = mapped_column(String(100))
    ad_name: Mapped[str | None] = mapped_column(String(500))

    impressions: Mapped[float] = mapped_column(Numeric, default=0)
    reach: Mapped[float] = mapped_column(Numeric, default=0)
    frequency: Mapped[float] = mapped_column(Numeric, default=0)
    clicks: Mapped[float] = mapped_column(Numeric, default=0)
    link_clicks: Mapped[float] = mapped_column(Numeric, default=0)
    landing_page_views: Mapped[float] = mapped_column(Numeric, default=0)
    spend: Mapped[float] = mapped_column(Numeric, default=0)
    leads: Mapped[float] = mapped_column(Numeric, default=0)
    purchases: Mapped[float] = mapped_column(Numeric, default=0)
    conversions: Mapped[float] = mapped_column(Numeric, default=0)
    conversion_value: Mapped[float] = mapped_column(Numeric, default=0)
    cpc: Mapped[float | None] = mapped_column(Numeric)
    cpm: Mapped[float | None] = mapped_column(Numeric)
    ctr: Mapped[float | None] = mapped_column(Numeric)
    currency: Mapped[str | None] = mapped_column(String(10))
    attribution_window: Mapped[str] = mapped_column(String(50), default="")
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class FactRezdyBooking(Base):
    __tablename__ = "fact_rezdy_bookings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    order_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    booking_id: Mapped[str | None] = mapped_column(String(100))
    order_status: Mapped[str | None] = mapped_column(String(50), index=True)
    product_code: Mapped[str | None] = mapped_column(String(100), index=True)
    product_name: Mapped[str | None] = mapped_column(String(500))
    customer_id: Mapped[str | None] = mapped_column(String(100))
    customer_name: Mapped[str | None] = mapped_column(String(255))
    customer_email: Mapped[str | None] = mapped_column(String(255))
    customer_phone: Mapped[str | None] = mapped_column(String(50))
    booking_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    booking_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quantity: Mapped[float] = mapped_column(Numeric, default=0)
    gross_revenue: Mapped[float] = mapped_column(Numeric, default=0)
    net_revenue: Mapped[float] = mapped_column(Numeric, default=0)
    commission: Mapped[float] = mapped_column(Numeric, default=0)
    payment_status: Mapped[str | None] = mapped_column(String(50))
    source_channel: Mapped[str | None] = mapped_column(String(100))
    campaign_id: Mapped[str | None] = mapped_column(String(100))
    campaign_name: Mapped[str | None] = mapped_column(String(500))
    utm_source: Mapped[str | None] = mapped_column(String(255))
    utm_medium: Mapped[str | None] = mapped_column(String(255))
    utm_campaign: Mapped[str | None] = mapped_column(String(255))
    utm_content: Mapped[str | None] = mapped_column(String(255))
    utm_term: Mapped[str | None] = mapped_column(String(255))
    raw_event_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("raw_events.id"))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class FactFunnelTouchpoint(Base):
    __tablename__ = "fact_funnel_touchpoints"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    booking_id: Mapped[str | None] = mapped_column(String(100))
    order_number: Mapped[str | None] = mapped_column(String(100), index=True)
    booking_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revenue: Mapped[float] = mapped_column(Numeric, default=0)
    platform: Mapped[str] = mapped_column(String(50), default="meta_ads")
    account_id: Mapped[str | None] = mapped_column(String(100))
    campaign_id: Mapped[str | None] = mapped_column(String(100), index=True)
    campaign_name: Mapped[str | None] = mapped_column(String(500))
    adset_id: Mapped[str | None] = mapped_column(String(100))
    adset_name: Mapped[str | None] = mapped_column(String(500))
    ad_id: Mapped[str | None] = mapped_column(String(100))
    ad_name: Mapped[str | None] = mapped_column(String(500))
    utm_source: Mapped[str | None] = mapped_column(String(255))
    utm_medium: Mapped[str | None] = mapped_column(String(255))
    utm_campaign: Mapped[str | None] = mapped_column(String(255))
    utm_content: Mapped[str | None] = mapped_column(String(255))
    utm_term: Mapped[str | None] = mapped_column(String(255))
    attribution_method: Mapped[str | None] = mapped_column(String(50))
    attribution_confidence: Mapped[str | None] = mapped_column(String(20))
    attribution_window_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class FactSyncHealth(Base):
    __tablename__ = "fact_sync_health"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict | None] = mapped_column(JSONB)
