from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MetaAction(BaseModel):
    action_type: str
    value: str = "0"

    @property
    def float_value(self) -> float:
        return float(self.value)


class MetaInsightRow(BaseModel):
    date_start: date
    date_stop: date
    account_id: str
    account_name: str | None = None
    campaign_id: str | None = None
    campaign_name: str | None = None
    adset_id: str | None = None
    adset_name: str | None = None
    ad_id: str | None = None
    ad_name: str | None = None

    impressions: float = 0
    reach: float = 0
    frequency: float = 0
    clicks: float = 0
    inline_link_clicks: float = 0
    landing_page_views: float = 0
    spend: float = 0
    cpc: float | None = None
    cpm: float | None = None
    ctr: float | None = None

    actions: list[MetaAction] = Field(default_factory=list)
    action_values: list[MetaAction] = Field(default_factory=list)

    @field_validator("impressions", "reach", "clicks", "inline_link_clicks",
                     "landing_page_views", "spend", "frequency", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        return float(v)

    @field_validator("cpc", "cpm", "ctr", mode="before")
    @classmethod
    def coerce_nullable_numeric(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        return float(v)

    def get_action(self, *action_types: str) -> float:
        for a in self.actions:
            if a.action_type in action_types:
                return a.float_value
        return 0.0

    def get_action_value(self, *action_types: str) -> float:
        for a in self.action_values:
            if a.action_type in action_types:
                return a.float_value
        return 0.0

    @property
    def leads(self) -> float:
        return self.get_action("lead", "offsite_conversion.fb_pixel_lead")

    @property
    def purchases(self) -> float:
        return self.get_action(
            "purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"
        )

    @property
    def conversion_value(self) -> float:
        return self.get_action_value(
            "purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"
        )

    @property
    def conversions(self) -> float:
        return self.purchases or self.leads


class MetaInsightPage(BaseModel):
    data: list[MetaInsightRow] = Field(default_factory=list)
    paging: dict[str, Any] | None = None

    @property
    def next_cursor(self) -> str | None:
        if self.paging and "cursors" in self.paging:
            return self.paging["cursors"].get("after")
        return None

    @property
    def next_url(self) -> str | None:
        if self.paging:
            return self.paging.get("next")
        return None
