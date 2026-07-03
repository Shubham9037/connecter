"""Security primitives for HMAC-authenticated sync.

The signing scheme is:

    canonical = f"{timestamp}\\n{connector_id}\\n{company_id}\\n{idempotency_key}\\n{sha256_hex(body)}"
    signature = hex( hmac_sha256(secret, canonical) )

The Windows Connector produces the same string. We recompute server-side and
compare with `hmac.compare_digest` (constant time) to prevent timing oracles.

Nothing in this module logs the secret, the raw body, or the signature.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

# ---------------------------------------------------------------------------
# Configuration (read once at import time — .env is loaded by server.py first)
# ---------------------------------------------------------------------------
MAX_CLOCK_SKEW_SECONDS = int(os.environ.get("SECURITY_MAX_CLOCK_SKEW_SECONDS", "300"))
NONCE_TTL_SECONDS = int(os.environ.get("NONCE_TTL_SECONDS", "600"))
IDEMPOTENCY_TTL_SECONDS = int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "86400"))

_fernet_key = os.environ["CONNECTOR_SECRET_ENCRYPTION_KEY"].encode()
_fernet = Fernet(_fernet_key)


# ---------------------------------------------------------------------------
# Secret generation + encryption at rest
# ---------------------------------------------------------------------------
def generate_connector_id() -> str:
    """Public connector identifier (URL-safe, short-ish)."""
    return f"cn_{secrets.token_urlsafe(9)}"


def generate_secret() -> str:
    """HMAC secret. 48 bytes -> 64 URL-safe chars. `secrets` uses the OS CSPRNG."""
    return secrets.token_urlsafe(48)


def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover — misconfig fails loudly
        raise RuntimeError("Failed to decrypt connector secret; check key rotation.") from exc


def secret_last4(plaintext: str) -> str:
    return plaintext[-4:]


# ---------------------------------------------------------------------------
# Canonical signing string + signature computation
# ---------------------------------------------------------------------------
def canonical_string(
    timestamp: str,
    connector_id: str,
    company_id: str,
    idempotency_key: str,
    body_bytes: bytes,
) -> str:
    """Deterministic order — anything changed here breaks all connectors."""
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    return "\n".join([timestamp, connector_id, company_id, idempotency_key, body_hash])


def sign(secret: str, canonical: str) -> str:
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def signatures_equal(a: str, b: str) -> bool:
    """`hmac.compare_digest` avoids per-byte early exit — no timing oracle."""
    return hmac.compare_digest(a.encode(), b.encode())


# ---------------------------------------------------------------------------
# Timestamp validation
# ---------------------------------------------------------------------------
class TimestampError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def validate_timestamp(raw: str, now: Optional[datetime] = None) -> datetime:
    """Parse and range-check a request timestamp.

    Accepts either RFC3339 ("2025-01-01T00:00:00Z") or an integer Unix seconds
    string. Rejects if outside +/- MAX_CLOCK_SKEW_SECONDS.
    """
    now = now or datetime.now(timezone.utc)
    parsed: datetime
    if raw.isdigit():
        parsed = datetime.fromtimestamp(int(raw), tz=timezone.utc)
    else:
        try:
            # tolerate trailing Z
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TimestampError("malformed_timestamp", "Timestamp must be RFC3339 or epoch seconds.") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

    delta = (now - parsed).total_seconds()
    if delta > MAX_CLOCK_SKEW_SECONDS:
        raise TimestampError("expired_timestamp", f"Timestamp is {int(delta)}s old (max {MAX_CLOCK_SKEW_SECONDS}s).")
    if delta < -MAX_CLOCK_SKEW_SECONDS:
        raise TimestampError("future_timestamp", f"Timestamp is {int(-delta)}s in the future.")
    return parsed


# ---------------------------------------------------------------------------
# Header names — single source of truth
# ---------------------------------------------------------------------------
class Headers:
    SIGNATURE = "X-Signature"
    TIMESTAMP = "X-Timestamp"
    CONNECTOR_ID = "X-Connector-ID"
    COMPANY_ID = "X-Company-ID"
    IDEMPOTENCY_KEY = "X-Idempotency-Key"
    REQUEST_ID = "X-Request-ID"

    REQUIRED_SYNC = (SIGNATURE, TIMESTAMP, CONNECTOR_ID, COMPANY_ID, IDEMPOTENCY_KEY)
