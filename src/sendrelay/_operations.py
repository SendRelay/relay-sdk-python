"""Every API operation, defined once as a request. Sync and async resources both use these."""

from __future__ import annotations

from typing import Any, Mapping, Optional
from urllib.parse import quote

from ._errors import ValidationError
from ._http import Request


def _id(value: str, name: str) -> str:
    if not value:
        raise ValidationError(f"{name} is required", name)
    return quote(value, safe="")


def tasks_quote(body: Mapping[str, Any]) -> Request:
    return Request("POST", "/sdk/tasks/quote", body=dict(body))


def tasks_create(body: Mapping[str, Any], idempotency_key: Optional[str]) -> Request:
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    return Request("POST", "/sdk/tasks", body=dict(body), headers=headers)


def tasks_list(query: Optional[Mapping[str, Any]]) -> Request:
    return Request("GET", "/sdk/tasks", query=query)


def tasks_get(task_id: str) -> Request:
    return Request("GET", f"/sdk/tasks/{_id(task_id, 'task_id')}")


def tasks_cancel(task_id: str, body: Optional[Mapping[str, Any]]) -> Request:
    return Request("DELETE", f"/sdk/tasks/{_id(task_id, 'task_id')}/cancel", body=dict(body) if body else None)


def tasks_assign(task_id: str, body: Mapping[str, Any]) -> Request:
    return Request("POST", f"/sdk/tasks/{_id(task_id, 'task_id')}/assign", body=dict(body))


def tasks_available_riders(task_id: str, query: Optional[Mapping[str, Any]]) -> Request:
    return Request("GET", f"/sdk/tasks/{_id(task_id, 'task_id')}/available-riders", query=query)


def tasks_rate(task_id: str, body: Mapping[str, Any]) -> Request:
    return Request("POST", f"/sdk/tasks/{_id(task_id, 'task_id')}/ratings", body=dict(body))


def tasks_dispute(task_id: str, body: Mapping[str, Any]) -> Request:
    return Request("POST", f"/sdk/tasks/{_id(task_id, 'task_id')}/dispute", body=dict(body))


def webhooks_create(body: Mapping[str, Any]) -> Request:
    return Request("POST", "/sdk/webhooks", body=dict(body))


def webhooks_list() -> Request:
    return Request("GET", "/sdk/webhooks")


def webhooks_get(webhook_id: str) -> Request:
    return Request("GET", f"/sdk/webhooks/{_id(webhook_id, 'webhook_id')}")


def webhooks_update(webhook_id: str, body: Mapping[str, Any]) -> Request:
    return Request("PUT", f"/sdk/webhooks/{_id(webhook_id, 'webhook_id')}", body=dict(body))


def webhooks_delete(webhook_id: str) -> Request:
    return Request("DELETE", f"/sdk/webhooks/{_id(webhook_id, 'webhook_id')}")


def auth_create_websocket_token(body: Mapping[str, Any]) -> Request:
    scope = list(body.get("scope") or [])
    if not scope:
        raise ValidationError("scope must contain at least one resource", "scope")
    for resource in scope:
        parts = str(resource).split(":")
        if len(parts) != 2:
            raise ValidationError(
                f'Invalid scope format: "{resource}". Expected "type:id" (e.g., "task:abc123")', "scope"
            )
        kind, ident = parts
        if not kind or not ident:
            raise ValidationError(f'Invalid scope format: "{resource}". Both type and id must be non-empty', "scope")
        if kind == "task" and len(ident.split(",")) > 5:
            raise ValidationError(f'Scoped tasks cannot exceed 5 per scope entry: "{resource}"', "scope")
    expires_in = body.get("expiresIn")
    if expires_in is not None and not 60 <= expires_in <= 7200:
        raise ValidationError("expiresIn must be between 60 and 7200 seconds", "expiresIn")
    return Request(
        "POST",
        "/auth/websocket-token",
        body={"scope": scope, "expiresIn": expires_in if expires_in is not None else 1800},
    )


def presence_get(query: Mapping[str, Any]) -> Request:
    return Request("GET", "/sdk/presence", query=query)
