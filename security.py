"""Pure security helpers shared by the dashboard and its companion API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import datetime, timezone


PBKDF2_ITERATIONS = 600_000
LEGACY_PBKDF2_ITERATIONS = 260_000
MIN_PASSWORD_LENGTH = 14
MAX_PASSWORD_LENGTH = 256
MAX_FAILED_ATTEMPTS = 5
ACCOUNT_LOCK_MINUTES = 15
SESSION_TTL_HOURS = 8
INACTIVITY_TIMEOUT_SECONDS = 120

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)


class SecurityConfigurationError(RuntimeError):
    """Raised when the application cannot start without weakening security."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_utc_timestamp(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hash_password(password: str, salt: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        str(salt).encode("utf-8"),
        int(iterations),
    )
    return base64.b64encode(digest).decode("ascii")


def verify_password(password: str, user: dict) -> bool:
    expected = str(user.get("password") or "")
    salt = str(user.get("salt") or "")
    if not expected or not salt or len(str(password)) > MAX_PASSWORD_LENGTH:
        return False
    iterations = int(user.get("password_iterations") or LEGACY_PBKDF2_ITERATIONS)
    candidate = hash_password(password, salt, iterations)
    return hmac.compare_digest(candidate, expected)


def password_needs_upgrade(user: dict) -> bool:
    return int(user.get("password_iterations") or LEGACY_PBKDF2_ITERATIONS) < PBKDF2_ITERATIONS


def valid_password(password: str) -> bool:
    value = str(password or "")
    checks = (
        MIN_PASSWORD_LENGTH <= len(value) <= MAX_PASSWORD_LENGTH,
        bool(re.search(r"[A-Z]", value)),
        bool(re.search(r"[a-z]", value)),
        bool(re.search(r"\d", value)),
        bool(re.search(r"[^A-Za-z0-9]", value)),
    )
    return all(checks)


def valid_username(username: str) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(str(username or "").strip().lower()))


def valid_email(email: str) -> bool:
    value = str(email or "").strip()
    return len(value) <= 254 and bool(EMAIL_PATTERN.fullmatch(value))


def account_is_locked(user: dict, now: datetime | None = None) -> bool:
    locked_until = parse_utc_timestamp(user.get("locked_until"))
    return bool(locked_until and locked_until > (now or utc_now()))


def session_is_active(user: dict, now: datetime | None = None) -> bool:
    expires_at = parse_utc_timestamp(user.get("session_expires_at"))
    return bool(
        user.get("status") == "approved"
        and user.get("session_token_hash")
        and expires_at
        and expires_at > (now or utc_now())
    )


def inactivity_expired(last_activity, now, timeout_seconds=INACTIVITY_TIMEOUT_SECONDS) -> bool:
    try:
        elapsed = float(now) - float(last_activity)
    except (TypeError, ValueError):
        return True
    return elapsed >= max(1, int(timeout_seconds))
