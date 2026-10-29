"""HTTP plumbing shared by the sync and async clients: request building, retries and error mapping."""

from __future__ import annotations

import asyncio
import json
import random
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

import httpx

from ._errors import ApiError, NetworkError
from ._version import __version__

DEFAULT_BASE_URL = "https://api.sendrelay.com.ng"
DEFAULT_API_VERSION = "v1"
RETRYABLE_STATUS_CODES: Tuple[int, ...] = (408, 429, 500, 502, 503, 504)
# Test-mode quota 429s last minutes to hours; retrying can't succeed, so surface them at once.
NON_RETRYABLE_ERROR_CODES = frozenset({"TEST_QUOTA_EXCEEDED", "TEST_CONCURRENCY_EXCEEDED"})


@dataclass
class RetryConfig:
    """How failed requests are retried. Delays are in seconds."""

    enabled: bool = True
    max_retries: int = 3
    initial_delay: float = 0.5
    max_delay: float = 10.0
    backoff_multiplier: float = 2.0
    retryable_status_codes: Tuple[int, ...] = RETRYABLE_STATUS_CODES

    def delay(self, attempt: int) -> float:
        base = min(self.initial_delay * self.backoff_multiplier**attempt, self.max_delay)
        # ±25% jitter so many clients don't retry in lockstep.
        return max(0.0, base + base * 0.25 * (random.random() * 2 - 1))


@dataclass
class Request:
    method: str
    path: str
    body: Any = None
    query: Optional[Mapping[str, Any]] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    api_version: str = DEFAULT_API_VERSION
    timeout: float = 30.0
    retry: RetryConfig = field(default_factory=RetryConfig)
    auto_idempotency: bool = True
    headers: Dict[str, str] = field(default_factory=dict)


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build(config: Config, request: Request) -> httpx.Request:
    url = f"{config.base_url.rstrip('/')}/{config.api_version}{request.path}"
    params = {k: _query_value(v) for k, v in (request.query or {}).items() if v is not None}
    headers = {
        "Content-Type": "application/json",
        "X-Relay-Key": config.api_key,
        "User-Agent": f"sendrelay-python/{__version__}",
        **config.headers,
        **request.headers,
    }
    if request.method == "POST" and config.auto_idempotency and "Idempotency-Key" not in headers:
        headers["Idempotency-Key"] = f"sdk-{int(time.time() * 1000)}-{secrets.token_hex(16)}"
    content = json.dumps(request.body).encode() if request.body is not None else None
    return httpx.Request(request.method, url, params=params, headers=headers, content=content)


def api_error(response: httpx.Response) -> ApiError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error") if isinstance(body, dict) else None
    error = error if isinstance(error, dict) else {}
    return ApiError(
        response.status_code,
        error.get("code") or "UNKNOWN_ERROR",
        error.get("message") or response.reason_phrase or "Request failed",
        error.get("details"),
    )


def retryable(config: Config, error: ApiError, attempt: int) -> bool:
    return (
        config.retry.enabled
        and attempt < config.retry.max_retries
        and error.code not in NON_RETRYABLE_ERROR_CODES
        and error.status_code in config.retry.retryable_status_codes
    )


def network_error(config: Config, cause: httpx.TransportError) -> NetworkError:
    if isinstance(cause, httpx.TimeoutException):
        return NetworkError(f"Request timeout after {config.timeout}s", cause)
    return NetworkError("Network error - connection failed", cause)


def send(config: Config, client: httpx.Client, request: Request) -> Any:
    attempt = 0
    while True:
        try:
            response = client.send(build(config, request))
        except httpx.TransportError as exc:
            if config.retry.enabled and attempt < config.retry.max_retries:
                time.sleep(config.retry.delay(attempt))
                attempt += 1
                continue
            raise network_error(config, exc) from exc
        if response.is_success:
            return response.json()
        error = api_error(response)
        if retryable(config, error, attempt):
            time.sleep(config.retry.delay(attempt))
            attempt += 1
            continue
        raise error


async def send_async(config: Config, client: httpx.AsyncClient, request: Request) -> Any:
    attempt = 0
    while True:
        try:
            response = await client.send(build(config, request))
        except httpx.TransportError as exc:
            if config.retry.enabled and attempt < config.retry.max_retries:
                await asyncio.sleep(config.retry.delay(attempt))
                attempt += 1
                continue
            raise network_error(config, exc) from exc
        if response.is_success:
            return response.json()
        error = api_error(response)
        if retryable(config, error, attempt):
            await asyncio.sleep(config.retry.delay(attempt))
            attempt += 1
            continue
        raise error
