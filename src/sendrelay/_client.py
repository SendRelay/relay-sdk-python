from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterator, Mapping, Optional, cast

import httpx

from . import _operations as ops
from ._errors import ValidationError
from ._http import DEFAULT_API_VERSION, DEFAULT_BASE_URL, Config, Request, RetryConfig, send, send_async
from ._webhooks import WebhookSignatureVerification, verify_webhook_signature
from .types import (
    CancelTaskResponse,
    CreateTaskResponse,
    CreateWebhookResponse,
    GetTaskResponse,
    ListTasksResponse,
    ListWebhooksResponse,
    PresenceResponse,
    TaskListItem,
    TaskQuoteResponse,
    Webhook,
    WebSocketToken,
)

Body = Mapping[str, Any]


def _config(
    api_key: str,
    base_url: Optional[str],
    api_version: Optional[str],
    timeout: float,
    max_retries: Optional[int],
    retry: Optional[RetryConfig],
    auto_idempotency: bool,
    headers: Optional[Dict[str, str]],
) -> Config:
    if not api_key:
        raise ValidationError("API key is required", "api_key")
    if not (api_key.startswith("sk_live_") or api_key.startswith("sk_test_")):
        raise ValidationError("Invalid API key format. Must start with sk_live_ or sk_test_", "api_key")
    retry = retry or RetryConfig()
    if max_retries is not None:
        retry.max_retries = max_retries
    return Config(
        api_key=api_key,
        base_url=base_url or DEFAULT_BASE_URL,
        api_version=api_version or DEFAULT_API_VERSION,
        timeout=timeout,
        retry=retry,
        auto_idempotency=auto_idempotency,
        headers=dict(headers or {}),
    )


class _Base:
    _config: Config

    @property
    def environment(self) -> str:
        """``"live"`` for a live key, ``"test"`` for a test key."""
        return "live" if self._config.api_key.startswith("sk_live_") else "test"


# ─── Sync ────────────────────────────────────────────────────────────────────


class Tasks:
    def __init__(self, run: Any) -> None:
        self._run = run

    def quote(self, body: Body) -> TaskQuoteResponse:
        """Price a delivery without creating it. Pass the ``quoteId`` to ``create`` to lock the price."""
        return cast(TaskQuoteResponse, self._run(ops.tasks_quote(body)))

    def create(self, body: Body, *, idempotency_key: Optional[str] = None) -> CreateTaskResponse:
        """Create a delivery. Pass your own ``idempotency_key`` (for example your order ID) so retries
        never create a second delivery; otherwise one is generated per call."""
        return cast(CreateTaskResponse, self._run(ops.tasks_create(body, idempotency_key)))

    def list(self, **query: Any) -> ListTasksResponse:
        """One page of tasks, newest first by default. Filters: ``limit``, ``order``, ``cursor``."""
        return cast(ListTasksResponse, self._run(ops.tasks_list(query)))

    def list_all(self, **query: Any) -> Iterator[TaskListItem]:
        """Every task, following the cursor page by page."""
        cursor: Optional[str] = None
        while True:
            page = self.list(**{**query, **({"cursor": cursor} if cursor else {})})
            yield from page["data"]
            cursor = page.get("cursor") if page.get("hasMore") else None
            if not cursor:
                return

    def get(self, task_id: str) -> GetTaskResponse:
        """A task, with your ``rating`` of it and the rider's ``liveEta`` while they are on the way."""
        return cast(GetTaskResponse, self._run(ops.tasks_get(task_id)))

    def cancel(self, task_id: str, body: Optional[Body] = None) -> CancelTaskResponse:
        return cast(CancelTaskResponse, self._run(ops.tasks_cancel(task_id, body)))

    def assign(self, task_id: str, body: Body) -> Dict[str, Any]:
        """Offer a manual (``autoAssign: false``) live task to riders from ``available_riders``."""
        return cast(Dict[str, Any], self._run(ops.tasks_assign(task_id, body)))

    def available_riders(self, task_id: str, **query: Any) -> Dict[str, Any]:
        return cast(Dict[str, Any], self._run(ops.tasks_available_riders(task_id, query)))

    def rate(self, task_id: str, body: Body) -> Dict[str, Any]:
        """Rate the rider of a completed task, once. Check ``get(...)["rating"]`` first."""
        return cast(Dict[str, Any], self._run(ops.tasks_rate(task_id, body)))

    def dispute(self, task_id: str, body: Body) -> Dict[str, Any]:
        return cast(Dict[str, Any], self._run(ops.tasks_dispute(task_id, body)))


class Webhooks:
    def __init__(self, run: Any) -> None:
        self._run = run

    def create(self, body: Body) -> CreateWebhookResponse:
        """Register an endpoint. Store the returned ``secret``: it is shown only once."""
        return cast(CreateWebhookResponse, self._run(ops.webhooks_create(body)))

    def list(self) -> ListWebhooksResponse:
        return cast(ListWebhooksResponse, self._run(ops.webhooks_list()))

    def get(self, webhook_id: str) -> Webhook:
        return cast(Webhook, self._run(ops.webhooks_get(webhook_id)))

    def update(self, webhook_id: str, body: Body) -> Webhook:
        return cast(Webhook, self._run(ops.webhooks_update(webhook_id, body)))

    def delete(self, webhook_id: str) -> Webhook:
        return cast(Webhook, self._run(ops.webhooks_delete(webhook_id)))

    @staticmethod
    def verify_signature(
        payload: str | bytes, signature_header: str, secret: str, tolerance: int = 300
    ) -> WebhookSignatureVerification:
        """Check a delivery's ``X-Relay-Signature`` header against the raw body."""
        return verify_webhook_signature(payload, signature_header, secret, tolerance)


