import datetime as dt
from pathlib import Path

import pandas as pd


def get_eastern_us_timestamp() -> str:
    """Return the current timestamp formatted for Eastern US time."""
    eastern = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-4)))
    return eastern.strftime("%Y-%m-%d %H:%M:%S ET")


FAKE_TICKET_ID_PREFIXES = ("TICKET-1001", "TICKET-1002", "TICKET-1003", "TICKET-1004", "TICKET-1005", "TICKET-1006", "TICKET-1007", "TICKET-1008")
TICKET_CODES = ("IT", "CI", "Maintenance", "Custodial")


def _get_resolution_status_column(df: pd.DataFrame) -> str | None:
    """Return the supported resolution status column name for a dataframe."""
    if "Resolution Status" in df.columns:
        return "Resolution Status"
    if "Ticket Status" in df.columns:
        return "Ticket Status"
    return None


def _parse_date_column(df: pd.DataFrame, date_column: str) -> pd.Series:
    """Parse a ticket date column, accepting display timestamps and invalid values."""
    if date_column not in df.columns:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

    date_values = df[date_column].astype("string").str.replace(
        r"\s(?:ET|EST|EDT)$", "", regex=True
    )
    return pd.to_datetime(date_values, format="mixed", errors="coerce")


def _get_weekly_counts(df: pd.DataFrame, date_column: str) -> pd.Series:
    """Return weekly counts for the provided date column after dropping invalid dates."""
    if df.empty or date_column not in df.columns:
        return pd.Series(dtype="int64")

    parsed_dates = _parse_date_column(df, date_column)
    valid_dates = parsed_dates.notna()
    if not valid_dates.any():
        return pd.Series(dtype="int64")

    weekly_periods = parsed_dates[valid_dates].dt.to_period("W-MON")
    return weekly_periods.value_counts().sort_index()


def calculate_average_open_tickets_per_week(df: pd.DataFrame) -> float:
    """Return the average number of open tickets per week based on submitted tickets."""
    if df.empty:
        return 0.0

    weekly_counts = _get_weekly_counts(df, "Date Submitted")
    return round(float(weekly_counts.mean()), 2) if not weekly_counts.empty else 0.0


def calculate_average_closed_tickets_per_week(df: pd.DataFrame) -> float:
    """Return the average number of closed tickets per week based on submitted tickets."""
    if df.empty:
        return 0.0

    status_column = _get_resolution_status_column(df)
    if status_column is None:
        return 0.0

    resolved_df = df[df[status_column].astype(str).str.lower() == "resolved"]
    weekly_counts = _get_weekly_counts(resolved_df, "Date Submitted")
    return round(float(weekly_counts.mean()), 2) if not weekly_counts.empty else 0.0


def calculate_open_ticket_count(df: pd.DataFrame) -> int:
    """Return the number of tickets that have not been resolved."""
    status_column = _get_resolution_status_column(df)
    if df.empty or status_column is None:
        return 0

    return int((df[status_column].astype(str).str.lower() != "resolved").sum())


def calculate_urgent_open_ticket_count(df: pd.DataFrame) -> int:
    """Return the number of unresolved tickets with Urgent priority."""
    status_column = _get_resolution_status_column(df)
    if df.empty or status_column is None or "Priority" not in df.columns:
        return 0

    is_open = df[status_column].astype(str).str.lower() != "resolved"
    is_urgent = df["Priority"].astype(str).str.lower() == "urgent"
    return int((is_open & is_urgent).sum())


def calculate_resolution_rate(df: pd.DataFrame) -> float:
    """Return the percentage of tickets marked resolved."""
    status_column = _get_resolution_status_column(df)
    if df.empty or status_column is None:
        return 0.0

    resolved_count = (df[status_column].astype(str).str.lower() == "resolved").sum()
    return round(float(resolved_count / len(df) * 100), 2)


def calculate_average_resolution_time_hours(df: pd.DataFrame) -> float:
    """Return average elapsed hours from submission to resolution for valid closed tickets."""
    status_column = _get_resolution_status_column(df)
    if (
        df.empty
        or status_column is None
        or "Date Submitted" not in df.columns
        or "Date Closed" not in df.columns
    ):
        return 0.0

    submitted_dates = _parse_date_column(df, "Date Submitted")
    closed_dates = _parse_date_column(df, "Date Closed")
    resolution_hours = (closed_dates - submitted_dates).dt.total_seconds() / 3600
    is_resolved = df[status_column].astype(str).str.lower() == "resolved"
    valid_resolution_hours = resolution_hours[is_resolved & (resolution_hours >= 0)]
    return round(float(valid_resolution_hours.mean()), 2) if not valid_resolution_hours.empty else 0.0


