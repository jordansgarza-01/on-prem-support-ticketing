import datetime as dt
from urllib.parse import parse_qs, urlparse

import pytest

import auth
import manage_accounts

EMAIL = "jordan.garza@owens-minor.com"
PASSWORD = "Jordan56#kQ"


class FakeRepo:
    def __init__(self):
        self.users = {}

    def get_user(self, email):
        user = self.users.get(email)
        return dict(user) if user else None

    def save_user(self, user):
        self.users[user["email"]] = dict(user)


def test_set_password_lets_the_person_log_in_without_any_e_mail():
    repo = FakeRepo()

    manage_accounts.set_password(repo, EMAIL.upper(), PASSWORD)

    assert repo.users[EMAIL]["password_hash"].startswith("scrypt$")
    assert PASSWORD not in str(repo.users)
    service = auth.AccountService(repo, lambda *a: True, lambda *a: True)
    result = service.authenticate(EMAIL, PASSWORD)
    assert result.ok and result.name == "Jordan Garza"


def test_set_password_enforces_the_policy_and_stores_nothing_when_it_fails():
    repo = FakeRepo()

    with pytest.raises(ValueError, match="uppercase"):
        manage_accounts.set_password(repo, EMAIL, "weakpassword1!")

    assert repo.users == {}


def test_set_password_clears_a_lockout_and_pending_reset_link():
    repo = FakeRepo()
    repo.save_user(
        {"email": EMAIL, "password_hash": "old", "failed_attempts": 3,
         "locked_until": "2999-01-01T00:00:00+00:00", "reset_token_hash": "x", "reset_token_expires": "2999-01-01T00:00:00+00:00"}
    )

    manage_accounts.set_password(repo, EMAIL, PASSWORD)

    user = repo.users[EMAIL]
    assert user["failed_attempts"] == 0 and user["locked_until"] is None and user["reset_token_hash"] is None


def test_reset_link_works_with_the_normal_reset_flow_and_expires_in_an_hour():
    repo = FakeRepo()
    now = dt.datetime(2026, 10, 6, 12, 0, tzinfo=dt.timezone.utc)

    link = manage_accounts.create_reset_link(repo, EMAIL, "https://app.example.com", now=now)

    query = parse_qs(urlparse(link).query)
    token = query["reset_token"][0]
    assert query["email"] == [EMAIL] and link.startswith("https://app.example.com/?")
    assert repo.users[EMAIL]["reset_token_hash"] == auth.hash_reset_token(token)
    assert token not in str(repo.users)
    service = auth.AccountService(repo, lambda *a: True, lambda *a: True, clock=lambda: now + dt.timedelta(minutes=30))
    assert service.complete_password_reset(EMAIL, token, PASSWORD).ok
    other = FakeRepo()
    other_link = manage_accounts.create_reset_link(other, EMAIL, "https://app.example.com", now=now)
    expired = auth.AccountService(other, lambda *a: True, lambda *a: True, clock=lambda: now + dt.timedelta(minutes=61))
    assert not expired.complete_password_reset(EMAIL, parse_qs(urlparse(other_link).query)["reset_token"][0], PASSWORD).ok


def test_unlock_resets_attempts_and_requires_an_existing_account():
    repo = FakeRepo()
    repo.save_user({"email": EMAIL, "password_hash": "h", "failed_attempts": 3, "locked_until": "2999-01-01T00:00:00+00:00"})

    manage_accounts.unlock_account(repo, EMAIL)

    assert repo.users[EMAIL]["failed_attempts"] == 0 and repo.users[EMAIL]["locked_until"] is None
    with pytest.raises(ValueError, match="no account"):
        manage_accounts.unlock_account(repo, "nobody.here@owens-minor.com")


def test_status_describes_account_state_without_revealing_secrets():
    repo = FakeRepo()
    assert "no account yet" in manage_accounts.describe_account(repo, EMAIL)
    manage_accounts.set_password(repo, EMAIL, PASSWORD)

    report = manage_accounts.describe_account(repo, EMAIL)

    assert "password set:     yes" in report and "locked:           no" in report
    assert "scrypt" not in report and PASSWORD not in report


def test_non_corporate_addresses_are_rejected():
    with pytest.raises(ValueError, match="owens-minor.com"):
        manage_accounts.set_password(FakeRepo(), "jordan@gmail.com", PASSWORD)


def test_cli_set_password_prompts_twice_and_reports_success():
    repo, output = FakeRepo(), []
    answers = iter([PASSWORD, PASSWORD])

    code = manage_accounts.main(
        ["set-password", EMAIL], repo=repo, settings={}, prompt=lambda _label: next(answers), out=output.append
    )

    assert code == 0 and EMAIL in repo.users and "They can log in now" in output[-1]


def test_cli_rejects_mismatched_passwords_and_store_failures_are_reported():
    output = []
    answers = iter([PASSWORD, "Different1!pw"])
    code = manage_accounts.main(
        ["set-password", EMAIL], repo=FakeRepo(), settings={}, prompt=lambda _l: next(answers), out=output.append
    )
    assert code == 1 and "don't match" in output[-1]

    class BrokenRepo:
        def get_user(self, email):
            raise RuntimeError("relation app_users does not exist")

    output.clear()
    assert manage_accounts.main(["status", EMAIL], repo=BrokenRepo(), settings={}, out=output.append) == 2
    assert "0003_add_app_users_table.sql" in output[-1]


def test_cli_reset_link_uses_configured_app_url():
    output = []

    manage_accounts.main(
        ["reset-link", EMAIL], repo=FakeRepo(), settings={"APP_BASE_URL": "https://app.example.com"}, out=output.append
    )

    assert output[0].startswith("https://app.example.com/?reset_token=")


def test_settings_prefer_environment_over_secrets_file(tmp_path):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text('SUPABASE_URL = "https://file.supabase.co"\nSUPABASE_SERVICE_ROLE_KEY = "file-key"\nOTHER = "ignored"\n')

    settings = manage_accounts.load_settings({"SUPABASE_URL": "https://env.supabase.co"}, secrets)

    assert settings == {"SUPABASE_URL": "https://env.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "file-key"}
