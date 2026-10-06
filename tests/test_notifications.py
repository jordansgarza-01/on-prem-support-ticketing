import pytest

import notifications
from notifications import EmailNotConfiguredError, EmailSettings

SETTINGS = EmailSettings(
    host="smtp.example.com", port=587, username="svc", password="pw",
    sender="support@owens-minor.com", app_url="https://app.example.com",
)


def test_settings_require_a_host_and_sender():
    with pytest.raises(EmailNotConfiguredError):
        EmailSettings.from_mapping({})
    with pytest.raises(EmailNotConfiguredError):
        EmailSettings.from_mapping({"SMTP_HOST": "smtp.example.com"})


def test_settings_default_to_starttls_port_and_strip_trailing_slash_from_app_url():
    settings = EmailSettings.from_mapping(
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_USERNAME": "svc@owens-minor.com",
            "SMTP_PASSWORD": "pw",
            "APP_BASE_URL": "https://app.example.com/",
        }
    )
    assert settings.port == 587
    assert settings.sender == "svc@owens-minor.com"
    assert settings.app_url == "https://app.example.com"


def test_reset_link_carries_the_email_and_token_as_query_parameters():
    link = notifications.build_reset_link("https://app.example.com/", "gary.lewis@owens-minor.com", "tok_en-1")
    assert link == "https://app.example.com/?reset_token=tok_en-1&email=gary.lewis%40owens-minor.com"


def test_ticket_update_email_is_branded_names_the_update_and_links_to_login():
    ticket = {"ID": "TICKET-ABC123", "Issue": "Printer jam", "Resolution Status": "Resolved"}

    subject, text, page = notifications.build_ticket_update_email(
        "https://app.example.com", "Gary Lewis", ticket,
        ["Status changed from Pending to Resolved"], "Jordan Garza", "2026-10-01 09:00:00 ET",
    )

    assert "TICKET-ABC123" in subject and "Status changed from Pending to Resolved" in subject
    assert "Hello Gary," in text and "https://app.example.com" in text and "Jordan Garza" in text
    assert notifications.BRAND_BURGUNDY in page and "Owens &amp; Minor" in page
    assert 'href="https://app.example.com"' in page and "Log in to review the update" in page
    assert "Resolved" in page


def test_ticket_update_email_escapes_user_supplied_text():
    ticket = {"ID": "T-1", "Issue": "<script>alert(1)</script>", "Resolution Status": "Pending"}

    _subject, _text, page = notifications.build_ticket_update_email(
        "https://app.example.com", "Gary Lewis", ticket,
        ['Notes set to: <img src=x onerror=alert(1)>'], "<b>Eve</b>", "now",
    )

    assert "<script>" not in page and "<img src=x" not in page and "<b>Eve</b>" not in page
    assert "&lt;script&gt;" in page


def test_long_descriptions_are_truncated_in_the_update_email():
    ticket = {"ID": "T-1", "Issue": "x" * 500, "Resolution Status": "Pending"}
    _subject, text, _page = notifications.build_ticket_update_email(
        "https://app.example.com", "Gary Lewis", ticket, ["Updated"], "Jordan Garza", "now"
    )
    assert "x" * 201 not in text and "..." in text


def test_reset_and_lockout_emails_contain_the_single_use_link_and_lockout_details():
    _s, reset_text, reset_page = notifications.build_reset_email(
        "https://app.example.com", "Gary Lewis", "gary.lewis@owens-minor.com", "TOKEN123"
    )
    _s, lock_text, lock_page = notifications.build_lockout_email(
        "https://app.example.com", "Gary Lewis", "gary.lewis@owens-minor.com", "TOKEN123"
    )

    assert "reset_token=TOKEN123" in reset_text and "Set my password" in reset_page
    assert "15 minutes" in lock_text and "reset_token=TOKEN123" in lock_text
    assert "Reset my password" in lock_page and notifications.BRAND_BURGUNDY in lock_page


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.calls = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message):
        self.calls.append(("send", message))


def test_send_email_uses_starttls_logs_in_and_sends_multipart_html():
    FakeSMTP.instances.clear()

    notifications.send_email(SETTINGS, "gary.lewis@owens-minor.com", "Subject", "plain", "<p>html</p>", smtp_factory=FakeSMTP)

    server = FakeSMTP.instances[0]
    assert (server.host, server.port) == ("smtp.example.com", 587)
    assert server.calls[:2] == ["starttls", ("login", "svc", "pw")]
    message = server.calls[2][1]
    assert message["To"] == "gary.lewis@owens-minor.com" and message["Subject"] == "Subject"
    assert message.get_body(("html",)).get_content().strip() == "<p>html</p>"
    assert message.get_body(("plain",)).get_content().strip() == "plain"


def test_send_email_on_implicit_tls_port_skips_starttls():
    FakeSMTP.instances.clear()
    settings = EmailSettings(**{**SETTINGS.__dict__, "port": 465})

    notifications.send_email(settings, "a@b.com", "S", "t", "<p>h</p>", smtp_factory=FakeSMTP)

    assert "starttls" not in FakeSMTP.instances[0].calls
