import pandas as pd

import streamlit_app
from ticket_data import (
    calculate_average_resolution_time_hours,
    calculate_average_closed_tickets_per_week,
    calculate_average_open_tickets_per_week,
    calculate_high_priority_open_ticket_count,
    calculate_open_ticket_count,
    calculate_resolution_rate,
    create_initial_ticket_dataframe,
    delete_ticket_by_id,
    filter_tickets_by_code,
    filter_tickets_by_id,
    sanitize_ticket_dataframe,
)


def test_create_initial_ticket_dataframe_starts_empty():
    df = create_initial_ticket_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "ID",
        "Issue",
        "Code",
        "Priority",
        "Date Submitted",
        "Date Closed",
        "Submitted By",
        "Assigned To",
        "Notes",
        "Resolution Status",
    ]
    assert df.empty


def test_sanitize_ticket_dataframe_removes_fake_ticket_ids():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1001",
                "Issue": "fake",
                "Resolution Status": "Pending",
                "Priority": "High",
                "Date Submitted": "2024-01-01",
            },
            {
                "ID": "TICKET-1009",
                "Issue": "real",
                "Resolution Status": "Pending",
                "Priority": "Medium",
                "Date Submitted": "2024-05-01",
            },
        ]
    )

    cleaned = sanitize_ticket_dataframe(df)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["ID"] == "TICKET-1009"


def test_sanitize_ticket_dataframe_replaces_empty_close_date_placeholder():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1009",
                "Issue": "real",
                "Date Closed": "empty",
                "Resolution Status": "Pending",
            }
        ]
    )

    cleaned = sanitize_ticket_dataframe(df)

    assert cleaned.iloc[0]["Date Closed"] == ""


def test_sanitize_ticket_dataframe_adds_default_code_to_legacy_tickets():
    df = pd.DataFrame(
        [{"ID": "TICKET-1009", "Issue": "real", "Resolution Status": "Pending"}]
    )

    cleaned = sanitize_ticket_dataframe(df)

    assert cleaned.iloc[0]["Code"] == "IT"


def test_sanitize_ticket_dataframe_adds_notes_to_legacy_tickets():
    df = pd.DataFrame(
        [{"ID": "TICKET-1009", "Issue": "real", "Resolution Status": "Pending"}]
    )

    cleaned = sanitize_ticket_dataframe(df)

    assert cleaned.iloc[0]["Notes"] == ""


def test_delete_ticket_by_id_removes_the_requested_row():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1009",
                "Issue": "first",
                "Resolution Status": "Pending",
                "Priority": "High",
                "Date Submitted": "2024-05-01",
            },
            {
                "ID": "TICKET-1010",
                "Issue": "second",
                "Resolution Status": "Resolved",
                "Priority": "Low",
                "Date Submitted": "2024-05-02",
            },
        ]
    )

    updated = delete_ticket_by_id(df, "TICKET-1009")

    assert len(updated) == 1
    assert updated.iloc[0]["ID"] == "TICKET-1010"


def test_filter_tickets_by_id_matches_ticket_numbers_case_insensitively():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1009",
                "Issue": "first",
                "Resolution Status": "Pending",
                "Priority": "High",
                "Date Submitted": "2024-05-01",
            },
            {
                "ID": "TICKET-1010",
                "Issue": "second",
                "Resolution Status": "Resolved",
                "Priority": "Low",
                "Date Submitted": "2024-05-02",
            },
        ]
    )

    filtered = filter_tickets_by_id(df, "ticket-1010")

    assert len(filtered) == 1
    assert filtered.iloc[0]["ID"] == "TICKET-1010"


def test_filter_tickets_by_code_returns_matching_tickets():
    df = pd.DataFrame(
        [
            {"ID": "TICKET-1009", "Code": "IT"},
            {"ID": "TICKET-1010", "Code": "Maintenance"},
            {"ID": "TICKET-1011", "Code": "IT"},
        ]
    )

    filtered = filter_tickets_by_code(df, "it")

    assert filtered["ID"].tolist() == ["TICKET-1009", "TICKET-1011"]


def test_calculate_average_open_tickets_per_week_uses_ticket_history():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1011",
                "Issue": "one",
                "Resolution Status": "Pending",
                "Priority": "High",
                "Date Submitted": "08-02-2026",
            },
            {
                "ID": "TICKET-1012",
                "Issue": "two",
                "Resolution Status": "Resolved",
                "Priority": "Medium",
                "Date Submitted": "08-09-2026",
            },
            {
                "ID": "TICKET-1013",
                "Issue": "three",
                "Resolution Status": "Pending",
                "Priority": "Low",
                "Date Submitted": "08-16-2026",
            },
        ]
    )

    assert calculate_average_open_tickets_per_week(df) == 1.0
    assert calculate_average_closed_tickets_per_week(df) == 1.0


def test_calculate_average_tickets_per_week_accepts_mixed_date_formats():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1014",
                "Issue": "one",
                "Resolution Status": "Pending",
                "Priority": "High",
                "Date Submitted": "08-02-2026",
            },
            {
                "ID": "TICKET-1015",
                "Issue": "two",
                "Resolution Status": "Pending",
                "Priority": "Medium",
                "Date Submitted": "2026-08-03",
            },
            {
                "ID": "TICKET-1016",
                "Issue": "three",
                "Resolution Status": "Pending",
                "Priority": "Low",
                "Date Submitted": "08-09-2026",
            },
        ]
    )

    assert calculate_average_open_tickets_per_week(df) == 1.5


