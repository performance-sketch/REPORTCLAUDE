import hashlib
import json
import pytest

from connectors.rezdy.webhooks import compute_payload_hash, verify_signature, parse_webhook
from connectors.rezdy.schemas import RezdyWebhookPayload


def test_compute_payload_hash_deterministic():
    payload = {"event": "order.created", "booking": {"orderNumber": "VR001"}}
    h1 = compute_payload_hash("rezdy", "order.created", payload)
    h2 = compute_payload_hash("rezdy", "order.created", payload)
    assert h1 == h2
    assert len(h1) == 64


def test_compute_payload_hash_different_for_different_source():
    payload = {"event": "order.created"}
    h1 = compute_payload_hash("rezdy", "order.created", payload)
    h2 = compute_payload_hash("meta_ads", "order.created", payload)
    assert h1 != h2


def test_compute_payload_hash_idempotent_on_key_order():
    p1 = {"b": 2, "a": 1}
    p2 = {"a": 1, "b": 2}
    h1 = compute_payload_hash("rezdy", "order.created", p1)
    h2 = compute_payload_hash("rezdy", "order.created", p2)
    assert h1 == h2


def test_verify_signature_valid():
    import hmac
    body = b'{"event":"order.created"}'
    secret = "test_secret"
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, expected, secret) is True


def test_verify_signature_invalid():
    body = b'{"event":"order.created"}'
    assert verify_signature(body, "bad_sig", "test_secret") is False


def test_verify_signature_empty_secret_always_passes():
    body = b'{"event":"order.created"}'
    assert verify_signature(body, "anything", "") is True


def test_parse_webhook_valid():
    payload = {
        "event": "order.created",
        "booking": {
            "orderNumber": "VRTEST01",
            "status": "CONFIRMED",
            "totalAmount": 1200.0,
            "customer": {"firstName": "João", "lastName": "Silva", "email": "joao@test.com"},
        }
    }
    body = json.dumps(payload).encode()
    result = parse_webhook(body)
    assert isinstance(result, RezdyWebhookPayload)
    assert result.event == "order.created"
    assert result.booking.orderNumber == "VRTEST01"


def test_parse_webhook_invalid_signature_raises():
    body = b'{"event":"order.created","booking":{"orderNumber":"VR1"}}'
    with pytest.raises(ValueError, match="Invalid webhook signature"):
        parse_webhook(body, secret="mysecret", signature="bad")


@pytest.mark.asyncio
async def test_webhook_endpoint_idempotent(client):
    payload = {
        "event": "order.created",
        "booking": {
            "orderNumber": "VRTEST_IDEMPOTENT",
            "status": "CONFIRMED",
            "totalAmount": 500.0,
        }
    }
    body = json.dumps(payload).encode()

    r1 = await client.post("/webhooks/rezdy", content=body, headers={"Content-Type": "application/json"})
    r2 = await client.post("/webhooks/rezdy", content=body, headers={"Content-Type": "application/json"})

    assert r1.status_code == 202
    assert r2.status_code == 202
