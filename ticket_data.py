import datetime as dt

import pandas as pd


def get_eastern_us_timestamp() -> str:
    """Return the current timestamp formatted for Eastern US time."""
    eastern = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-4)))
    return eastern.strftime("%Y-%m-%d %H:%M:%S ET")


FAKE_TICKET_ID_PREFIXES = ("TICKET-1001", "TICKET-1002", "TICKET-1003", "TICKET-1004", "TICKET-1005", "TICKET-1006", "TICKET-1007", "TICKET-1008")


def calculate_average_open_tickets_per_week(df: pd.DataFrame) -> float:
    """Return the average number of open tickets per week based on submitted tickets."""
    if df.empty:
        return 0.0

    weekly_counts = df.groupby(pd.to_datetime(df["Date Submitted"], format="%m-%d-%Y").dt.to_period("W-MON")).size()
    return round(float(weekly_counts.mean()), 2) if not weekly_counts.empty else 0.0


def calculate_average_closed_tickets_per_week(df: pd.DataFrame) -> float:
    """Return the average number of closed tickets per week based on submitted tickets."""
    if df.empty:
        return 0.0

    weekly_counts = (
        df[df["Status"].astype(str).str.lower() == "closed"]
        .groupby(pd.to_datetime(df.loc[df["Status"].astype(str).str.lower() == "closed", "Date Submitted"], format="%m-%d-%Y").dt.to_period("W-MON"))
        .size()
    )
    return round(float(weekly_counts.mean()), 2) if not weekly_counts.empty else 0.0


def create_initial_ticket_dataframe() -> pd.DataFrame:
    """Create an empty starter dataset with no preloaded tickets."""
    return pd.DataFrame(
        columns=["ID", "Issue", "Status", "Priority", "Date Submitted", "Date Closed", "Submitted By"],
    )


def sanitize_ticket_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove fake/random ticket rows from a dataframe before displaying or counting them."""
    if df.empty:
        return df.copy()

    cleaned = df[~df["ID"].astype(str).str.startswith(FAKE_TICKET_ID_PREFIXES)].copy()
    return cleaned.reset_index(drop=True)


def delete_ticket_by_id(df: pd.DataFrame, ticket_id: str) -> pd.DataFrame:
    """Remove the row matching the provided ticket ID."""
    if df.empty:
        return df.copy()

    return df[df["ID"].astype(str) != ticket_id].reset_index(drop=True)


def filter_tickets_by_id(df: pd.DataFrame, ticket_id_query: str) -> pd.DataFrame:
    """Return only the rows whose ticket IDs match the provided search text."""
    if df.empty or not ticket_id_query:
        return df.copy()

    return df[
        df["ID"].astype(str).str.contains(ticket_id_query, case=False, na=False)
    ].reset_index(drop=True)
