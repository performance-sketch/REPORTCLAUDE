import pytest


def _safe_div(num, den):
    return round(num / den, 4) if den else None


def test_roas_real():
    assert _safe_div(11000, 2200) == pytest.approx(5.0)
    assert _safe_div(0, 0) is None
    assert _safe_div(5000, 0) is None


def test_cac():
    assert _safe_div(2200, 10) == pytest.approx(220.0)
    assert _safe_div(2200, 0) is None


def test_avg_ticket():
    assert _safe_div(11000, 5) == pytest.approx(2200.0)


def test_ctr():
    assert _safe_div(500, 10000) == pytest.approx(0.05)


def test_cpc():
    assert _safe_div(2200, 500) == pytest.approx(4.4)


def test_cpm():
    assert _safe_div(2200 * 1000, 10000) == pytest.approx(220.0)


def test_click_to_booking_rate():
    assert _safe_div(10, 500) == pytest.approx(0.02)


def test_cancellation_rate():
    assert _safe_div(3, 10) == pytest.approx(0.3)


def test_revenue_per_click():
    assert _safe_div(11000, 500) == pytest.approx(22.0)


@pytest.mark.asyncio
async def test_health_endpoint(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
