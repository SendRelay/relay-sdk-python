from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterator, Mapping, Optional, cast

import httpx

from . import _operations as ops
from ._errors import ValidationError
from ._http import DEFAULT_API_VERSION, DEFAULT_BASE_URL, Config, Request, RetryConfig, send, send_async
from ._webhooks import WebhookSignatureVerification, verify_webhook_signature
from .types import (
    CancelTaskResponse,
    Claim,
    ClaimState,
    ClaimUpload,
    CreateTaskResponse,
    CreateWebhookResponse,
    GetTaskResponse,
    ListEventsResponse,
    ListTasksResponse,
    ListWebhooksResponse,
    PresenceResponse,
    RedeliverWebhookResponse,
    RelayEvent,
    SimulateAdvanceResponse,
    TaskEventsResponse,
    TaskListItem,
    TaskQuoteResponse,
    TrackingLinkResponse,
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
        """One page of tasks, newest first by default. Filters: ``limit``, ``order``, ``cursor``, and
        ``updatedSince`` (ISO 8601) for tasks changed since then, in ``updatedAt`` order."""
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

    def update(self, task_id: str, body: Body) -> Dict[str, Any]:
        """Change ``notes``, ``externalId``, or a stop's ``instructions`` and ``contact`` until that
        stop is completed. Anything affecting price or dispatch is FIELD_NOT_EDITABLE."""
        return cast(Dict[str, Any], self._run(ops.tasks_update(task_id, body)))

    def tracking_link(self, task_id: str, body: Optional[Body] = None) -> TrackingLinkResponse:
        """A hosted tracking page to send your customer. ``{"stageIndex": n}`` limits it to one drop-off."""
        return cast(TrackingLinkResponse, self._run(ops.tasks_tracking_link(task_id, body)))

    def events(self, task_id: str) -> TaskEventsResponse:
        """Every event about a task, oldest first, each with its ``data["revision"]``."""
        return cast(TaskEventsResponse, self._run(ops.tasks_events(task_id)))

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

    def simulate_advance(self, task_id: str) -> SimulateAdvanceResponse:
        """Test keys only: open a ``SCHEDULED`` task's search now instead of at ``searchStartsAt``."""
        return cast(SimulateAdvanceResponse, self._run(ops.tasks_simulate_advance(task_id)))


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

    def redeliver(self, webhook_id: str, body: Body) -> RedeliverWebhookResponse:
        """Send a logged event (``{"eventId": ...}``) to this endpoint again, with the same id."""
        return cast(RedeliverWebhookResponse, self._run(ops.webhooks_redeliver(webhook_id, body)))

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


class Events:
    def __init__(self, run: Any) -> None:
        self._run = run

    def list(self, **query: Any) -> ListEventsResponse:
        """One page of events for your account and the key's mode, kept 30 days. Filters:
        ``limit``, ``order`` (``"asc"`` to catch up), ``cursor``, ``types`` (a list of event types)."""
        return cast(ListEventsResponse, self._run(ops.events_list(query)))

    def list_all(self, **query: Any) -> Iterator[RelayEvent]:
        """Every matching event, following the cursor page by page."""
        cursor: Optional[str] = None
        while True:
            page = self.list(**{**query, **({"cursor": cursor} if cursor else {})})
            yield from page["data"]
            cursor = page.get("cursor") if page.get("hasMore") else None
            if not cursor:
                return


class Claims:
    """Insurance claims on a task, for insured goods lost, stolen or damaged after the rider collected
    them. Test keys insure nothing, so their tasks can't be claimed on."""

    def __init__(self, run: Any) -> None:
        self._run = run

    def get(self, task_id: str) -> ClaimState:
        """The task's claim, or whether you can file one (``canFile``, ``reason``) and until when."""
        return cast(ClaimState, self._run(ops.claims_get(task_id)))

    def create_upload(self, task_id: str, body: Body) -> ClaimUpload:
        """Somewhere to upload one file: ``{"contentType": "image/jpeg"}``. PUT the file to ``uploadUrl``
        with that ``Content-Type``, then pass ``{"key": ..., "name": ...}`` in a claim's ``files``."""
        return cast(ClaimUpload, self._run(ops.claims_create_upload(task_id, body)))

    def file(self, task_id: str, body: Body) -> Claim:
        """File a claim: ``incidentType``, ``incidentDate``, ``claimedAmount`` (kobo), ``description``, ``files``."""
        return cast(Claim, self._run(ops.claims_file(task_id, body)))

    def respond(self, task_id: str, body: Body) -> Claim:
        """Answer Relay's request for more information (``status == "NEEDS_INFO"``): ``message``, ``files``."""
        return cast(Claim, self._run(ops.claims_respond(task_id, body)))

    def withdraw(self, task_id: str) -> Claim:
        """Withdraw a claim that is still being decided. You can file again afterwards."""
        return cast(Claim, self._run(ops.claims_withdraw(task_id)))


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
        self.events = Events(self._request)
        self.claims = Claims(self._request)

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

    async def update(self, task_id: str, body: Body) -> Dict[str, Any]:
        return cast(Dict[str, Any], await self._run(ops.tasks_update(task_id, body)))

    async def tracking_link(self, task_id: str, body: Optional[Body] = None) -> TrackingLinkResponse:
        return cast(TrackingLinkResponse, await self._run(ops.tasks_tracking_link(task_id, body)))

    async def events(self, task_id: str) -> TaskEventsResponse:
        return cast(TaskEventsResponse, await self._run(ops.tasks_events(task_id)))

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

    async def simulate_advance(self, task_id: str) -> SimulateAdvanceResponse:
        """Test keys only: open a ``SCHEDULED`` task's search now instead of at ``searchStartsAt``."""
        return cast(SimulateAdvanceResponse, await self._run(ops.tasks_simulate_advance(task_id)))


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

    async def redeliver(self, webhook_id: str, body: Body) -> RedeliverWebhookResponse:
        return cast(RedeliverWebhookResponse, await self._run(ops.webhooks_redeliver(webhook_id, body)))

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


class AsyncEvents:
    def __init__(self, run: Any) -> None:
        self._run = run

    async def list(self, **query: Any) -> ListEventsResponse:
        return cast(ListEventsResponse, await self._run(ops.events_list(query)))

    async def list_all(self, **query: Any) -> AsyncIterator[RelayEvent]:
        cursor: Optional[str] = None
        while True:
            page = await self.list(**{**query, **({"cursor": cursor} if cursor else {})})
            for item in page["data"]:
                yield item
            cursor = page.get("cursor") if page.get("hasMore") else None
            if not cursor:
                return


class AsyncClaims:
    def __init__(self, run: Any) -> None:
        self._run = run

    async def get(self, task_id: str) -> ClaimState:
        return cast(ClaimState, await self._run(ops.claims_get(task_id)))

    async def create_upload(self, task_id: str, body: Body) -> ClaimUpload:
        return cast(ClaimUpload, await self._run(ops.claims_create_upload(task_id, body)))

    async def file(self, task_id: str, body: Body) -> Claim:
        return cast(Claim, await self._run(ops.claims_file(task_id, body)))

    async def respond(self, task_id: str, body: Body) -> Claim:
        return cast(Claim, await self._run(ops.claims_respond(task_id, body)))

    async def withdraw(self, task_id: str) -> Claim:
        return cast(Claim, await self._run(ops.claims_withdraw(task_id)))


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
        self.events = AsyncEvents(self._request)
        self.claims = AsyncClaims(self._request)

    async def _request(self, request: Request) -> Any:
        return await send_async(self._config, self._http, request)

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncRelay:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
