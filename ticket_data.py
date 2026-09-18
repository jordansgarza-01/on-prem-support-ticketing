import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd


def get_eastern_us_timestamp() -> str:
    """Return the current timestamp formatted for Eastern US time."""
    eastern = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-4)))
    return eastern.strftime("%Y-%m-%d %H:%M:%S ET")


FAKE_TICKET_ID_PREFIXES = ("TICKET-1001", "TICKET-1002", "TICKET-1003", "TICKET-1004", "TICKET-1005", "TICKET-1006", "TICKET-1007", "TICKET-1008")
TICKET_CODES = ("IT", "CI", "MHE", "Maintenance", "Custodial")
ASSIGNEES = ("Jordan Garza", "Tanner Bourgeois", "Gary Lewis")
PERFORMANCE_TREND_METRICS = ("Tickets Submitted", "Tickets Resolved", "Average Resolution Time (hours)")


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


# Two-tailed 95% t-distribution critical values by degrees of freedom (1-30); falls back
# to the normal approximation (1.96) beyond that, avoiding a scipy dependency.
_T_CRITICAL_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
    30: 2.042,
}


def _t_critical_95(degrees_of_freedom: int) -> float:
    """Return the two-tailed 95% t critical value for the given degrees of freedom."""
    if degrees_of_freedom < 1:
        return 1.96
    return _T_CRITICAL_95.get(degrees_of_freedom, 1.96)


def calculate_daily_metric_series(df: pd.DataFrame, metric: str) -> pd.Series:
    """Return a date-indexed daily series for the requested performance metric."""
    if df.empty:
        return pd.Series(dtype="float64")

    if metric == "Tickets Submitted":
        submitted_dates = _parse_date_column(df, "Date Submitted").dt.normalize()
        valid_dates = submitted_dates.dropna()
        if valid_dates.empty:
            return pd.Series(dtype="float64")
        return valid_dates.value_counts().sort_index().astype(float)

    status_column = _get_resolution_status_column(df)
    if status_column is None:
        return pd.Series(dtype="float64")
    resolved_df = df[df[status_column].astype(str).str.lower() == "resolved"]

    if metric == "Tickets Resolved":
        closed_dates = _parse_date_column(resolved_df, "Date Closed").dt.normalize()
        valid_dates = closed_dates.dropna()
        if valid_dates.empty:
            return pd.Series(dtype="float64")
        return valid_dates.value_counts().sort_index().astype(float)

    if metric == "Average Resolution Time (hours)":
        submitted_dates = _parse_date_column(resolved_df, "Date Submitted")
        closed_dates = _parse_date_column(resolved_df, "Date Closed")
        resolution_hours = (closed_dates - submitted_dates).dt.total_seconds() / 3600
        valid = closed_dates.notna() & resolution_hours.notna() & (resolution_hours >= 0)
        if not valid.any():
            return pd.Series(dtype="float64")
        day_index = closed_dates[valid].dt.normalize()
        return pd.Series(resolution_hours[valid].to_numpy(), index=day_index).groupby(level=0).mean().sort_index()

    return pd.Series(dtype="float64")


