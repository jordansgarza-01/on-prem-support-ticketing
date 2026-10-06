"""Branded e-mail notifications (ticket updates, password reset, lockout) sent over SMTP."""

from __future__ import annotations

import html
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode

BRAND_BURGUNDY = "#7A1F2D"
BRAND_NAME = "Owens & Minor | P&HS Internal Support Portal"
DEFAULT_APP_URL = "https://on-prem-support-ticketing.streamlit.app"


class EmailNotConfiguredError(RuntimeError):
    """Raised when SMTP settings are missing from the app's secrets."""


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    app_url: str

    @classmethod
    def from_mapping(cls, secrets: Mapping[str, Any]) -> "EmailSettings":
        def get(key: str, default: str = "") -> str:
            try:
                value = secrets[key]
            except (KeyError, FileNotFoundError):
                return default
            return str(value).strip() if value is not None else default

        host = get("SMTP_HOST")
        sender = get("SMTP_FROM") or get("SMTP_USERNAME")
        if not host or not sender:
            raise EmailNotConfiguredError(
                "E-mail delivery is not configured. Add SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD "
                "and SMTP_FROM to Streamlit secrets."
            )
        return cls(
            host=host,
            port=int(get("SMTP_PORT", "587") or 587),
            username=get("SMTP_USERNAME"),
            password=get("SMTP_PASSWORD"),
            sender=sender,
            app_url=(get("APP_BASE_URL") or DEFAULT_APP_URL).rstrip("/"),
        )


def build_reset_link(app_url: str, email: str, token: str) -> str:
    return f"{app_url.rstrip('/')}/?{urlencode({'reset_token': token, 'email': email})}"


def _render_html(heading: str, body_html: str, button_label: str, button_url: str, footer: str) -> str:
    return f"""\
<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f2f2f2;font-family:Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f2f2f2;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:8px;overflow:hidden;max-width:600px;">
<tr><td style="background:{BRAND_BURGUNDY};padding:20px 28px;color:#ffffff;">
<span style="font-size:18px;font-weight:700;">{html.escape(BRAND_NAME)}</span></td></tr>
<tr><td style="padding:28px;color:#222222;font-size:15px;line-height:1.5;">
<h2 style="margin:0 0 16px 0;color:{BRAND_BURGUNDY};font-size:20px;">{html.escape(heading)}</h2>
{body_html}
<p style="margin:28px 0;"><a href="{html.escape(button_url, quote=True)}" style="background:{BRAND_BURGUNDY};color:#ffffff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:6px;display:inline-block;">{html.escape(button_label)}</a></p>
<p style="font-size:12px;color:#666666;word-break:break-all;">If the button doesn't work, copy this link into your browser:<br>{html.escape(button_url)}</p>
</td></tr>
<tr><td style="background:#f7f7f7;padding:16px 28px;color:#777777;font-size:12px;">{html.escape(footer)}</td></tr>
</table></td></tr></table></body></html>"""