def calculate_due_date(submitted_at: str, days: int = 7) -> str:
    """Return a due-date timestamp `days` after the given submission timestamp."""
    cleaned_submitted_at = str(submitted_at).strip()
    parsed = pd.to_datetime(
        cleaned_submitted_at.replace(" ET", ""), format="mixed", errors="coerce"
    )
    if pd.isna(parsed):
        parsed = dt.datetime.now()
    due = parsed + dt.timedelta(days=days)
    return due.strftime("%Y-%m-%d %H:%M:%S ET")


def calculate_stale_open_ticket_flags(df: pd.DataFrame, days: int = 7) -> pd.Series:
    """Return a boolean Series flagging unresolved tickets open for `days` or more."""
    status_column = _get_resolution_status_column(df)
    if df.empty or status_column is None:
        return pd.Series(False, index=df.index, dtype=bool)

    submitted_dates = _parse_date_column(df, "Date Submitted")
    days_open = (pd.Timestamp.now() - submitted_dates).dt.total_seconds() / 86400
    is_open = df[status_column].astype(str).str.lower() != "resolved"
    return is_open & (days_open >= days)


def calculate_past_due_labels(df: pd.DataFrame, days: int = 7) -> pd.Series:
    """Return per-row Past Due labels: 'Flagged' for stale open tickets, 'N/A' for
    tickets closed within the `days` threshold, and '' otherwise."""
    if df.empty:
        return pd.Series("", index=df.index, dtype="object")

    status_column = _get_resolution_status_column(df)
    if status_column is None:
        return pd.Series("", index=df.index, dtype="object")

    is_open = df[status_column].astype(str).str.lower() != "resolved"
    submitted_dates = _parse_date_column(df, "Date Submitted")
    closed_dates = _parse_date_column(df, "Date Closed")
    days_to_close = (closed_dates - submitted_dates).dt.total_seconds() / 86400
    closed_within_threshold = (~is_open) & closed_dates.notna() & (days_to_close < days)

    labels = pd.Series("", index=df.index, dtype="object")
    labels[calculate_stale_open_ticket_flags(df, days=days)] = "Flagged"
    labels[closed_within_threshold] = "N/A"
    return labels


def calculate_overdue_ticket_count(df: pd.DataFrame) -> int:
    """Return the count of unresolved tickets whose Due Date has already passed."""
    status_column = _get_resolution_status_column(df)
    if df.empty or status_column is None or "Due Date" not in df.columns:
        return 0

    due_dates = _parse_date_column(df, "Due Date")
    is_open = df[status_column].astype(str).str.lower() != "resolved"
    is_past_due = due_dates.notna() & (due_dates < pd.Timestamp.now())
    return int((is_open & is_past_due).sum())


def calculate_on_time_close_rate(df: pd.DataFrame) -> float:
    """Return the percentage of resolved tickets closed on or before their Due Date."""
    status_column = _get_resolution_status_column(df)
    if (
        df.empty
        or status_column is None
        or "Due Date" not in df.columns
        or "Date Closed" not in df.columns
    ):
        return 0.0

    is_resolved = df[status_column].astype(str).str.lower() == "resolved"
    due_dates = _parse_date_column(df, "Due Date")
    closed_dates = _parse_date_column(df, "Date Closed")
    eligible = is_resolved & due_dates.notna() & closed_dates.notna()
    if not eligible.any():
        return 0.0

    on_time = eligible & (closed_dates <= due_dates)
    return round(float(on_time.sum() / eligible.sum() * 100), 2)