def test_calculate_average_tickets_per_week_accepts_submitted_timestamp():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1017",
                "Issue": "one",
                "Resolution Status": "Pending",
                "Priority": "High",
                "Date Submitted": "2026-08-04 12:34:56 ET",
            }
        ]
    )

    assert calculate_average_open_tickets_per_week(df) == 1.0


def test_helpdesk_kpis_calculate_from_ticket_data():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1018",
                "Priority": "High",
                "Date Submitted": "2026-08-04 08:00:00 ET",
                "Date Closed": "",
                "Resolution Status": "Pending",
            },
            {
                "ID": "TICKET-1019",
                "Priority": "Low",
                "Date Submitted": "2026-08-04 09:00:00",
                "Date Closed": "",
                "Resolution Status": "In Process",
            },
            {
                "ID": "TICKET-1020",
                "Priority": "Medium",
                "Date Submitted": "2026-08-04 10:00:00",
                "Date Closed": "2026-08-04 14:30:00",
                "Resolution Status": "Resolved",
            },
        ]
    )

    assert calculate_open_ticket_count(df) == 2
    assert calculate_high_priority_open_ticket_count(df) == 1
    assert calculate_resolution_rate(df) == 33.33
    assert calculate_average_resolution_time_hours(df) == 4.5


def test_calculate_average_tickets_per_week_ignores_unparseable_dates():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1014",
                "Issue": "one",
                "Resolution Status": "Pending",
                "Priority": "High",
                "Date Submitted": "08-02-2026",
            },
            {
                "ID": "TICKET-1015",
                "Issue": "two",
                "Resolution Status": "Resolved",
                "Priority": "Medium",
                "Date Submitted": "not-a-date",
            },
            {
                "ID": "TICKET-1016",
                "Issue": "three",
                "Resolution Status": "Pending",
                "Priority": "Low",
                "Date Submitted": "",
            },
        ]
    )

    assert calculate_average_open_tickets_per_week(df) == 1.0
    assert calculate_average_closed_tickets_per_week(df) == 0.0


def test_sanitize_ticket_dataframe_handles_missing_id_column():
    df = pd.DataFrame([{"Issue": "missing id", "Resolution Status": "Pending"}])

    cleaned = sanitize_ticket_dataframe(df)

    assert cleaned.equals(df)


def test_call_local_support_assistant_returns_printer_guidance():
    reply = streamlit_app.call_local_support_assistant("printer is offline")

    assert "printer" in reply.lower()
    assert "zebra zt620" in reply.lower()
    assert "honeywell rp4d" in reply.lower()
    assert "ricoh im 460f" in reply.lower()


def test_call_local_support_assistant_returns_rp4d_guidance():
    reply = streamlit_app.call_local_support_assistant("My Honeywell RP4D will not print")

    assert "honeywell rp4d" in reply.lower()
    assert "battery" in reply.lower()
    assert "re-pair" in reply.lower()


def test_get_assistant_reply_does_not_call_github_models(monkeypatch):
    def fail_if_called(prompt):
        raise AssertionError("GitHub Models should not be called")

    monkeypatch.setattr(
        streamlit_app, "call_github_models_support_assistant", fail_if_called
    )

    reply = streamlit_app.get_assistant_reply("printer is offline")

    assert "printer" in reply.lower()


def test_get_github_models_token_uses_dedicated_environment_variable(monkeypatch):
    monkeypatch.setenv("GITHUB_MODELS_TOKEN", "models-token")
    monkeypatch.setenv("GITHUB_TOKEN", "general-token")
    monkeypatch.setenv("GH_TOKEN", "general-token")

    assert streamlit_app._get_github_models_token() == "models-token"


def test_clear_assistant_messages_resets_conversation_history():
    session_state = {
        "assistant_messages": [
            {"role": "user", "content": "old prompt"},
            {"role": "assistant", "content": "old response"},
        ]
    }

    streamlit_app.clear_assistant_messages(session_state)

    assert session_state["assistant_messages"] == []


def test_format_stat_value_rounds_to_two_decimals():
    assert streamlit_app.format_stat_value(3) == "3.00"
    assert streamlit_app.format_stat_value(3.456) == "3.46"


def test_get_github_models_token_ignores_generic_github_tokens(monkeypatch):
    monkeypatch.delenv("GITHUB_MODELS_TOKEN", raising=False)
    monkeypatch.setattr(streamlit_app.st, "secrets", {}, raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")
    monkeypatch.setenv("GH_TOKEN", "gh-token")

    assert streamlit_app._get_github_models_token() is None


def test_get_github_models_token_uses_streamlit_secrets(monkeypatch):
    monkeypatch.delenv("GITHUB_MODELS_TOKEN", raising=False)
    monkeypatch.setattr(
        streamlit_app.st,
        "secrets",
        {"GITHUB_MODELS_TOKEN": "secret-from-secrets"},
        raising=False,
    )

    assert streamlit_app._get_github_models_token() == "secret-from-secrets"
