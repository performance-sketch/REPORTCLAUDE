"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── raw_events ────────────────────────────────────────────────────────────
    op.create_table(
        "raw_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("processing_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text),
        sa.UniqueConstraint("source", "event_type", "payload_hash", name="uq_raw_events_dedup"),
    )
    op.create_index("ix_raw_events_source", "raw_events", ["source"])
    op.create_index("ix_raw_events_status", "raw_events", ["processing_status"])

    # ── dim_platform_accounts ─────────────────────────────────────────────────
    op.create_table(
        "dim_platform_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("account_name", sa.String(255)),
        sa.Column("currency", sa.String(10)),
        sa.Column("timezone", sa.String(100)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("platform", "account_id", name="uq_dim_platform_account"),
    )

    # ── dim_meta_campaigns ────────────────────────────────────────────────────
    op.create_table(
        "dim_meta_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("campaign_id", sa.String(100), nullable=False),
        sa.Column("campaign_name", sa.String(500)),
        sa.Column("objective", sa.String(100)),
        sa.Column("status", sa.String(50)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("account_id", "campaign_id", name="uq_dim_meta_campaign"),
    )
    op.create_index("ix_dim_meta_campaigns_account_id", "dim_meta_campaigns", ["account_id"])

    # ── dim_meta_adsets ───────────────────────────────────────────────────────
    op.create_table(
        "dim_meta_adsets",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("campaign_id", sa.String(100)),
        sa.Column("adset_id", sa.String(100), nullable=False),
        sa.Column("adset_name", sa.String(500)),
        sa.Column("status", sa.String(50)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("account_id", "adset_id", name="uq_dim_meta_adset"),
    )

    # ── dim_meta_ads ──────────────────────────────────────────────────────────
    op.create_table(
        "dim_meta_ads",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("adset_id", sa.String(100)),
        sa.Column("ad_id", sa.String(100), nullable=False),
        sa.Column("ad_name", sa.String(500)),
        sa.Column("status", sa.String(50)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("account_id", "ad_id", name="uq_dim_meta_ad"),
    )

    # ── dim_rezdy_products ────────────────────────────────────────────────────
    op.create_table(
        "dim_rezdy_products",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("product_code", sa.String(100), nullable=False, unique=True),
        sa.Column("product_name", sa.String(500)),
        sa.Column("product_type", sa.String(100)),
        sa.Column("duration_minutes", sa.Integer),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── dim_rezdy_customers ───────────────────────────────────────────────────
    op.create_table(
        "dim_rezdy_customers",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("customer_id", sa.String(100)),
        sa.Column("email", sa.String(255)),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("phone", sa.String(50)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_dim_rezdy_customer_email"),
    )
    op.create_index("ix_dim_rezdy_customers_email", "dim_rezdy_customers", ["email"])

    # ── fact_meta_ad_performance_daily ────────────────────────────────────────
    op.create_table(
        "fact_meta_ad_performance_daily",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("account_name", sa.String(255)),
        sa.Column("campaign_id", sa.String(100)),
        sa.Column("campaign_name", sa.String(500)),
        sa.Column("adset_id", sa.String(100)),
        sa.Column("adset_name", sa.String(500)),
        sa.Column("ad_id", sa.String(100)),
        sa.Column("ad_name", sa.String(500)),
        sa.Column("impressions", sa.Numeric, server_default="0"),
        sa.Column("reach", sa.Numeric, server_default="0"),
        sa.Column("frequency", sa.Numeric, server_default="0"),
        sa.Column("clicks", sa.Numeric, server_default="0"),
        sa.Column("link_clicks", sa.Numeric, server_default="0"),
        sa.Column("landing_page_views", sa.Numeric, server_default="0"),
        sa.Column("spend", sa.Numeric, server_default="0"),
        sa.Column("leads", sa.Numeric, server_default="0"),
        sa.Column("purchases", sa.Numeric, server_default="0"),
        sa.Column("conversions", sa.Numeric, server_default="0"),
        sa.Column("conversion_value", sa.Numeric, server_default="0"),
        sa.Column("cpc", sa.Numeric),
        sa.Column("cpm", sa.Numeric),
        sa.Column("ctr", sa.Numeric),
        sa.Column("currency", sa.String(10)),
        sa.Column("attribution_window", sa.String(50), server_default=""),
        sa.Column("raw_payload", postgresql.JSONB),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("date", "account_id", "campaign_id", "adset_id", "ad_id", "attribution_window", name="uq_meta_perf_daily"),
    )
    op.create_index("ix_meta_perf_date", "fact_meta_ad_performance_daily", ["date"])
    op.create_index("ix_meta_perf_account", "fact_meta_ad_performance_daily", ["account_id"])
    op.create_index("ix_meta_perf_campaign", "fact_meta_ad_performance_daily", ["campaign_id"])

    # ── fact_rezdy_bookings ───────────────────────────────────────────────────
    op.create_table(
        "fact_rezdy_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("order_number", sa.String(100), unique=True, nullable=False),
        sa.Column("booking_id", sa.String(100)),
        sa.Column("order_status", sa.String(50)),
        sa.Column("product_code", sa.String(100)),
        sa.Column("product_name", sa.String(500)),
        sa.Column("customer_id", sa.String(100)),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("customer_email", sa.String(255)),
        sa.Column("customer_phone", sa.String(50)),
        sa.Column("booking_created_at", sa.DateTime(timezone=True)),
        sa.Column("booking_updated_at", sa.DateTime(timezone=True)),
        sa.Column("session_start_at", sa.DateTime(timezone=True)),
        sa.Column("session_end_at", sa.DateTime(timezone=True)),
        sa.Column("quantity", sa.Numeric, server_default="0"),
        sa.Column("gross_revenue", sa.Numeric, server_default="0"),
        sa.Column("net_revenue", sa.Numeric, server_default="0"),
        sa.Column("commission", sa.Numeric, server_default="0"),
        sa.Column("payment_status", sa.String(50)),
        sa.Column("source_channel", sa.String(100)),
        sa.Column("campaign_id", sa.String(100)),
        sa.Column("campaign_name", sa.String(500)),
        sa.Column("utm_source", sa.String(255)),
        sa.Column("utm_medium", sa.String(255)),
        sa.Column("utm_campaign", sa.String(255)),
        sa.Column("utm_content", sa.String(255)),
        sa.Column("utm_term", sa.String(255)),
        sa.Column("raw_event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("raw_events.id")),
        sa.Column("raw_payload", postgresql.JSONB),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_rezdy_bookings_created", "fact_rezdy_bookings", ["booking_created_at"])
    op.create_index("ix_rezdy_bookings_status", "fact_rezdy_bookings", ["order_status"])
    op.create_index("ix_rezdy_bookings_product", "fact_rezdy_bookings", ["product_code"])

    # ── fact_funnel_touchpoints ───────────────────────────────────────────────
    op.create_table(
        "fact_funnel_touchpoints",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("booking_id", sa.String(100)),
        sa.Column("order_number", sa.String(100)),
        sa.Column("booking_created_at", sa.DateTime(timezone=True)),
        sa.Column("revenue", sa.Numeric, server_default="0"),
        sa.Column("platform", sa.String(50), server_default="meta_ads"),
        sa.Column("account_id", sa.String(100)),
        sa.Column("campaign_id", sa.String(100)),
        sa.Column("campaign_name", sa.String(500)),
        sa.Column("adset_id", sa.String(100)),
        sa.Column("adset_name", sa.String(500)),
        sa.Column("ad_id", sa.String(100)),
        sa.Column("ad_name", sa.String(500)),
        sa.Column("utm_source", sa.String(255)),
        sa.Column("utm_medium", sa.String(255)),
        sa.Column("utm_campaign", sa.String(255)),
        sa.Column("utm_content", sa.String(255)),
        sa.Column("utm_term", sa.String(255)),
        sa.Column("attribution_method", sa.String(50)),
        sa.Column("attribution_confidence", sa.String(20)),
        sa.Column("attribution_window_days", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_funnel_order_number", "fact_funnel_touchpoints", ["order_number"])
    op.create_index("ix_funnel_campaign", "fact_funnel_touchpoints", ["campaign_id"])

    # ── fact_sync_health ──────────────────────────────────────────────────────
    op.create_table(
        "fact_sync_health",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("sync_type", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("records_processed", sa.Integer, server_default="0"),
        sa.Column("records_failed", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("metadata", postgresql.JSONB),
    )
    op.create_index("ix_sync_health_source", "fact_sync_health", ["source"])


def downgrade() -> None:
    for table in [
        "fact_sync_health", "fact_funnel_touchpoints",
        "fact_rezdy_bookings", "fact_meta_ad_performance_daily",
        "dim_rezdy_customers", "dim_rezdy_products",
        "dim_meta_ads", "dim_meta_adsets", "dim_meta_campaigns",
        "dim_platform_accounts", "raw_events",
    ]:
        op.drop_table(table)
