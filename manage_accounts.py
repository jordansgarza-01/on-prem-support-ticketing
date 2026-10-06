"""Admin tool to provision accounts without e-mail (needs the Supabase service-role key).

    python manage_accounts.py status EMAIL        # does the account exist, is it locked?
    python manage_accounts.py set-password EMAIL  # prompts (hidden) for the new password
    python manage_accounts.py reset-link EMAIL    # prints a single-use link to hand over securely
    python manage_accounts.py unlock EMAIL        # clears a lockout / failed-attempt counter

Credentials come from .streamlit/secrets.toml or the SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY /
APP_BASE_URL environment variables (environment wins).
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Callable, Mapping

import auth
import notifications
from ticket_repository import SupabaseTicketRepository, validate_supabase_url

SETTING_NAMES = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "APP_BASE_URL")
DEFAULT_SECRETS_PATH = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"


def load_settings(env: Mapping[str, str] | None = None, secrets_path: Path = DEFAULT_SECRETS_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if secrets_path.exists():
        values.update({k: str(v) for k, v in tomllib.loads(secrets_path.read_text()).items() if k in SETTING_NAMES})
    for name in SETTING_NAMES:
        if (env if env is not None else os.environ).get(name):
            values[name] = (env if env is not None else os.environ)[name]
    return values


def build_repository(settings: Mapping[str, str]) -> SupabaseTicketRepository:
    missing = [name for name in SETTING_NAMES[:2] if not settings.get(name)]
    if missing:
        raise RuntimeError(f"Missing {', '.join(missing)} (set them in .streamlit/secrets.toml or the environment).")
    from supabase import create_client

    return SupabaseTicketRepository(
        create_client(validate_supabase_url(settings["SUPABASE_URL"]), settings["SUPABASE_SERVICE_ROLE_KEY"])
    )


def _require_email(raw_email: str) -> str:
    email = auth.normalize_email(raw_email)
    if not auth.is_valid_corporate_email(email):
        raise ValueError(auth.EMAIL_FORMAT_MESSAGE)
    return email


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def describe_account(repo: Any, raw_email: str, now: dt.datetime | None = None) -> str:
    email = _require_email(raw_email)
    user = repo.get_user(email)
    if not user:
        return f"{email}: no account yet (the person can use 'First time or forgot password?', or run set-password)."
    now = now or _utcnow()
    locked_until = auth._parse_timestamp(user.get("locked_until"))
    token_expires = auth._parse_timestamp(user.get("reset_token_expires"))
    lines = [
        f"{email}",
        f"  password set:     {'yes' if user.get('password_hash') else 'no'}",
        f"  failed attempts:  {int(user.get('failed_attempts') or 0)}",
        f"  locked:           {'until ' + locked_until.isoformat() if locked_until and locked_until > now else 'no'}",
        f"  reset link:       {'pending' if token_expires and token_expires > now else 'none active'}",
    ]
    return "\n".join(lines)


def set_password(repo: Any, raw_email: str, password: str) -> str:
    email = _require_email(raw_email)
    problems = auth.validate_password(password)
    if problems:
        raise ValueError(" ".join(problems))
    user = repo.get_user(email) or {"email": email}
    user.update(
        email=email,
        password_hash=auth.hash_password(password),
        failed_attempts=0,
        locked_until=None,
        reset_token_hash=None,
        reset_token_expires=None,
    )
    repo.save_user(user)
    return email


def create_reset_link(repo: Any, raw_email: str, app_url: str, now: dt.datetime | None = None) -> str:
    email = _require_email(raw_email)
    now = now or _utcnow()
    token, token_hash = auth.generate_reset_token()
    user = repo.get_user(email) or {"email": email, "failed_attempts": 0}
    user.update(
        email=email,
        reset_token_hash=token_hash,
        reset_token_expires=(now + auth.RESET_TOKEN_TTL).isoformat(),
    )
    repo.save_user(user)
    return notifications.build_reset_link(app_url, email, token)


def unlock_account(repo: Any, raw_email: str) -> str:
    email = _require_email(raw_email)
    user = repo.get_user(email)
    if not user:
        raise ValueError(f"{email} has no account to unlock.")
    user.update(failed_attempts=0, locked_until=None)
    repo.save_user(user)
    return email


def main(
    argv: list[str] | None = None,
    repo: Any = None,
    settings: Mapping[str, str] | None = None,
    prompt: Callable[[str], str] = getpass.getpass,
    out: Callable[[str], None] = print,
) -> int:
    parser = argparse.ArgumentParser(description="Manage O&M support-portal accounts.")
    parser.add_argument("command", choices=["status", "set-password", "reset-link", "unlock"])
    parser.add_argument("email", help="firstname.lastname@owens-minor.com")
    args = parser.parse_args(argv)

    try:
        settings = settings if settings is not None else load_settings()
        repo = repo or build_repository(settings)
        if args.command == "status":
            out(describe_account(repo, args.email))
        elif args.command == "set-password":
            _require_email(args.email)
            out(auth.PASSWORD_REQUIREMENTS_TEXT)
            password = prompt("New password: ")
            if password != prompt("Confirm password: "):
                raise ValueError("The two passwords don't match.")
            out(f"Password set for {set_password(repo, args.email, password)}. They can log in now.")
        elif args.command == "reset-link":
            app_url = settings.get("APP_BASE_URL") or notifications.DEFAULT_APP_URL
            out(create_reset_link(repo, args.email, app_url))
            out("Single use; expires in 60 minutes. Send it only to the account owner.")
        else:
            out(f"Unlocked {unlock_account(repo, args.email)}.")
    except ValueError as exc:
        out(f"Error: {exc}")
        return 1
    except Exception as exc:
        hint = (
            "Have you run migrations/0003_add_app_users_table.sql?"
            if "app_users" in str(exc)
            else "Check SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (the exact Project URL from Supabase > Settings > API)."
        )
        out(f"Could not reach the account store: {exc}\n{hint}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
