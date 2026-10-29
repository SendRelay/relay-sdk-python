"""Runs the shared SDK conformance fixtures (packages/sdks/conformance) against this SDK.

Every Relay SDK runs the same fixtures, which is how they stay at parity. Each fixture runs twice:
once through ``Relay`` and once through ``AsyncRelay``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List

import httpx
import pytest

from sendrelay import ApiError, AsyncRelay, NetworkError, Relay, RetryConfig, ValidationError, verify_webhook_signature
from sendrelay._http import RETRYABLE_STATUS_CODES, Config

DIR = Path(os.environ.get("RELAY_CONFORMANCE_DIR", Path(__file__).resolve().parents[2] / "conformance"))
pytestmark = pytest.mark.skipif(not (DIR / "manifest.json").exists(), reason="conformance folder not found")


def read(name: str) -> Any:
    return json.loads((DIR / name).read_text())


def fixtures() -> List[Dict[str, Any]]:
    if not (DIR / "http").exists():
        return []
    return [json.loads(p.read_text()) for p in sorted((DIR / "http").rglob("*.json"))]


SYNC: Dict[str, Callable[[Relay, Dict[str, Any]], Any]] = {
    "tasks.quote": lambda r, i: r.tasks.quote(i["body"]),
    "tasks.create": lambda r, i: r.tasks.create(i["body"], idempotency_key=i.get("idempotencyKey")),
    "tasks.list": lambda r, i: r.tasks.list(**(i.get("query") or {})),
    "tasks.listAll": lambda r, i: [t["id"] for t in r.tasks.list_all(**(i.get("query") or {}))],
    "tasks.get": lambda r, i: r.tasks.get(i["taskId"]),
    "tasks.cancel": lambda r, i: r.tasks.cancel(i["taskId"], i.get("body")),
    "tasks.assign": lambda r, i: r.tasks.assign(i["taskId"], i["body"]),
    "tasks.availableRiders": lambda r, i: r.tasks.available_riders(i["taskId"], **(i.get("query") or {})),
    "tasks.rate": lambda r, i: r.tasks.rate(i["taskId"], i["body"]),
    "tasks.dispute": lambda r, i: r.tasks.dispute(i["taskId"], i["body"]),
    "webhooks.create": lambda r, i: r.webhooks.create(i["body"]),
    "webhooks.list": lambda r, i: r.webhooks.list(),
    "webhooks.get": lambda r, i: r.webhooks.get(i["webhookId"]),
    "webhooks.update": lambda r, i: r.webhooks.update(i["webhookId"], i["body"]),
    "webhooks.delete": lambda r, i: r.webhooks.delete(i["webhookId"]),
    "auth.createWebSocketToken": lambda r, i: r.auth.create_websocket_token(i["body"]),
    "presence.get": lambda r, i: r.presence.get(**i["query"]),
}


async def run_async(relay: AsyncRelay, op: str, i: Dict[str, Any]) -> Any:
    q = i.get("query") or {}
    if op == "tasks.quote":
        return await relay.tasks.quote(i["body"])
    if op == "tasks.create":
        return await relay.tasks.create(i["body"], idempotency_key=i.get("idempotencyKey"))
    if op == "tasks.list":
        return await relay.tasks.list(**q)
    if op == "tasks.listAll":
        return [t["id"] async for t in relay.tasks.list_all(**q)]
    if op == "tasks.get":
        return await relay.tasks.get(i["taskId"])
    if op == "tasks.cancel":
        return await relay.tasks.cancel(i["taskId"], i.get("body"))
    if op == "tasks.assign":
        return await relay.tasks.assign(i["taskId"], i["body"])
    if op == "tasks.availableRiders":
        return await relay.tasks.available_riders(i["taskId"], **q)
    if op == "tasks.rate":
        return await relay.tasks.rate(i["taskId"], i["body"])
    if op == "tasks.dispute":
        return await relay.tasks.dispute(i["taskId"], i["body"])
    if op == "webhooks.create":
        return await relay.webhooks.create(i["body"])
    if op == "webhooks.list":
        return await relay.webhooks.list()
    if op == "webhooks.get":
        return await relay.webhooks.get(i["webhookId"])
    if op == "webhooks.update":
        return await relay.webhooks.update(i["webhookId"], i["body"])
    if op == "webhooks.delete":
        return await relay.webhooks.delete(i["webhookId"])
    if op == "auth.createWebSocketToken":
        return await relay.auth.create_websocket_token(i["body"])
    if op == "presence.get":
        return await relay.presence.get(**q)
    raise AssertionError(f"no async binding for {op}")


def lookup(value: Any, dotted: str) -> Any:
    node = value
    for key in dotted.split("."):
        if isinstance(node, list):
            node = node[int(key)] if int(key) < len(node) else None
        elif isinstance(node, dict):
            node = node.get(key)
        else:
            return None
    return node


def expect_paths(actual: Any, expected: Dict[str, Any]) -> None:
    for key, want in expected.items():
        assert lookup(actual, key) == want, f"{key}: {lookup(actual, key)!r} != {want!r}"


def error_json(error: Exception) -> Dict[str, Any]:
    if isinstance(error, ApiError):
        return {"statusCode": error.status_code, "code": error.code, "message": error.message, "details": error.details}
    return {"message": str(error)}


class Exchanges:
    """An httpx transport that answers a fixture's exchanges in order and checks each request."""

    def __init__(self, exchanges: List[Dict[str, Any]], common: Dict[str, str]) -> None:
        self.queue = list(exchanges)
        self.common = common
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        assert self.queue, f"unexpected request {request.method} {request.url}"
        want = self.queue.pop(0)
        expected = want["request"]
        assert request.method == expected["method"]
        assert request.url.path == expected["path"]
        assert dict(request.url.params) == expected["query"]
        body = json.loads(request.content) if request.content else None
        assert body == expected["body"]
        for name, value in {**self.common, **expected["headers"]}.items():
            if value == "<absent>":
                assert name not in request.headers, name
            elif value == "<any>":
                assert request.headers.get(name), name
            else:
                assert request.headers.get(name) == value, name
        return httpx.Response(want["response"]["status"], json=want["response"]["body"])


