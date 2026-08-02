import pandas as pd

import streamlit_app
from ticket_data import (
    calculate_average_closed_tickets_per_week,
    calculate_average_open_tickets_per_week,
    create_initial_ticket_dataframe,
    delete_ticket_by_id,
    filter_tickets_by_id,
    sanitize_ticket_dataframe,
)


def test_create_initial_ticket_dataframe_starts_empty():
    df = create_initial_ticket_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["ID", "Issue", "Status", "Priority", "Date Submitted"]
    assert df.empty


def test_sanitize_ticket_dataframe_removes_fake_ticket_ids():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1001",
                "Issue": "fake",
                "Status": "Open",
                "Priority": "High",
                "Date Submitted": "2024-01-01",
            },
            {
                "ID": "TICKET-1009",
                "Issue": "real",
                "Status": "Open",
                "Priority": "Medium",
                "Date Submitted": "2024-05-01",
            },
        ]
    )

    cleaned = sanitize_ticket_dataframe(df)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["ID"] == "TICKET-1009"


def test_delete_ticket_by_id_removes_the_requested_row():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1009",
                "Issue": "first",
                "Status": "Open",
                "Priority": "High",
                "Date Submitted": "2024-05-01",
            },
            {
                "ID": "TICKET-1010",
                "Issue": "second",
                "Status": "Closed",
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
                "Status": "Open",
                "Priority": "High",
                "Date Submitted": "2024-05-01",
            },
            {
                "ID": "TICKET-1010",
                "Issue": "second",
                "Status": "Closed",
                "Priority": "Low",
                "Date Submitted": "2024-05-02",
            },
        ]
    )

    filtered = filter_tickets_by_id(df, "ticket-1010")

    assert len(filtered) == 1
    assert filtered.iloc[0]["ID"] == "TICKET-1010"


def test_calculate_average_open_tickets_per_week_uses_ticket_history():
    df = pd.DataFrame(
        [
            {
                "ID": "TICKET-1011",
                "Issue": "one",
                "Status": "Open",
                "Priority": "High",
                "Date Submitted": "08-02-2026",
            },
            {
                "ID": "TICKET-1012",
                "Issue": "two",
                "Status": "Closed",
                "Priority": "Medium",
                "Date Submitted": "08-09-2026",
            },
            {
                "ID": "TICKET-1013",
                "Issue": "three",
                "Status": "Open",
                "Priority": "Low",
                "Date Submitted": "08-16-2026",
            },
        ]
    )

    assert calculate_average_open_tickets_per_week(df) == 1.0
    assert calculate_average_closed_tickets_per_week(df) == 1.0


def test_call_local_support_assistant_returns_printer_guidance():
    reply = streamlit_app.call_local_support_assistant("printer is offline")

    assert "printer" in reply.lower()


def test_format_stat_value_rounds_to_two_decimals():
    assert streamlit_app.format_stat_value(3) == "3.00"
    assert streamlit_app.format_stat_value(3.456) == "3.46"