def calculate_performance_trend(df: pd.DataFrame, metric: str, forecast_days: int = 7) -> pd.DataFrame:
    """Build a 7-day moving average trend with a forward-looking multiple linear
    regression (MLR) forecast and its 95% confidence interval.

    The MLR model regresses the moving average against a day-index trend term plus
    sine/cosine day-of-week terms (weekly seasonality), giving more than one predictor.
    Returns a DataFrame with one row per day (historical, then forecast) with columns:
    date, value, moving_average, mlr_line, ci_lower, ci_upper, segment.
    """
    empty_columns = ["date", "value", "moving_average", "mlr_line", "ci_lower", "ci_upper", "segment"]
    daily_series = calculate_daily_metric_series(df, metric)
    if daily_series.empty:
        return pd.DataFrame(columns=empty_columns)

    full_index = pd.date_range(daily_series.index.min(), daily_series.index.max(), freq="D")
    daily_series = daily_series.reindex(full_index)
    if metric == "Average Resolution Time (hours)":
        daily_series = daily_series.interpolate(limit_direction="both")
    daily_series = daily_series.fillna(0.0)

    moving_average = daily_series.rolling(window=7, min_periods=1).mean()

    n = len(daily_series)
    day_index = np.arange(n, dtype=float)
    weekday = full_index.weekday.to_numpy(dtype=float)
    design = np.column_stack(
        [
            np.ones(n),
            day_index,
            np.sin(2 * np.pi * weekday / 7),
            np.cos(2 * np.pi * weekday / 7),
        ]
    )
    target = moving_average.to_numpy(dtype=float)

    has_model = n >= design.shape[1] + 1
    if has_model:
        coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
        fitted = design @ coefficients
        residual_degrees_of_freedom = max(n - design.shape[1], 1)
        residual_variance = float(np.sum((target - fitted) ** 2) / residual_degrees_of_freedom)
        xtx_inv = np.linalg.pinv(design.T @ design)
        t_critical = _t_critical_95(residual_degrees_of_freedom)

    rows = []
    for i, date in enumerate(full_index):
        rows.append(
            {
                "date": date,
                "value": float(daily_series.iloc[i]),
                "moving_average": float(moving_average.iloc[i]),
                "mlr_line": float(fitted[i]) if has_model else None,
                "ci_lower": None,
                "ci_upper": None,
                "segment": "historical",
            }
        )

    if has_model:
        last_weekday = int(full_index[-1].weekday())
        for step in range(1, forecast_days + 1):
            future_day_index = float(n - 1 + step)
            future_weekday = (last_weekday + step) % 7
            x0 = np.array(
                [
                    1.0,
                    future_day_index,
                    np.sin(2 * np.pi * future_weekday / 7),
                    np.cos(2 * np.pi * future_weekday / 7),
                ]
            )
            predicted = float(x0 @ coefficients)
            standard_error = float(np.sqrt(max(residual_variance * (x0 @ xtx_inv @ x0), 0.0)))
            margin = t_critical * standard_error
            rows.append(
                {
                    "date": full_index[-1] + pd.Timedelta(days=step),
                    "value": None,
                    "moving_average": None,
                    "mlr_line": predicted,
                    "ci_lower": predicted - margin,
                    "ci_upper": predicted + margin,
                    "segment": "forecast",
                }
            )

    return pd.DataFrame(rows, columns=empty_columns)


