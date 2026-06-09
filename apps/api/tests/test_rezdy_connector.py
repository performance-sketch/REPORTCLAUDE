import pytest
from datetime import datetime

from connectors.rezdy.schemas import RezdyBooking, RezdyCustomer, RezdySessionItem, RezdyQuantity


def test_rezdy_booking_parses_minimal():
    b = RezdyBooking(orderNumber="VR001")
    assert b.orderNumber == "VR001"
    assert b.totalAmount == 0.0


def test_rezdy_booking_product_code():
    b = RezdyBooking(
        orderNumber="VR002",
        items=[RezdySessionItem(productCode="PROD01", productName="Doors Off 30min")],
    )
    assert b.product_code == "PROD01"
    assert b.product_name == "Doors Off 30min"


def test_rezdy_booking_total_pax():
    b = RezdyBooking(
        orderNumber="VR003",
        items=[
            RezdySessionItem(quantities=[RezdyQuantity(value=2), RezdyQuantity(value=1)])
        ],
    )
    assert b.total_pax == 3


def test_rezdy_customer_full_name():
    c = RezdyCustomer(firstName="Maria", lastName="Silva")
    assert c.full_name == "Maria Silva"


def test_rezdy_customer_full_name_partial():
    c = RezdyCustomer(firstName="Maria")
    assert c.full_name == "Maria"


def test_rezdy_booking_created_at_parses():
    b = RezdyBooking(orderNumber="VR004", dateCreated="2026-06-09T14:30:00Z")
    assert isinstance(b.created_at, datetime)
    assert b.created_at.year == 2026


def test_rezdy_booking_get_utm():
    b = RezdyBooking(
        orderNumber="VR005",
        fields=[
            {"label": "utm_source", "value": "facebook"},
            {"label": "utm_campaign", "value": "carioquinha"},
        ],
    )
    assert b.get_utm("utm_source") == "facebook"
    assert b.get_utm("utm_campaign") == "carioquinha"
    assert b.get_utm("utm_medium") is None
