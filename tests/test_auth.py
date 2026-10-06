import datetime as dt

import pytest

import auth
from auth import (
    AccountService,
    generate_reset_token,
    hash_password,
    validate_password,
    verify_password,
)

VALID_PASSWORD = "Abcdef1!gh"
NEW_PASSWORD = "Zyxwvu9#tk"
EMAIL = "gary.lewis@owens-minor.com"


class FakeStore:
    def __init__(self):
        self.users = {}

    def get_user(self, email):
        user = self.users.get(email)
        return dict(user) if user else None

    def save_user(self, user):
        self.users[user["email"]] = dict(user)


class Mailbox:
    def __init__(self):
        self.reset = []
        self.lockout = []
        self.fail = False

    def send_reset(self, email, name, token):
        if self.fail:
            raise RuntimeError("smtp down")
        self.reset.append((email, name, token))
        return True

    def send_lockout(self, email, name, token):
        if self.fail:
            raise RuntimeError("smtp down")
        self.lockout.append((email, name, token))
        return True


class Clock:
    def __init__(self):
        self.now = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += dt.timedelta(**kwargs)


@pytest.fixture
def env():
    store, mailbox, clock = FakeStore(), Mailbox(), Clock()
    service = AccountService(store, mailbox.send_reset, mailbox.send_lockout, clock=clock)
    return service, store, mailbox, clock


def register(env, email=EMAIL, password=VALID_PASSWORD):
    service, _store, mailbox, clock = env
    service.request_password_reset(email)
    token = mailbox.reset[-1][2]
    result = service.complete_password_reset(email, token, password)
    assert result.ok
    clock.advance(minutes=5)


@pytest.mark.parametrize(
    "email",
    [
        "gary.lewis@owens-minor.com",
        "GARY.LEWIS@Owens-Minor.com",
        "  gary.lewis@owens-minor.com ",
        "mary-ann.o'neil@owens-minor.com",
    ],
)
def test_accepts_firstname_lastname_corporate_emails(email):
    assert auth.is_valid_corporate_email(email)


@pytest.mark.parametrize(
    "email",
    [
        "gary@owens-minor.com",
        "gary.lewis@gmail.com",
        "gary.lewis@owens-minor.com.evil.com",
        "gary.lewis@mail.owens-minor.com",
        "gary.m.lewis@owens-minor.com",
        "gary lewis@owens-minor.com",
        "gary.lewis1@owens-minor.com",
        "",
    ],
)
def test_rejects_non_firstname_lastname_or_non_corporate_emails(email):
    assert not auth.is_valid_corporate_email(email)


def test_names_and_emails_map_both_ways_using_directory_spelling():
    assert auth.email_for_name("Michael McDowell") == "michael.mcdowell@owens-minor.com"
    assert auth.display_name_for_email("MICHAEL.MCDOWELL@owens-minor.com") == "Michael McDowell"
    assert auth.display_name_for_email("jane.smith@owens-minor.com") == "Jane Smith"
    assert auth.email_for_name("Unknown") is None
    assert auth.email_for_name(None) is None


def test_only_the_three_management_accounts_get_management_portals():
    for email in (
        "george.dixon@owens-minor.com",
        "Deno.Erickson@owens-minor.com",
        "jordan.garza@owens-minor.com",
    ):
        assert auth.is_management_email(email)
    for email in ("gary.lewis@owens-minor.com", "", None, "george.dixon@gmail.com"):
        assert not auth.is_management_email(email)


def test_password_policy_accepts_a_compliant_password():
    assert validate_password(VALID_PASSWORD) == []


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Ab1!cdefg", "at least 10"),
        ("abcdef1!gh", "uppercase"),
        ("ABCDEF1!GH", "lowercase"),
        ("Abcdefg!hi", "number"),
        ("Abcdef1ghi", "symbol"),
        ("Abcdef1!gg", "repeat"),
        ("Abcdef1! gh", "no spaces"),
        ("Abcdef1!ghé", "no spaces"),
    ],
)
def test_password_policy_reports_each_unmet_requirement(password, expected):
    problems = " ".join(validate_password(password)).lower()
    assert expected in problems