def _build_tickets_table_pdf(title: str, df: pd.DataFrame, empty_message: str) -> bytes:
    """Render a ticket table with the given title into a printable PDF and return its bytes."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    styles = getSampleStyleSheet()
    elements: list = [Paragraph(title, styles["Title"])]

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
        elements.append(Paragraph(empty_message, styles["Normal"]))
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
    document = SimpleDocTemplate(buffer, pagesize=landscape(letter), title=title)
    document.build(elements)
    return buffer.getvalue()


def build_assignee_tickets_pdf(df: pd.DataFrame, assignees: tuple[str, ...] = ASSIGNEES) -> bytes:
    """Render all tickets assigned to any of the given people into a printable PDF."""
    if df.empty or "Assigned To" not in df.columns:
        matching_df = df.iloc[0:0]
    else:
        assignee_names = {assignee.casefold() for assignee in assignees}
        matching_df = df[df["Assigned To"].astype(str).str.casefold().isin(assignee_names)]

    title = f"Tickets Assigned To {', '.join(assignees)}"
    return _build_tickets_table_pdf(title, matching_df, "No matching tickets.")


def _build_performance_trend_drawing(trend_df: pd.DataFrame, metric: str, width: float = 460, height: float = 260):
    """Render the performance trend (moving average + MLR forecast + 95% CI) as a
    reportlab vector Drawing, suitable for embedding directly in a PDF."""
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors

    drawing = Drawing(width, height)
    drawing.add(
        String(width / 2, height - 14, f"Performance Trend \u2014 {metric}", textAnchor="middle", fontName="Helvetica-Bold", fontSize=11)
    )

    if trend_df.empty:
        drawing.add(String(width / 2, height / 2, "No trend data available.", textAnchor="middle", fontSize=9))
        return drawing

    ordinals = [row.date.toordinal() for row in trend_df.itertuples()]
    moving_average_series = [
        (o, v) for o, v in zip(ordinals, trend_df["moving_average"]) if pd.notna(v)
    ]
    mlr_series = [(o, v) for o, v in zip(ordinals, trend_df["mlr_line"]) if pd.notna(v)]
    ci_upper_series = [(o, v) for o, v in zip(ordinals, trend_df["ci_upper"]) if pd.notna(v)]
    ci_lower_series = [(o, v) for o, v in zip(ordinals, trend_df["ci_lower"]) if pd.notna(v)]

    color_moving_average = colors.HexColor("#1f4e79")
    color_mlr = colors.HexColor("#7A1F2D")
    color_ci = colors.HexColor("#A6A6A6")

    plot = LinePlot()
    plot.x = 45
    plot.y = 40
    plot.height = height - 85
    plot.width = width - 80
    plot.data = [series for series in (moving_average_series, mlr_series, ci_upper_series, ci_lower_series) if series]

    series_index = 0
    if moving_average_series:
        plot.lines[series_index].strokeColor = color_moving_average
        plot.lines[series_index].strokeWidth = 2
        series_index += 1
    if mlr_series:
        plot.lines[series_index].strokeColor = color_mlr
        plot.lines[series_index].strokeWidth = 2
        plot.lines[series_index].strokeDashArray = [5, 3]
        series_index += 1
    if ci_upper_series:
        plot.lines[series_index].strokeColor = color_ci
        plot.lines[series_index].strokeDashArray = [2, 2]
        series_index += 1
    if ci_lower_series:
        plot.lines[series_index].strokeColor = color_ci
        plot.lines[series_index].strokeDashArray = [2, 2]
        series_index += 1

    if ordinals:
        tick_count = min(6, len(sorted(set(ordinals))))
        unique_ordinals = sorted(set(ordinals))
        step = max(len(unique_ordinals) // tick_count, 1)
        tick_values = unique_ordinals[::step]
        plot.xValueAxis.valueSteps = tick_values
        plot.xValueAxis.labelTextFormat = lambda value: dt.date.fromordinal(int(value)).strftime("%m/%d")
    plot.xValueAxis.labels.angle = 30
    plot.xValueAxis.labels.dy = -8
    plot.yValueAxis.labelTextFormat = "%0.1f"

    drawing.add(plot)

    legend = Legend()
    legend.x = width - 15
    legend.y = height - 25
    legend.dx = 7
    legend.dy = 7
    legend.fontSize = 7.5
    legend.alignment = "right"
    legend.colorNamePairs = [
        (color_moving_average, "7-Day Moving Average"),
        (color_mlr, "MLR Trend & Forecast"),
        (color_ci, "95% Confidence Interval (Forecast)"),
    ]
    drawing.add(legend)

    return drawing


def build_assignee_snapshot_pdf(
    df: pd.DataFrame, assignee: str, trend_metric: str = "Tickets Submitted"
) -> bytes:
    """Render one person's descriptive statistics and performance trend into a printable PDF."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    title = f"Statistics Snapshot: {assignee}"
    elements: list = [Paragraph(title, styles["Title"]), Spacer(1, 10)]

    assignee_tickets = filter_tickets_by_assignee(df, assignee)
    elements.append(Paragraph("Descriptive Statistics", styles["Heading2"]))
    header = [
        "Code",
        "Open",
        "Urgent Open",
        "Resolution Rate %",
        "Avg Resolution (hrs)",
        "Overdue",
        "On-Time Close %",
    ]
    table_rows = [header]
    for code_name in TICKET_CODES:
        code_tickets = filter_tickets_by_code(assignee_tickets, code_name)
        table_rows.append(
            [
                code_name,
                str(calculate_open_ticket_count(code_tickets)),
                str(calculate_urgent_open_ticket_count(code_tickets)),
                str(calculate_resolution_rate(code_tickets)),
                str(calculate_average_resolution_time_hours(code_tickets)),
                str(calculate_overdue_ticket_count(code_tickets)),
                str(calculate_on_time_close_rate(code_tickets)),
            ]
        )

    table = Table(table_rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7A1F2D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
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

    elements.append(Spacer(1, 18))
    elements.append(Paragraph("Performance Trend", styles["Heading2"]))
    trend_df = calculate_performance_trend(assignee_tickets, trend_metric)
    elements.append(_build_performance_trend_drawing(trend_df, trend_metric))

    elements.append(Spacer(1, 28))
    signature_rows = [
        ["Print:", "_" * 40],
        ["Signature:", "_" * 40],
        ["Date:", "_" * 24],
    ]
    signature_table = Table(signature_rows, colWidths=[70, 300])
    signature_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("TOPPADDING", (0, 0), (-1, -1), 16),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ]
        )
    )
    elements.append(signature_table)

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, title=title)
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


def filter_tickets_by_assignee(df: pd.DataFrame, assignee: str) -> pd.DataFrame:
    """Return tickets assigned to the given person, or all tickets when no person is selected."""
    if df.empty or not assignee or assignee == "All" or "Assigned To" not in df.columns:
        return df.copy()

    return df[
        df["Assigned To"].astype(str).str.casefold() == assignee.casefold()
    ].reset_index(drop=True)


def get_distinct_assignees(df: pd.DataFrame) -> list[str]:
    """Return sorted distinct non-blank Assigned To values found in the dataframe."""
    if df.empty or "Assigned To" not in df.columns:
        return []

    assigned = df["Assigned To"].astype("string").fillna("").str.strip()
    return sorted({value for value in assigned if value})
