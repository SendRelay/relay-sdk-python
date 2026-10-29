from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WebhookSignatureVerification:
    valid: bool
    error: Optional[str] = None

    def __bool__(self) -> bool:
        return self.valid


def verify_webhook_signature(
    payload: str | bytes,
    signature_header: str,
    secret: str,
    tolerance: int = 300,
) -> WebhookSignatureVerification:
    """Check that a webhook came from Relay and wasn't changed on the way.

    Pass the raw request body (exactly as received), the ``X-Relay-Signature`` header and the
    ``whsec_...`` secret you got when you created the webhook. ``tolerance`` is how old, in seconds,
    a delivery may be.
    """
    try:
        parts = signature_header.split(",")
        timestamp_part = next((p for p in parts if p.startswith("t=")), None)
        signature_part = next((p for p in parts if p.startswith("v1=")), None)
        if timestamp_part is None or signature_part is None:
            return WebhookSignatureVerification(False, "Invalid signature format")

        timestamp = int(timestamp_part.split("=", 1)[1])
        signature = signature_part.split("=", 1)[1]
        if abs(int(time.time()) - timestamp) > tolerance:
            return WebhookSignatureVerification(False, "Timestamp outside tolerance window")

        # The key is everything after `whsec_` (mode prefix included), base64url-decoded.
        key_text = secret.replace("whsec_", "", 1)
        key = base64.urlsafe_b64decode(key_text + "=" * (-len(key_text) % 4))
        body = payload if isinstance(payload, str) else payload.decode("utf-8")
        expected = hmac.new(key, f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature.encode(), expected.encode()):
            return WebhookSignatureVerification(False, "Signature verification failed")
        return WebhookSignatureVerification(True)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        return WebhookSignatureVerification(False, str(exc))