def test_hash_is_salted_verifiable_and_never_the_password():
    first, second = hash_password(VALID_PASSWORD), hash_password(VALID_PASSWORD)
    assert first != second
    assert VALID_PASSWORD not in first
    assert verify_password(VALID_PASSWORD, first)
    assert not verify_password("Wrong1!pass", first)
    assert not verify_password(VALID_PASSWORD, "not-a-hash")
    assert not verify_password(VALID_PASSWORD, None)


def test_first_time_setup_link_creates_an_account_that_can_log_in(env):
    service, store, mailbox, _clock = env

    requested = service.request_password_reset(EMAIL)
    assert requested.ok
    email, name, token = mailbox.reset[0]
    assert (email, name) == (EMAIL, "Gary Lewis")
    assert store.users[EMAIL]["reset_token_hash"] != token

    completed = service.complete_password_reset(EMAIL, token, VALID_PASSWORD)
    assert completed.ok and completed.name == "Gary Lewis"
    assert store.users[EMAIL]["password_hash"] != VALID_PASSWORD

    logged_in = service.authenticate(EMAIL.upper(), VALID_PASSWORD)
    assert logged_in.ok and logged_in.email == EMAIL and logged_in.name == "Gary Lewis"


def test_login_failures_do_not_reveal_whether_an_account_exists(env):
    service, _store, mailbox, _clock = env

    unknown = service.authenticate("nobody.here@owens-minor.com", VALID_PASSWORD)
    assert not unknown.ok and unknown.message == auth.GENERIC_LOGIN_ERROR and not unknown.locked

    register(env)
    wrong = service.authenticate(EMAIL, "Wrong1!pass")
    assert wrong.message == auth.GENERIC_LOGIN_ERROR
    assert mailbox.lockout == []


def test_non_corporate_email_is_rejected_before_any_lookup(env):
    service, store, _mailbox, _clock = env
    result = service.authenticate("gary.lewis@gmail.com", VALID_PASSWORD)
    assert not result.ok and "owens-minor.com" in result.message
    assert store.users == {}
    assert not service.request_password_reset("gary.lewis@gmail.com").ok


def test_three_wrong_passwords_lock_the_account_for_15_minutes_and_email_a_reset_link(env):
    service, store, mailbox, clock = env
    register(env)

    assert not service.authenticate(EMAIL, "Wrong1!pass").locked
    assert not service.authenticate(EMAIL, "Wrong2!pass").locked
    assert mailbox.lockout == []

    third = service.authenticate(EMAIL, "Wrong3!pass")
    assert third.locked and "15 more minutes" in third.message
    assert len(mailbox.lockout) == 1
    assert mailbox.lockout[0][0] == EMAIL

    # Even the right password is refused while locked.
    clock.advance(minutes=14)
    still_locked = service.authenticate(EMAIL, VALID_PASSWORD)
    assert not still_locked.ok and still_locked.locked

    clock.advance(minutes=1, seconds=1)
    assert service.authenticate(EMAIL, VALID_PASSWORD).ok
    assert store.users[EMAIL]["failed_attempts"] == 0
    assert store.users[EMAIL]["locked_until"] is None


def test_successful_login_resets_the_failed_attempt_counter(env):
    service, _store, mailbox, _clock = env
    register(env)

    service.authenticate(EMAIL, "Wrong1!pass")
    service.authenticate(EMAIL, "Wrong2!pass")
    assert service.authenticate(EMAIL, VALID_PASSWORD).ok
    service.authenticate(EMAIL, "Wrong3!pass")
    assert not service.authenticate(EMAIL, "Wrong4!pass").locked
    assert mailbox.lockout == []


