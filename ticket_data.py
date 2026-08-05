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


def create_initial_ticket_dataframe() -> pd.DataFrame:
    """Create an empty starter dataset with no preloaded tickets."""
    return pd.DataFrame(
        columns=["ID", "Issue", "Code", "Priority", "Date Submitted", "Date Closed", "Submitted By", "Assigned To", "Notes", "Resolution Status"],
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