MANIFEST = read("manifest.json") if (DIR / "manifest.json").exists() else {"server": {}}
SERVER = MANIFEST["server"]
FIXTURES = fixtures()
IDS = [f"{f['operation']}: {f['name']}" for f in FIXTURES]


def test_manifest_is_fully_bound() -> None:
    for op in SERVER["operations"]:
        if op.get("local"):
            continue
        assert op["id"] in SYNC, f"missing binding for {op['id']}"
        assert any(f["operation"] == op["id"] for f in FIXTURES), f"no fixture for {op['id']}"


def make_relay(transport: Any, cls: Any = Relay) -> Any:
    client_cls = httpx.Client if cls is Relay else httpx.AsyncClient
    return cls(
        SERVER["apiKey"],
        base_url=SERVER["baseUrl"],
        retry=RetryConfig(enabled=False),
        http_client=client_cls(transport=httpx.MockTransport(transport)),
    )


def check(fixture: Dict[str, Any], transport: Exchanges, run: Callable[[], Any]) -> None:
    expect = fixture["expect"]
    if "error" in expect:
        want = dict(expect["error"])
        kind = want.pop("type")
        with pytest.raises((ApiError, ValidationError, NetworkError)) as caught:
            run()
        assert type(caught.value).__name__ == kind
        expect_paths(error_json(caught.value), want)
    else:
        result = run()
        if "items" in expect:
            assert result == expect["items"]
        if "result" in expect:
            expect_paths(json.loads(json.dumps(result)), expect["result"])
    assert not transport.queue, "unanswered exchanges"
    assert transport.calls == len(fixture["exchanges"])


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
def test_http_sync(fixture: Dict[str, Any]) -> None:
    transport = Exchanges(fixture["exchanges"], SERVER["commonHeaders"])
    relay = make_relay(transport)
    check(fixture, transport, lambda: SYNC[fixture["operation"]](relay, fixture["input"]))


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
async def test_http_async(fixture: Dict[str, Any]) -> None:
    transport = Exchanges(fixture["exchanges"], SERVER["commonHeaders"])
    relay = make_relay(transport, AsyncRelay)
    expect = fixture["expect"]
    if "error" in expect:
        want = dict(expect["error"])
        kind = want.pop("type")
        with pytest.raises((ApiError, ValidationError, NetworkError)) as caught:
            await run_async(relay, fixture["operation"], fixture["input"])
        assert type(caught.value).__name__ == kind
        expect_paths(error_json(caught.value), want)
    else:
        result = await run_async(relay, fixture["operation"], fixture["input"])
        if "items" in expect:
            assert result == expect["items"]
        if "result" in expect:
            expect_paths(json.loads(json.dumps(result)), expect["result"])
    assert not transport.queue
    await relay.close()


