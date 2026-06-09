import pytest
from datetime import date

from connectors.meta_ads.schemas import MetaInsightRow, MetaAction


def test_meta_insight_row_coerces_strings():
    row = MetaInsightRow(
        date_start="2026-06-01",
        date_stop="2026-06-01",
        account_id="act_123",
        impressions="10000",
        clicks="500",
        spend="150.25",
        ctr="5.0",
        cpc="0.30",
    )
    assert row.impressions == 10000.0
    assert row.clicks == 500.0
    assert row.spend == 150.25
    assert row.ctr == 5.0


def test_meta_insight_row_none_becomes_zero():
    row = MetaInsightRow(
        date_start=date(2026, 6, 1),
        date_stop=date(2026, 6, 1),
        account_id="act_123",
        impressions=None,
        clicks=None,
        spend=None,
    )
    assert row.impressions == 0.0
    assert row.clicks == 0.0
    assert row.spend == 0.0


def test_meta_insight_row_extracts_purchases():
    row = MetaInsightRow(
        date_start=date(2026, 6, 1),
        date_stop=date(2026, 6, 1),
        account_id="act_123",
        actions=[
            MetaAction(action_type="purchase", value="3"),
            MetaAction(action_type="link_click", value="100"),
        ],
        action_values=[
            MetaAction(action_type="purchase", value="4500.00"),
        ],
    )
    assert row.purchases == 3.0
    assert row.conversion_value == 4500.0


def test_meta_insight_row_extracts_leads():
    row = MetaInsightRow(
        date_start=date(2026, 6, 1),
        date_stop=date(2026, 6, 1),
        account_id="act_123",
        actions=[MetaAction(action_type="lead", value="7")],
    )
    assert row.leads == 7.0


def test_meta_insight_row_conversions_falls_back_to_leads():
    row = MetaInsightRow(
        date_start=date(2026, 6, 1),
        date_stop=date(2026, 6, 1),
        account_id="act_123",
        actions=[MetaAction(action_type="lead", value="5")],
    )
    assert row.conversions == 5.0