def build_open_tickets_pdf(df: pd.DataFrame) -> bytes:
    """Render open (non-resolved) tickets into a printable PDF table and return its bytes."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    styles = getSampleStyleSheet()
    elements: list = [Paragraph("Open Tickets", styles["Title"])]

    columns = [
        "ID",
        "Issue",
        "Code",
        "Priority",
        "Date Submitted",
        "Due Date",
        "Assigned To",
        "Resolution Status",
    ]
    available_columns = [column for column in columns if column in df.columns]

    if df.empty or not available_columns:
        elements.append(Paragraph("No open tickets.", styles["Normal"]))
    else:
        table_rows = [available_columns]
        for _, ticket in df[available_columns].iterrows():
            table_rows.append(
                [
                    Paragraph(str(ticket[column]), styles["BodyText"])
                    if column == "Issue"
                    else str(ticket[column])
                    for column in available_columns
                ]
            )

        table = Table(table_rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7A1F2D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F7F7F7")],
                    ),
                ]
            )
        )
        elements.append(table)

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(letter), title="Open Tickets")
    document.build(elements)
    return buffer.getvalue()


def create_initial_ticket_dataframe() -> pd.DataFrame:
    """Create an empty starter dataset with no preloaded tickets."""
    return pd.DataFrame(
        columns=["ID", "Issue", "Code", "Priority", "Date Submitted", "Due Date", "Date Closed", "Submitted By", "Assigned To", "Notes", "Resolution Status"],
    )


def load_ticket_dataframe(storage_path: Path) -> pd.DataFrame:
    """Load tickets from persistent storage, returning an empty dataset when absent."""
    if not storage_path.exists():
        return create_initial_ticket_dataframe()

    try:
        return pd.read_json(storage_path, orient="records", convert_dates=False)
    except (OSError, ValueError):
        return create_initial_ticket_dataframe()


def save_ticket_dataframe(df: pd.DataFrame, storage_path: Path) -> None:
    """Atomically persist the current ticket dataframe for future sessions."""
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = storage_path.with_suffix(".tmp")
    df.to_json(temporary_path, orient="records", indent=2)
    temporary_path.replace(storage_path)


def sanitize_ticket_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove fake/random ticket rows from a dataframe before displaying or counting them."""
    if df.empty or "ID" not in df.columns:
        return df.copy()

    ticket_ids = df["ID"].fillna("").astype(str)
    cleaned = df[~ticket_ids.str.startswith(FAKE_TICKET_ID_PREFIXES, na=False)].copy()
    defaults = {
        "Issue": "",
        "Priority": "Medium",
        "Date Submitted": "",
        "Due Date": "",
        "Date Closed": "",
        "Submitted By": "Unknown",
        "Assigned To": "",
        "Notes": "",
        "Resolution Status": "Pending",
    }
    for column, default_value in defaults.items():
        if column not in cleaned.columns:
            cleaned[column] = default_value
    if "Code" not in cleaned.columns:
        cleaned["Code"] = "IT"
    else:
        codes = cleaned["Code"].astype("string").str.strip()
        cleaned["Code"] = codes.where(codes.isin(TICKET_CODES), "IT")
    date_closed = cleaned["Date Closed"].astype("string")
    cleaned["Date Closed"] = date_closed.mask(
        date_closed.str.strip().str.lower() == "empty", ""
    )
    due_date_missing = cleaned["Due Date"].astype("string").fillna("").str.strip() == ""
    if due_date_missing.any():
        cleaned.loc[due_date_missing, "Due Date"] = cleaned.loc[
            due_date_missing, "Date Submitted"
        ].apply(lambda submitted: calculate_due_date(submitted) if str(submitted).strip() else "")
    return cleaned.reset_index(drop=True)


def delete_ticket_by_id(df: pd.DataFrame, ticket_id: str) -> pd.DataFrame:
    """Remove the row matching the provided ticket ID."""
    if df.empty or "ID" not in df.columns:
        return df.copy()

    return df[df["ID"].astype(str) != ticket_id].reset_index(drop=True)


def filter_tickets_by_id(df: pd.DataFrame, ticket_id_query: str) -> pd.DataFrame:
    """Return only the rows whose ticket IDs match the provided search text."""
    if df.empty or not ticket_id_query or "ID" not in df.columns:
        return df.copy()

    return df[
        df["ID"].astype(str).str.contains(ticket_id_query, case=False, na=False)
    ].reset_index(drop=True)


def filter_tickets_by_code(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """Return tickets for the selected code, or all tickets when no code is selected."""
    if df.empty or not code or code == "All" or "Code" not in df.columns:
        return df.copy()

    return df[df["Code"].astype(str).str.casefold() == code.casefold()].reset_index(
        drop=True
    )
