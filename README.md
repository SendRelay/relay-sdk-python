# Relay Python SDK

The official server SDK for [Relay](https://sendrelay.com.ng), the delivery API. Quote and create deliveries, read them back with the rider's live ETA, manage webhooks, and mint tracking tokens for your apps.

```bash
pip install sendrelay
```

Python 3.9 or newer. Use `Relay` in regular code and `AsyncRelay` with asyncio. Both have the same methods.

## Quick start

```python
import os
from sendrelay import Relay

relay = Relay(api_key=os.environ["RELAY_API_KEY"])  # sk_test_... or sk_live_..., server only

stages = [
    {
        "type": "PICKUP",
        "location": {"latitude": 6.5244, "longitude": 3.3792, "address": "12 Marina Road, Lagos"},
        "items": [{"name": "Phone case", "estimatedValue": 500000, "estimatedWeight": "LIGHT", "estimatedSize": "BOX"}],
    },
    {"type": "DROPOFF", "location": {"latitude": 6.4474, "longitude": 3.4723, "address": "22 Admiralty Way, Lekki"}},
]

quote = relay.tasks.quote({"taskType": "PACKAGE_DELIVERY", "stages": stages})
print(quote["total"])  # kobo

created = relay.tasks.create(
    {"taskType": "PACKAGE_DELIVERY", "stages": stages, "quoteId": quote["quoteId"]},
    idempotency_key="order-1042",  # retries with the same key never create a second delivery
)

read = relay.tasks.get(created["task"]["id"])
if read["liveEta"]:
    print(f"Arriving at stop {read['liveEta']['stageIndex'] + 1} at {read['liveEta']['arrivesAt']}")
```

Responses are plain dicts with the API's field names (`liveEta`, `totalFee`, ...). `sendrelay.types` has TypedDicts for them.

## Asyncio

```python
from sendrelay import AsyncRelay

async with AsyncRelay(api_key=os.environ["RELAY_API_KEY"]) as relay:
    async for task in relay.tasks.list_all(limit=50):
        print(task["id"], task["status"])
```

## Webhooks

```python
from sendrelay import verify_webhook_signature

result = verify_webhook_signature(raw_body, request.headers["X-Relay-Signature"], os.environ["RELAY_WEBHOOK_SECRET"])
if not result.valid:
    return 400
```

Pass the raw request body exactly as received, not re-serialized JSON.

## Errors and retries

- `ApiError` has `status_code`, `code` and `details` from the API.
- `NetworkError` means the request never got an answer.
- `ValidationError` means the SDK rejected the input before sending.

Timeouts, 408, 429 and 5xx responses are retried up to 3 times with exponential backoff. Test-mode quota errors are not retried. Change this with `max_retries=` or `retry=RetryConfig(...)`.

## Tracking in your app

Mint a short-lived token on your server and hand it to your app:

```python
token = relay.auth.create_websocket_token({"scope": [f"task:{task_id}"]})["token"]
```

Your app then tracks the task live with one of the UI SDKs.

[Full documentation](https://docs.sendrelay.com.ng/sdks/python-sdk)