CLIENT = (
    read("client.json") if (DIR / "client.json").exists() else {"defaults": {}, "apiKeys": [], "errors": {"cases": []}}
)


def test_defaults() -> None:
    d = CLIENT["defaults"]
    config = Config(api_key="sk_test_abc")
    assert config.base_url == d["baseUrl"]
    assert config.api_version == d["apiVersion"]
    assert config.timeout * 1000 == d["timeoutMs"]
    assert config.retry.enabled == d["retry"]["enabled"]
    assert config.retry.max_retries == d["retry"]["maxRetries"]
    assert config.retry.initial_delay * 1000 == d["retry"]["initialDelayMs"]
    assert config.retry.max_delay * 1000 == d["retry"]["maxDelayMs"]
    assert config.retry.backoff_multiplier == d["retry"]["backoffMultiplier"]
    assert list(RETRYABLE_STATUS_CODES) == d["retry"]["retryableStatusCodes"]
    assert config.auto_idempotency == d["idempotency"]["autoGenerate"]


@pytest.mark.parametrize("case", CLIENT["apiKeys"], ids=[repr(c["apiKey"]) for c in CLIENT["apiKeys"]])
def test_api_keys(case: Dict[str, Any]) -> None:
    if case.get("error"):
        with pytest.raises(ValidationError):
            Relay(case["apiKey"])
    else:
        assert Relay(case["apiKey"]).environment == case["environment"]


@pytest.mark.parametrize("case", CLIENT["errors"]["cases"], ids=[c["name"] for c in CLIENT["errors"]["cases"]])
def test_errors(case: Dict[str, Any]) -> None:
    calls = 0

    def answer(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if case.get("networkFailure"):
            raise httpx.ConnectError("connection refused", request=request)
        if "rawBody" in case:
            return httpx.Response(case["status"], text=case["rawBody"])
        return httpx.Response(case["status"], json=case["body"])

    relay = Relay(
        SERVER["apiKey"],
        base_url=SERVER["baseUrl"],
        retry=RetryConfig(max_retries=1, initial_delay=0, max_delay=0),
        http_client=httpx.Client(transport=httpx.MockTransport(answer)),
    )
    want = dict(case["expect"])
    kind = want.pop("type")
    with pytest.raises((ApiError, NetworkError)) as caught:
        relay.tasks.get("t_1")
    assert type(caught.value).__name__ == kind
    expect_paths(error_json(caught.value), want)
    assert calls == case["attempts"]


SIGNATURES = read("webhooks/signatures.json")["cases"] if (DIR / "webhooks").exists() else []


@pytest.mark.parametrize("case", SIGNATURES, ids=[c["name"] for c in SIGNATURES])
def test_webhook_signatures(case: Dict[str, Any]) -> None:
    result = verify_webhook_signature(case["payload"], case["header"], case["secret"], case["tolerance"])
    assert result.valid == case["valid"]
    if not case["valid"]:
        assert result.error == case["error"]
    assert (
        Relay.__init__
        and Relay("sk_test_abc")
        .webhooks.verify_signature(case["payload"], case["header"], case["secret"], case["tolerance"])
        .valid
        == case["valid"]
    )
