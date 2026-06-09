from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, computed_field


class CampaignRow(BaseModel):
    campaign_id: str | None
    campaign_name: str | None
    spend: float
    impressions: float
    clicks: float
    ctr: float | None
    cpc: float | None
    cpm: float | None
    leads: float
    purchases: float
    conversion_value: float
    roas: float | None


class ProductRow(BaseModel):
    product_code: str | None
    product_name: str | None
    bookings_confirmed: int
    revenue: float
    avg_ticket: float | None


class DailyMetaRow(BaseModel):
    date: date
    spend: float
    impressions: float
    clicks: float
    leads: float
    purchases: float
    conversion_value: float


class DailyBookingRow(BaseModel):
    date: date
    bookings_created: int
    bookings_confirmed: int
    bookings_cancelled: int
    gross_revenue: float


class OverviewKPI(BaseModel):
    date_start: date | None
    date_end: date | None
    meta_spend: float
    confirmed_revenue: float
    roas_real: float | None
    bookings_created: int
    bookings_confirmed: int
    bookings_cancelled: int
    cancellation_rate: float | None
    cac: float | None
    avg_ticket: float | None
    clicks: float
    ctr: float | None
    cpc: float | None
    cpm: float | None
    click_to_booking_rate: float | None
    revenue_per_click: float | None
    daily_meta: list[DailyMetaRow]
    daily_bookings: list[DailyBookingRow]
    top_campaigns: list[CampaignRow]
    top_products: list[ProductRow]


class MetaAdsKPI(BaseModel):
    date_start: date | None
    date_end: date | None
    spend: float
    impressions: float
    reach: float
    frequency: float | None
    clicks: float
    link_clicks: float
    landing_page_views: float
    ctr: float | None
    cpc: float | None
    cpm: float | None
    leads: float
    purchases: float
    conversion_value: float
    cpa: float | None
    roas_meta: float | None
    campaigns: list[CampaignRow]


class BookingsKPI(BaseModel):
    date_start: date | None
    date_end: date | None
    bookings_created: int
    bookings_confirmed: int
    bookings_cancelled: int
    cancellation_rate: float | None
    gross_revenue: float
    net_revenue: float
    avg_ticket: float | None
    total_pax: int
    daily: list[DailyBookingRow]
    by_product: list[ProductRow]
    by_status: list[dict]


class FunnelKPI(BaseModel):
    date_start: date | None
    date_end: date | None
    impressions: float
    clicks: float
    landing_page_views: float
    bookings_created: int
    bookings_confirmed: int
    confirmed_revenue: float
    imp_to_click_rate: float | None
    click_to_booking_rate: float | None
    booking_to_confirmed_rate: float | None
    cost_per_booking_created: float | None
    cost_per_booking_confirmed: float | None
    revenue_per_click: float | None
    roas_real: float | None
    by_campaign: list[CampaignRow]


class SyncRecord(BaseModel):
    source: str
    sync_type: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    records_processed: int
    records_failed: int
    error_message: str | None


class SyncHealthResponse(BaseModel):
    pending_events: int
    error_events: int
    recent_syncs: list[SyncRecord]
