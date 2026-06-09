from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class DimPlatformAccount(Base):
    __tablename__ = "dim_platform_accounts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str | None] = mapped_column(String(10))
    timezone: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (UniqueConstraint("platform", "account_id", name="uq_dim_platform_account"),)


class DimMetaCampaign(Base):
    __tablename__ = "dim_meta_campaigns"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_name: Mapped[str | None] = mapped_column(String(500))
    objective: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (UniqueConstraint("account_id", "campaign_id", name="uq_dim_meta_campaign"),)


class DimMetaAdset(Base):
    __tablename__ = "dim_meta_adsets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(100))
    adset_id: Mapped[str] = mapped_column(String(100), nullable=False)
    adset_name: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str | None] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (UniqueConstraint("account_id", "adset_id", name="uq_dim_meta_adset"),)


class DimMetaAd(Base):
    __tablename__ = "dim_meta_ads"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    adset_id: Mapped[str | None] = mapped_column(String(100))
    ad_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ad_name: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str | None] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (UniqueConstraint("account_id", "ad_id", name="uq_dim_meta_ad"),)


class DimRezdyProduct(Base):
    __tablename__ = "dim_rezdy_products"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    product_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    product_name: Mapped[str | None] = mapped_column(String(500))
    product_type: Mapped[str | None] = mapped_column(String(100))
    duration_minutes: Mapped[int | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class DimRezdyCustomer(Base):
    __tablename__ = "dim_rezdy_customers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    customer_id: Mapped[str | None] = mapped_column(String(100), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (UniqueConstraint("email", name="uq_dim_rezdy_customer_email"),)