def test_lockout_email_link_resets_the_password_and_lifts_the_lock(env):
    service, _store, mailbox, _clock = env
    register(env)
    for attempt in ("Wrong1!pass", "Wrong2!pass", "Wrong3!pass"):
        service.authenticate(EMAIL, attempt)
    token = mailbox.lockout[0][2]

    assert service.complete_password_reset(EMAIL, token, NEW_PASSWORD).ok
    assert service.authenticate(EMAIL, NEW_PASSWORD).ok
    assert not service.authenticate(EMAIL, VALID_PASSWORD).ok


def test_lockout_still_applies_if_the_notification_email_cannot_be_sent(env):
    service, _store, mailbox, _clock = env
    register(env)
    mailbox.fail = True
    for attempt in ("Wrong1!pass", "Wrong2!pass"):
        service.authenticate(EMAIL, attempt)

    third = service.authenticate(EMAIL, "Wrong3!pass")

    assert third.locked
    assert "Forgot password" in third.message


def test_reset_links_are_single_use(env):
    service, _store, mailbox, _clock = env
    service.request_password_reset(EMAIL)
    token = mailbox.reset[0][2]

    assert service.complete_password_reset(EMAIL, token, VALID_PASSWORD).ok
    replay = service.complete_password_reset(EMAIL, token, NEW_PASSWORD)
    assert not replay.ok and replay.message == auth.INVALID_RESET_LINK_MESSAGE


def test_reset_links_expire_after_one_hour(env):
    service, _store, mailbox, clock = env
    service.request_password_reset(EMAIL)
    token = mailbox.reset[0][2]

    clock.advance(minutes=61)

    assert not service.complete_password_reset(EMAIL, token, VALID_PASSWORD).ok


def test_reset_rejects_wrong_tokens_and_other_peoples_tokens(env):
    service, _store, mailbox, _clock = env
    service.request_password_reset(EMAIL)
    service.request_password_reset("tim.norris@owens-minor.com")
    gary_token = mailbox.reset[0][2]
    tim_token = mailbox.reset[1][2]

    assert not service.complete_password_reset(EMAIL, "not-the-token", VALID_PASSWORD).ok
    assert not service.complete_password_reset(EMAIL, tim_token, VALID_PASSWORD).ok
    assert not service.complete_password_reset(EMAIL, "", VALID_PASSWORD).ok
    assert service.complete_password_reset(EMAIL, gary_token, VALID_PASSWORD).ok


def test_weak_password_keeps_the_link_valid_and_lists_what_to_fix(env):
    service, _store, mailbox, _clock = env
    service.request_password_reset(EMAIL)
    token = mailbox.reset[0][2]

    weak = service.complete_password_reset(EMAIL, token, "password")

    assert not weak.ok and weak.problems
    assert service.complete_password_reset(EMAIL, token, VALID_PASSWORD).ok


def test_new_password_must_differ_from_the_current_one(env):
    service, _store, mailbox, clock = env
    register(env)
    clock.advance(minutes=2)
    service.request_password_reset(EMAIL)
    token = mailbox.reset[-1][2]

    same = service.complete_password_reset(EMAIL, token, VALID_PASSWORD)

    assert not same.ok and any("different" in problem for problem in same.problems)


def test_reset_requests_are_rate_limited_per_address(env):
    service, _store, mailbox, clock = env

    service.request_password_reset(EMAIL)
    service.request_password_reset(EMAIL)
    assert len(mailbox.reset) == 1

    clock.advance(seconds=61)
    service.request_password_reset(EMAIL)
    assert len(mailbox.reset) == 2


def test_reset_request_response_is_identical_whether_or_not_the_email_sends(env):
    service, _store, mailbox, _clock = env
    mailbox.fail = True

    result = service.request_password_reset(EMAIL)

    assert result.ok and result.message == auth.GENERIC_RESET_MESSAGE


def test_generated_tokens_are_unique_and_only_their_hash_is_stored():
    (token_a, hash_a), (token_b, hash_b) = generate_reset_token(), generate_reset_token()
    assert token_a != token_b and hash_a != hash_b
    assert auth.hash_reset_token(token_a) == hash_a and token_a not in hash_a
