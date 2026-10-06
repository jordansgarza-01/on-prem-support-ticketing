"""Individual-account authentication: e-mail identity, password policy, hashing, lockout and reset."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import math
import re
import secrets
import string
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ticket_data import STAFF_DIRECTORY

EMAIL_DOMAIN = "owens-minor.com"
_NAME_PART = r"[a-z]+(?:[-'][a-z]+)*"
_EMAIL_PATTERN = re.compile(rf"^{_NAME_PART}\.{_NAME_PART}@{re.escape(EMAIL_DOMAIN)}$")

# Only these accounts may see the Service Overview and Performance Management portals.
MANAGEMENT_EMAILS = frozenset(
    {
        "george.dixon@owens-minor.com",
        "deno.erickson@owens-minor.com",
        "jordan.garza@owens-minor.com",
    }
)

MAX_FAILED_ATTEMPTS = 3
LOCKOUT_DURATION = dt.timedelta(minutes=15)
RESET_TOKEN_TTL = dt.timedelta(hours=1)
RESET_REQUEST_COOLDOWN = dt.timedelta(seconds=60)
MIN_PASSWORD_LENGTH = 10

PASSWORD_REQUIREMENTS_TEXT = (
    f"At least {MIN_PASSWORD_LENGTH} characters of letters, numbers and symbols, including at least "
    "one uppercase letter, one lowercase letter, one number and one symbol. No character may be "
    "used more than once, and spaces are not allowed."
)
EMAIL_FORMAT_MESSAGE = f"Enter your Owens & Minor e-mail address (firstname.lastname@{EMAIL_DOMAIN})."
GENERIC_LOGIN_ERROR = "Incorrect e-mail or password."
GENERIC_RESET_MESSAGE = (
    "If that address is eligible, a link to set or reset your password has been e-mailed to it. "
    "The link expires in 60 minutes."
)
INVALID_RESET_LINK_MESSAGE = "This reset link is invalid or has expired. Request a new one."

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _SCRYPT_DKLEN = 2**14, 8, 1, 32
_ALLOWED_PASSWORD_CHARACTERS = set(string.ascii_letters + string.digits + string.punctuation)


def normalize_email(raw_email: str | None) -> str:
    return str(raw_email or "").strip().lower()


def is_valid_corporate_email(email: str) -> bool:
    return bool(_EMAIL_PATTERN.fullmatch(normalize_email(email)))


def is_management_email(email: str | None) -> bool:
    return normalize_email(email) in MANAGEMENT_EMAILS


def email_for_name(name: str | None) -> str | None:
    """Derive firstname.lastname@owens-minor.com from a two-word display name."""
    parts = str(name or "").strip().lower().split()
    if len(parts) != 2:
        return None
    email = f"{parts[0]}.{parts[1]}@{EMAIL_DOMAIN}"
    return email if is_valid_corporate_email(email) else None


_DIRECTORY_NAMES_BY_EMAIL = {
    email: name for name in STAFF_DIRECTORY if (email := email_for_name(name))
}


def display_name_for_email(email: str) -> str:
    """Return the name tickets use for this person (directory spelling first, else title-cased)."""
    normalized = normalize_email(email)
    if normalized in _DIRECTORY_NAMES_BY_EMAIL:
        return _DIRECTORY_NAMES_BY_EMAIL[normalized]
    local_part = normalized.split("@", 1)[0]
    return " ".join(part.title() for part in local_part.split("."))


def validate_password(password: str) -> list[str]:
    """Return the unmet password requirements (empty when the password is acceptable)."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if any(character not in _ALLOWED_PASSWORD_CHARACTERS for character in password):
        problems.append("Use only letters, numbers and symbols (no spaces).")
    if not any(character in string.ascii_uppercase for character in password):
        problems.append("Include at least one uppercase letter.")
    if not any(character in string.ascii_lowercase for character in password):
        problems.append("Include at least one lowercase letter.")
    if not any(character in string.digits for character in password):
        problems.append("Include at least one number.")
    if not any(character in string.punctuation for character in password):
        problems.append("Include at least one symbol.")
    if len(set(password)) != len(password):
        problems.append("Do not repeat any character.")
    return problems


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN, maxmem=64 * 1024 * 1024,
    )
    return "$".join(
        [
            "scrypt", str(_SCRYPT_N), str(_SCRYPT_R), str(_SCRYPT_P),
            base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = str(stored_hash).split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p),
            dklen=len(expected), maxmem=64 * 1024 * 1024,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_reset_token() -> tuple[str, str]:
    """Return (token to e-mail, hash to store); the raw token is never persisted."""
    token = secrets.token_urlsafe(32)
    return token, hash_reset_token(token)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    message: str = ""
    locked: bool = False
    email: str = ""
    name: str = ""
    problems: tuple[str, ...] = field(default_factory=tuple)


class AccountService:
    """Login, lockout and password-reset rules on top of a user store.

    `store` needs get_user(email) -> dict | None and save_user(dict). The two senders take
    (email, display_name, reset_token) and return True when the e-mail was handed off.
    """

    def __init__(
        self,
        store: Any,
        send_reset_email: Callable[[str, str, str], bool],
        send_lockout_email: Callable[[str, str, str], bool],
        clock: Callable[[], dt.datetime] = _utcnow,
    ) -> None:
        self._store = store
        self._send_reset_email = send_reset_email
        self._send_lockout_email = send_lockout_email
        self._clock = clock

    @staticmethod
    def _safe_send(sender: Callable[[str, str, str], bool], email: str, name: str, token: str) -> bool:
        try:
            return bool(sender(email, name, token))
        except Exception:
            return False

    @staticmethod
    def _locked_message(remaining: dt.timedelta, emailed: bool | None) -> str:
        minutes = max(1, math.ceil(remaining.total_seconds() / 60))
        unit = "minute" if minutes == 1 else "minutes"
        message = f"Too many incorrect attempts. This account is locked for {minutes} more {unit}."
        if emailed is False:
            return message + " Reset your password with \"Forgot password\" once e-mail is available."
        return message + " Check your e-mail for a link to reset your password."

    def authenticate(self, raw_email: str, password: str) -> AuthResult:
        email = normalize_email(raw_email)
        if not is_valid_corporate_email(email):
            return AuthResult(False, EMAIL_FORMAT_MESSAGE)

        user = self._store.get_user(email)
        if not user or not user.get("password_hash"):
            # Spend comparable time so response timing doesn't reveal whether an account exists.
            verify_password(password, hash_password("timing-equalizer"))
            return AuthResult(False, GENERIC_LOGIN_ERROR)

        now = self._clock()
        name = display_name_for_email(email)
        locked_until = _parse_timestamp(user.get("locked_until"))
        if locked_until and locked_until > now:
            return AuthResult(False, self._locked_message(locked_until - now, None), locked=True)
        if locked_until:
            user["failed_attempts"] = 0
            user["locked_until"] = None

        if verify_password(password, user["password_hash"]):
            user["failed_attempts"] = 0
            user["locked_until"] = None
            self._store.save_user(user)
            return AuthResult(True, email=email, name=name)

        attempts = int(user.get("failed_attempts") or 0) + 1
        user["failed_attempts"] = attempts
        if attempts < MAX_FAILED_ATTEMPTS:
            self._store.save_user(user)
            return AuthResult(False, GENERIC_LOGIN_ERROR)

        token, token_hash = generate_reset_token()
        user["locked_until"] = (now + LOCKOUT_DURATION).isoformat()
        user["reset_token_hash"] = token_hash
        user["reset_token_expires"] = (now + RESET_TOKEN_TTL).isoformat()
        self._store.save_user(user)
        emailed = self._safe_send(self._send_lockout_email, email, name, token)
        return AuthResult(False, self._locked_message(LOCKOUT_DURATION, emailed), locked=True)

    def request_password_reset(self, raw_email: str) -> AuthResult:
        """Issue a single-use, expiring link for first-time setup or a forgotten password."""
        email = normalize_email(raw_email)
        if not is_valid_corporate_email(email):
            return AuthResult(False, EMAIL_FORMAT_MESSAGE)

        now = self._clock()
        user = self._store.get_user(email) or {"email": email, "failed_attempts": 0}
        expires = _parse_timestamp(user.get("reset_token_expires"))
        if expires and (expires - RESET_TOKEN_TTL) > now - RESET_REQUEST_COOLDOWN:
            # A link went out moments ago; don't let this form be used to flood a mailbox.
            return AuthResult(True, GENERIC_RESET_MESSAGE)

        token, token_hash = generate_reset_token()
        user["email"] = email
        user["reset_token_hash"] = token_hash
        user["reset_token_expires"] = (now + RESET_TOKEN_TTL).isoformat()
        self._store.save_user(user)
        self._safe_send(self._send_reset_email, email, display_name_for_email(email), token)
        return AuthResult(True, GENERIC_RESET_MESSAGE)

    def complete_password_reset(self, raw_email: str, token: str, new_password: str) -> AuthResult:
        email = normalize_email(raw_email)
        if not is_valid_corporate_email(email) or not token:
            return AuthResult(False, INVALID_RESET_LINK_MESSAGE)

        user = self._store.get_user(email)
        now = self._clock()
        stored_hash = (user or {}).get("reset_token_hash")
        expires = _parse_timestamp((user or {}).get("reset_token_expires"))
        token_is_valid = bool(
            user and stored_hash and expires and expires > now
            and hmac.compare_digest(str(stored_hash), hash_reset_token(token))
        )
        if not token_is_valid:
            return AuthResult(False, INVALID_RESET_LINK_MESSAGE)

        problems = validate_password(new_password)
        if user.get("password_hash") and verify_password(new_password, user["password_hash"]):
            problems.append("Choose a password different from your current one.")
        if problems:
            # The link stays valid so the person can correct the password and retry.
            return AuthResult(False, "That password doesn't meet the requirements.", problems=tuple(problems))

        user["password_hash"] = hash_password(new_password)
        user["failed_attempts"] = 0
        user["locked_until"] = None
        user["reset_token_hash"] = None
        user["reset_token_expires"] = None
        self._store.save_user(user)
        return AuthResult(True, email=email, name=display_name_for_email(email))