class Auth:
    def __init__(self, run: Any) -> None:
        self._run = run

    def create_websocket_token(self, body: Body) -> WebSocketToken:
        """A short-lived token for an app to track tasks live. ``scope``: ``["task:<id>", ...]``."""
        return cast(WebSocketToken, self._run(ops.auth_create_websocket_token(body)))


class Presence:
    def __init__(self, run: Any) -> None:
        self._run = run

    def get(self, **query: Any) -> PresenceResponse:
        """Anonymous rider availability around a point: ``latitude``, ``longitude``, ``resolution``."""
        return cast(PresenceResponse, self._run(ops.presence_get(query)))


class Relay(_Base):
    """The Relay server SDK. Keep your API key on your server.

    Example::

        from sendrelay import Relay

        relay = Relay(api_key=os.environ["RELAY_API_KEY"])
        quote = relay.tasks.quote({"taskType": "PACKAGE_DELIVERY", "stages": [...]})
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: Optional[int] = None,
        retry: Optional[RetryConfig] = None,
        auto_idempotency: bool = True,
        headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._config = _config(api_key, base_url, api_version, timeout, max_retries, retry, auto_idempotency, headers)
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)
        self.tasks = Tasks(self._request)
        self.webhooks = Webhooks(self._request)
        self.auth = Auth(self._request)
        self.presence = Presence(self._request)

    def _request(self, request: Request) -> Any:
        return send(self._config, self._http, request)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> Relay:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ─── Async ───────────────────────────────────────────────────────────────────


class AsyncTasks:
    def __init__(self, run: Any) -> None:
        self._run = run

    async def quote(self, body: Body) -> TaskQuoteResponse:
        return cast(TaskQuoteResponse, await self._run(ops.tasks_quote(body)))

    async def create(self, body: Body, *, idempotency_key: Optional[str] = None) -> CreateTaskResponse:
        return cast(CreateTaskResponse, await self._run(ops.tasks_create(body, idempotency_key)))

    async def list(self, **query: Any) -> ListTasksResponse:
        return cast(ListTasksResponse, await self._run(ops.tasks_list(query)))

    async def list_all(self, **query: Any) -> AsyncIterator[TaskListItem]:
        cursor: Optional[str] = None
        while True:
            page = await self.list(**{**query, **({"cursor": cursor} if cursor else {})})
            for item in page["data"]:
                yield item
            cursor = page.get("cursor") if page.get("hasMore") else None
            if not cursor:
                return

    async def get(self, task_id: str) -> GetTaskResponse:
        return cast(GetTaskResponse, await self._run(ops.tasks_get(task_id)))

    async def cancel(self, task_id: str, body: Optional[Body] = None) -> CancelTaskResponse:
        return cast(CancelTaskResponse, await self._run(ops.tasks_cancel(task_id, body)))

    async def assign(self, task_id: str, body: Body) -> Dict[str, Any]:
        return cast(Dict[str, Any], await self._run(ops.tasks_assign(task_id, body)))

    async def available_riders(self, task_id: str, **query: Any) -> Dict[str, Any]:
        return cast(Dict[str, Any], await self._run(ops.tasks_available_riders(task_id, query)))

    async def rate(self, task_id: str, body: Body) -> Dict[str, Any]:
        return cast(Dict[str, Any], await self._run(ops.tasks_rate(task_id, body)))

    async def dispute(self, task_id: str, body: Body) -> Dict[str, Any]:
        return cast(Dict[str, Any], await self._run(ops.tasks_dispute(task_id, body)))


class AsyncWebhooks:
    def __init__(self, run: Any) -> None:
        self._run = run

    async def create(self, body: Body) -> CreateWebhookResponse:
        return cast(CreateWebhookResponse, await self._run(ops.webhooks_create(body)))

    async def list(self) -> ListWebhooksResponse:
        return cast(ListWebhooksResponse, await self._run(ops.webhooks_list()))

    async def get(self, webhook_id: str) -> Webhook:
        return cast(Webhook, await self._run(ops.webhooks_get(webhook_id)))

    async def update(self, webhook_id: str, body: Body) -> Webhook:
        return cast(Webhook, await self._run(ops.webhooks_update(webhook_id, body)))

    async def delete(self, webhook_id: str) -> Webhook:
        return cast(Webhook, await self._run(ops.webhooks_delete(webhook_id)))

    verify_signature = staticmethod(Webhooks.verify_signature)


class AsyncAuth:
    def __init__(self, run: Any) -> None:
        self._run = run

    async def create_websocket_token(self, body: Body) -> WebSocketToken:
        return cast(WebSocketToken, await self._run(ops.auth_create_websocket_token(body)))


class AsyncPresence:
    def __init__(self, run: Any) -> None:
        self._run = run

    async def get(self, **query: Any) -> PresenceResponse:
        return cast(PresenceResponse, await self._run(ops.presence_get(query)))


class AsyncRelay(_Base):
    """The Relay server SDK for asyncio. Same methods as ``Relay``, awaited.

    Example::

        async with AsyncRelay(api_key=os.environ["RELAY_API_KEY"]) as relay:
            task = await relay.tasks.get(task_id)
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: Optional[int] = None,
        retry: Optional[RetryConfig] = None,
        auto_idempotency: bool = True,
        headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._config = _config(api_key, base_url, api_version, timeout, max_retries, retry, auto_idempotency, headers)
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self.tasks = AsyncTasks(self._request)
        self.webhooks = AsyncWebhooks(self._request)
        self.auth = AsyncAuth(self._request)
        self.presence = AsyncPresence(self._request)

    async def _request(self, request: Request) -> Any:
        return await send_async(self._config, self._http, request)

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncRelay:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
