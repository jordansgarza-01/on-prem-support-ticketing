from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from ticket_data import create_initial_ticket_dataframe


DISPLAY_TO_DATABASE_COLUMNS = {
    "ID": "id",
    "Issue": "issue",
    "Code": "code",
    "Priority": "priority",
    "Date Submitted": "date_submitted",
    "Due Date": "due_date",
    "Date Closed": "date_closed",
    "Submitted By": "submitted_by",
    "Assigned To": "assigned_to",
    "Notes": "notes",
    "Resolution Status": "resolution_status",
}
DATABASE_TO_DISPLAY_COLUMNS = {
    database_name: display_name
    for display_name, database_name in DISPLAY_TO_DATABASE_COLUMNS.items()
}


def validate_supabase_url(value: str) -> str:
    """Return a valid Supabase Project URL without a trailing slash."""
    url = str(value).strip().rstrip("/")
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".supabase.co")
        or parsed.path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "SUPABASE_URL must be the HTTPS Project URL in the form "
            "https://<project-ref>.supabase.co."
        )
    return url


def ticket_records_to_dataframe(records: list[Mapping[str, Any]]) -> pd.DataFrame:
    """Convert Supabase ticket records into the dataframe used by the UI."""
    if not records:
        return create_initial_ticket_dataframe()

    dataframe = pd.DataFrame(records).rename(columns=DATABASE_TO_DISPLAY_COLUMNS)
    for column in DISPLAY_TO_DATABASE_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""
    return dataframe[list(DISPLAY_TO_DATABASE_COLUMNS)].fillna("")


def ticket_row_to_record(ticket: Mapping[str, Any]) -> dict[str, str]:
    """Convert a UI ticket row into the database record shape."""
    record: dict[str, str] = {}
    for display_name, database_name in DISPLAY_TO_DATABASE_COLUMNS.items():
        value = ticket.get(display_name, "")
        record[database_name] = "" if pd.isna(value) else str(value)
    return record


COMMENT_DISPLAY_TO_DATABASE_COLUMNS = {
    "comment_id": "id",
    "parent_id": "parent_id",
    "ticket_id": "ticket_id",
    "username": "username",
    "comment": "comment",
    "timestamp": "timestamp",
    "likes": "likes",
}
COMMENT_DATABASE_TO_DISPLAY_COLUMNS = {
    database_name: display_name
    for display_name, database_name in COMMENT_DISPLAY_TO_DATABASE_COLUMNS.items()
}


def comment_records_to_list(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Convert Supabase comment records into the list-of-dict shape used by the UI."""
    comments: list[dict[str, Any]] = []
    for record in records:
        comment: dict[str, Any] = {}
        for database_name, display_name in COMMENT_DATABASE_TO_DISPLAY_COLUMNS.items():
            value = record.get(database_name)
            if display_name == "likes":
                comment[display_name] = list(value) if value else []
            elif display_name == "parent_id":
                comment[display_name] = value or None
            else:
                comment[display_name] = "" if value is None else value
        comments.append(comment)
    return comments


def comment_to_record(comment: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a UI comment dict into the database record shape."""
    record: dict[str, Any] = {}
    for display_name, database_name in COMMENT_DISPLAY_TO_DATABASE_COLUMNS.items():
        value = comment.get(display_name)
        record[database_name] = list(value) if display_name == "likes" and value else value
    return record


class SupabaseTicketRepository:
    """Persist tickets through the Supabase table API."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def load_tickets(self) -> pd.DataFrame:
        response = (
            self._client.table("tickets")
            .select("*")
            .order("date_submitted", desc=True)
            .execute()
        )
        return ticket_records_to_dataframe(response.data or [])

    def create_ticket(self, ticket: Mapping[str, Any]) -> None:
        self._client.table("tickets").insert(ticket_row_to_record(ticket)).execute()

    def update_ticket(self, ticket: Mapping[str, Any]) -> None:
        record = ticket_row_to_record(ticket)
        ticket_id = record.pop("id")
        self._client.table("tickets").update(record).eq("id", ticket_id).execute()

    def delete_ticket(self, ticket_id: str) -> None:
        self._client.table("tickets").delete().eq("id", ticket_id).execute()

    def load_comments(self) -> list[dict[str, Any]]:
        response = (
            self._client.table("ticket_comments")
            .select("*")
            .order("timestamp")
            .execute()
        )
        return comment_records_to_list(response.data or [])

    def create_comment(self, comment: Mapping[str, Any]) -> None:
        self._client.table("ticket_comments").insert(comment_to_record(comment)).execute()

    def update_comment_likes(self, comment_id: str, likes: list[str]) -> None:
        self._client.table("ticket_comments").update({"likes": list(likes)}).eq("id", comment_id).execute()

    def delete_comments(self, comment_ids: list[str]) -> None:
        if not comment_ids:
            return
        self._client.table("ticket_comments").delete().in_("id", list(comment_ids)).execute()