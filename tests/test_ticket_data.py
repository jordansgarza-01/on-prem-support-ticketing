import pandas as pd

import streamlit_app
from ticket_repository import (
    SupabaseTicketRepository,
    ticket_records_to_dataframe,
    validate_supabase_url,
)
from ticket_data import (
    calculate_average_resolution_time_hours,
    calculate_average_closed_tickets_per_week,
    calculate_average_open_tickets_per_week,
    calculate_urgent_open_ticket_count,
    calculate_open_ticket_count,
    calculate_resolution_rate,
    create_initial_ticket_dataframe,
    delete_ticket_by_id,
    filter_tickets_by_code,
    filter_tickets_by_id,
    load_ticket_dataframe,
    sanitize_ticket_dataframe,
    save_ticket_dataframe,
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


def test_sanitize_ticket_dataframe_adds_missing_ui_columns_to_legacy_tickets():
    df = pd.DataFrame([{"ID": "TICKET-1009"}])

    cleaned = sanitize_ticket_dataframe(df)

    assert cleaned.iloc[0]["Issue"] == ""
    assert cleaned.iloc[0]["Resolution Status"] == "Pending"
    assert cleaned.iloc[0]["Priority"] == "Medium"


def test_ticket_dataframe_persists_across_sessions(tmp_path):
    storage_path = tmp_path / "tickets.json"
    submitted = pd.DataFrame(
        [
            {
                "ID": "TICKET-1009",
                "Issue": "Printer is offline",
                "Notes": "Checked battery",
                "Resolution Status": "Pending",
            }
        ]
    )

    save_ticket_dataframe(submitted, storage_path)
    loaded = load_ticket_dataframe(storage_path)

    assert loaded.to_dict("records") == submitted.to_dict("records")


def test_validate_supabase_url_accepts_only_project_urls():
    assert validate_supabase_url("https://project-ref.supabase.co/") == (
        "https://project-ref.supabase.co"
    )

    for invalid_url in (
        "project-ref.supabase.co",
        "https://supabase.com/dashboard/project/project-ref",
        "postgresql://postgres@db.project-ref.supabase.co:5432/postgres",
        "https://project-ref.supabase.co/rest/v1",
    ):
        try:
            validate_supabase_url(invalid_url)
        except ValueError:
            continue
        raise AssertionError(f"Expected {invalid_url} to be rejected")


def test_supabase_ticket_repository_uses_row_level_ticket_operations():
    class FakeResponse:
        data = [
            {
                "id": "TICKET-1009",
                "issue": "Printer is offline",
                "code": "IT",
                "priority": "High",
                "date_submitted": "2026-08-05 10:00:00 ET",
                "date_closed": "",
                "submitted_by": "Jordan",
                "assigned_to": "",
                "notes": "Checked battery",
                "resolution_status": "Pending",
            }
        ]

    class FakeQuery:
        def __init__(self, calls):
            self.calls = calls

        def select(self, value):
            self.calls.append(("select", value))
            return self

        def order(self, column, desc):
            self.calls.append(("order", column, desc))
            return self

        def insert(self, record):
            self.calls.append(("insert", record))
            return self

        def update(self, record):
            self.calls.append(("update", record))
            return self

        def delete(self):
            self.calls.append(("delete",))
            return self

        def eq(self, column, value):
            self.calls.append(("eq", column, value))
            return self

        def execute(self):
            self.calls.append(("execute",))
            return FakeResponse()

    class FakeClient:
        def __init__(self):
            self.calls = []

        def table(self, name):
            self.calls.append(("table", name))
            return FakeQuery(self.calls)

    client = FakeClient()
    repository = SupabaseTicketRepository(client)

    dataframe = repository.load_tickets()
    ticket = dataframe.iloc[0].to_dict()
    repository.create_ticket(ticket)
    repository.update_ticket(ticket)
    repository.delete_ticket("TICKET-1009")

    assert dataframe.iloc[0]["ID"] == "TICKET-1009"
    assert dataframe.iloc[0]["Resolution Status"] == "Pending"
    assert ("insert", {"id": "TICKET-1009", "issue": "Printer is offline", "code": "IT", "priority": "High", "date_submitted": "2026-08-05 10:00:00 ET", "date_closed": "", "submitted_by": "Jordan", "assigned_to": "", "notes": "Checked battery", "resolution_status": "Pending"}) in client.calls
    assert ("update", {"issue": "Printer is offline", "code": "IT", "priority": "High", "date_submitted": "2026-08-05 10:00:00 ET", "date_closed": "", "submitted_by": "Jordan", "assigned_to": "", "notes": "Checked battery", "resolution_status": "Pending"}) in client.calls
    assert ("delete",) in client.calls
    assert ("eq", "id", "TICKET-1009") in client.calls


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
                "Priority": "Urgent",
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
    assert calculate_urgent_open_ticket_count(df) == 1
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


def test_call_local_support_assistant_routes_ct47_to_handheld_guidance():
    reply = streamlit_app.call_local_support_assistant("My Honeywell CT47 cannot scan")

    assert "ct47" in reply.lower()
    assert "scan window" in reply.lower()


def test_call_local_support_assistant_returns_wired_network_guidance():
    reply = streamlit_app.call_local_support_assistant("Ethernet connection is down")

    assert "ethernet cable" in reply.lower()
    assert "link lights" in reply.lower()


def test_call_local_support_assistant_returns_facilities_safety_guidance():
    reply = streamlit_app.call_local_support_assistant("There is a water leak by the dock door")

    assert "safety" in reply.lower()
    assert "location" in reply.lower()


def test_get_assistant_reply_uses_github_models_when_available(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "call_github_models_support_assistant",
        lambda prompt: "Model response",
    )

    reply = streamlit_app.get_assistant_reply("printer is offline")

    assert reply == "Model response"


def test_get_assistant_reply_falls_back_to_local_assistant(monkeypatch):
    monkeypatch.setattr(
        streamlit_app, "call_github_models_support_assistant", lambda prompt: None
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