def build_ticket_update_email(
    app_url: str,
    recipient_name: str,
    ticket: Mapping[str, Any],
    update_lines: Sequence[str],
    updated_by: str,
    updated_at: str,
) -> tuple[str, str, str]:
    """Return (subject, plain_text, html) telling a submitter what changed on their ticket."""
    ticket_id = str(ticket.get("ID", ""))
    issue = str(ticket.get("Issue", "")).strip()
    if len(issue) > 200:
        issue = issue[:197] + "..."
    status = str(ticket.get("Resolution Status", ""))
    subject = f"[P&HS Support] Update on {ticket_id}: {update_lines[0] if update_lines else 'ticket updated'}"
    first_name = (recipient_name.split() or ["there"])[0]
    login_url = app_url

    text = "\n".join(
        [
            f"Hello {first_name},",
            "",
            f"There is a new update on your support ticket {ticket_id}.",
            f"Description: {issue}",
            f"Current status: {status}",
            "",
            "Latest update:",
            *[f"  - {line}" for line in update_lines],
            f"Updated by {updated_by} on {updated_at}.",
            "",
            f"Log in with your account to review it: {login_url}",
            "",
            BRAND_NAME,
        ]
    )
    items = "".join(f"<li>{html.escape(line)}</li>" for line in update_lines)
    body = (
        f"<p>Hello {html.escape(first_name)},</p>"
        f"<p>There is a new update on your support ticket <strong>{html.escape(ticket_id)}</strong>.</p>"
        f"<p style=\"margin:0;\"><strong>Description:</strong> {html.escape(issue)}</p>"
        f"<p style=\"margin:4px 0 16px 0;\"><strong>Current status:</strong> {html.escape(status)}</p>"
        f"<p style=\"margin:0 0 4px 0;\"><strong>Latest update</strong></p><ul style=\"margin:0;padding-left:20px;\">{items}</ul>"
        f"<p style=\"font-size:13px;color:#666666;\">Updated by {html.escape(updated_by)} on {html.escape(updated_at)}.</p>"
    )
    page = _render_html(
        f"Update on {ticket_id}", body, "Log in to review the update", login_url,
        "You are receiving this because you submitted this ticket.",
    )
    return subject, text, page


def build_reset_email(app_url: str, recipient_name: str, email: str, token: str) -> tuple[str, str, str]:
    link = build_reset_link(app_url, email, token)
    first_name = (recipient_name.split() or ["there"])[0]
    subject = "[P&HS Support] Set or reset your password"
    text = (
        f"Hello {first_name},\n\nUse the link below to set or reset your password. It can be used once "
        f"and expires in 60 minutes.\n\n{link}\n\nIf you didn't request this, you can ignore this e-mail.\n\n{BRAND_NAME}"
    )
    body = (
        f"<p>Hello {html.escape(first_name)},</p>"
        "<p>Use the button below to set or reset your password. The link can be used once and expires in 60 minutes.</p>"
        "<p style=\"font-size:13px;color:#666666;\">If you didn't request this, you can ignore this e-mail.</p>"
    )
    return subject, text, _render_html(
        "Set or reset your password", body, "Set my password", link,
        "This message was sent because a password link was requested for this address.",
    )


def build_lockout_email(app_url: str, recipient_name: str, email: str, token: str) -> tuple[str, str, str]:
    link = build_reset_link(app_url, email, token)
    first_name = (recipient_name.split() or ["there"])[0]
    subject = "[P&HS Support] Your account was locked for 15 minutes"
    text = (
        f"Hello {first_name},\n\nThere were 3 incorrect password attempts on your account, so it is locked "
        f"for 15 minutes. If this was you, reset your password with the link below (single use, expires in "
        f"60 minutes). If it wasn't you, resetting your password also secures the account.\n\n{link}\n\n{BRAND_NAME}"
    )
    body = (
        f"<p>Hello {html.escape(first_name)},</p>"
        "<p>There were <strong>3 incorrect password attempts</strong> on your account, so it is locked for <strong>15 minutes</strong>.</p>"
        "<p>Reset your password with the button below. The link can be used once and expires in 60 minutes. "
        "If this wasn't you, resetting your password also secures the account.</p>"
    )
    return subject, text, _render_html(
        "Your account has been locked", body, "Reset my password", link,
        "This is an automated security notice.",
    )


def send_email(
    settings: EmailSettings,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str,
    smtp_factory: Callable[..., Any] | None = None,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"P&HS Support <{settings.sender}>"
    message["To"] = to_address
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if smtp_factory is None:
        if settings.port == 465:
            smtp_factory = lambda host, port: smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20)
        else:
            smtp_factory = lambda host, port: smtplib.SMTP(host, port, timeout=20)
    with smtp_factory(settings.host, settings.port) as server:
        if settings.port != 465:
            server.starttls(context=ssl.create_default_context())
        if settings.username:
            server.login(settings.username, settings.password)
        server.send_message(message)
