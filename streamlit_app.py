import base64
import datetime
import importlib.util
import os
import sys
import uuid
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from PIL import Image

try:
    from streamlit.components.v1 import html as components_html
except ImportError:  # pragma: no cover
    components_html = None

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

try:
    from ticket_data import (
        ASSIGNEES,
        build_assignee_snapshot_pdf,
        calculate_average_resolution_time_hours,
        calculate_average_closed_tickets_per_week,
        calculate_average_open_tickets_per_week,
        calculate_due_date,
        calculate_on_time_close_rate,
        calculate_overdue_ticket_count,
        calculate_past_due_labels,
        calculate_resolution_time_trend,
        calculate_urgent_open_ticket_count,
        calculate_open_ticket_count,
        calculate_resolution_rate,
        CODE_ASSIGNEE_MAP,
        create_initial_ticket_dataframe,
        delete_ticket_by_id,
        filter_tickets_by_assignee,
        filter_tickets_by_code,
        filter_tickets_by_id,
        get_distinct_assignees,
        get_eastern_us_timestamp,
        sanitize_ticket_dataframe,
        STAFF_DIRECTORY,
        TICKET_CODES,
    )
except ImportError:
    ticket_data_spec = importlib.util.spec_from_file_location(
        "ticket_data", APP_ROOT / "ticket_data.py"
    )
    if ticket_data_spec is None or ticket_data_spec.loader is None:
        raise

    ticket_data_module = importlib.util.module_from_spec(ticket_data_spec)
    ticket_data_spec.loader.exec_module(ticket_data_module)
    ASSIGNEES = ticket_data_module.ASSIGNEES
    build_assignee_snapshot_pdf = ticket_data_module.build_assignee_snapshot_pdf
    calculate_average_resolution_time_hours = (
        ticket_data_module.calculate_average_resolution_time_hours
    )
    calculate_average_closed_tickets_per_week = (
        ticket_data_module.calculate_average_closed_tickets_per_week
    )
    calculate_average_open_tickets_per_week = (
        ticket_data_module.calculate_average_open_tickets_per_week
    )
    calculate_due_date = ticket_data_module.calculate_due_date
    calculate_on_time_close_rate = ticket_data_module.calculate_on_time_close_rate
    calculate_overdue_ticket_count = ticket_data_module.calculate_overdue_ticket_count
    calculate_past_due_labels = ticket_data_module.calculate_past_due_labels
    calculate_resolution_time_trend = ticket_data_module.calculate_resolution_time_trend
    calculate_urgent_open_ticket_count = (
        ticket_data_module.calculate_urgent_open_ticket_count
    )
    calculate_open_ticket_count = ticket_data_module.calculate_open_ticket_count
    calculate_resolution_rate = ticket_data_module.calculate_resolution_rate
    CODE_ASSIGNEE_MAP = ticket_data_module.CODE_ASSIGNEE_MAP
    create_initial_ticket_dataframe = ticket_data_module.create_initial_ticket_dataframe
    delete_ticket_by_id = ticket_data_module.delete_ticket_by_id
    filter_tickets_by_assignee = ticket_data_module.filter_tickets_by_assignee
    filter_tickets_by_code = ticket_data_module.filter_tickets_by_code
    filter_tickets_by_id = ticket_data_module.filter_tickets_by_id
    get_distinct_assignees = ticket_data_module.get_distinct_assignees
    sanitize_ticket_dataframe = ticket_data_module.sanitize_ticket_dataframe
    STAFF_DIRECTORY = ticket_data_module.STAFF_DIRECTORY
    TICKET_CODES = ticket_data_module.TICKET_CODES

from ticket_repository import SupabaseTicketRepository, validate_supabase_url

# Show app title and description.
BRAND_COLORS = ["#111111", "#D9D9D9", "#7A1F2D"]

FAVICON_PATH = APP_ROOT / "O&M (3).png"
FAVICON = Image.open(FAVICON_PATH) if FAVICON_PATH.exists() else "💻"

st.set_page_config(
    page_title="DC05 ISP",
    page_icon=FAVICON,
)

if components_html is not None:
    components_html(
        """
        <script>
        const parentDocument = window.parent.document;
        const setPageTitle = () => {
            if (parentDocument.title !== 'DC05 ISP') {
                parentDocument.title = 'DC05 ISP';
            }
        };
        setPageTitle();
        new MutationObserver(setPageTitle).observe(parentDocument.querySelector('title'), {
            childList: true,
            subtree: true,
        });
        </script>
        """,
        height=0,
        width=0,
    )

DEEP_BURGUNDY = "#7A1F2D"
DARK_SLATE_CHARCOAL = "#2F3A3F"

st.markdown(
    f"""
    <style>
    ::selection {{ background-color: {DEEP_BURGUNDY}; color: #ffffff; }}
    input:focus, textarea:focus {{ border-color: {DEEP_BURGUNDY} !important; box-shadow: 0 0 0 1px {DEEP_BURGUNDY} !important; }}
    [data-baseweb="select"] > div:focus-within {{ border-color: {DEEP_BURGUNDY} !important; box-shadow: 0 0 0 1px {DEEP_BURGUNDY} !important; }}
    [data-baseweb="menu"] li:hover, [data-baseweb="menu"] li[aria-selected="true"] {{ background-color: {DARK_SLATE_CHARCOAL} !important; }}
    input[type="checkbox"], input[type="radio"] {{ accent-color: {DEEP_BURGUNDY}; }}
    [data-testid="InputInstructions"], [data-testid="stTextInputInstructions"], [data-testid="stTextAreaInstructions"], [data-testid="stWidgetInstructions"] {{ display: none !important; visibility: hidden !important; }}
    [data-testid="stDataFrame"] [aria-colindex="2"], [data-testid="stDataFrame"] [aria-colindex="2"] *,
    [data-testid="stDataFrame"] [aria-colindex="10"], [data-testid="stDataFrame"] [aria-colindex="10"] * {{ white-space: pre-wrap !important; overflow-wrap: anywhere !important; overflow-y: auto !important; max-height: 180px !important; display: block !important; }}
    [data-testid="stMetric"], [data-testid="stMetric"] > div {{ min-width: 0 !important; }}
    [data-testid="stMetricLabel"] {{ display: block !important; max-width: 100% !important; white-space: pre-line !important; overflow-wrap: anywhere !important; line-height: 1.25 !important; }}
    [data-testid="stMetricValue"] {{ font-size: 1rem !important; white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.2 !important; }}
    [data-testid="stMetricValue"] > div {{ overflow: visible !important; text-overflow: clip !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Avoid runtime issues when the app is launched in a headless/container environment.
if not st.runtime.exists():
    st.session_state.setdefault("_headless_runtime", True)

APP_PASSWORD = "Platinum2025"
INTERNAL_MANAGEMENT_PASSWORD = "ServiceStats01@!"
TICKET_MANAGEMENT_PASSWORD = "ULSDfuelHC01@$$"


# Navigation/login state changes are done via on_click callbacks (run before the script
# reruns) rather than inline `if st.button(...): ... st.rerun()`, since the latter pattern
# is unreliable for widgets nested inside st.popover.
def _go_to_view(view_name: str) -> None:
    st.session_state.current_view = view_name


def _go_home_from_my_tickets() -> None:
    st.session_state.current_view = "home"
    st.session_state.my_tickets_person = None
    st.session_state.pop("my_tickets_person_selectbox", None)


def _attempt_internal_management_login() -> None:
    if st.session_state.get("ism_password_input", "") == INTERNAL_MANAGEMENT_PASSWORD:
        st.session_state.internal_management_authenticated = True
        st.session_state.current_view = "internal_management"
        st.session_state.ism_login_error = False
        st.session_state.pop("ism_password_input", None)
    else:
        st.session_state.ism_login_error = True


def _attempt_ticket_management_login() -> None:
    if st.session_state.get("tm_password_input", "") == TICKET_MANAGEMENT_PASSWORD:
        st.session_state.ticket_management_authenticated = True
        st.session_state.current_view = "ticket_management"
        st.session_state.tm_login_error = False
        st.session_state.pop("tm_password_input", None)
    else:
        st.session_state.tm_login_error = True


if not st.session_state.get("authenticated", False):
    st.markdown(
        f"<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: {DEEP_BURGUNDY};'>P&HS | Internal Support Portal</h1></div>",
        unsafe_allow_html=True,
    )
    entered_password = st.text_input("Password", type="password")
    login_clicked = st.button("Log in", type="primary")
    if login_clicked:
        if entered_password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("The password you entered is incorrect. Please try again.")
    st.stop()

st.session_state.setdefault("current_view", "home")

st.markdown(
    f"<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: {DEEP_BURGUNDY}; white-space: nowrap; overflow-x: auto;'>P&HS | Internal Support Portal</h1></div>",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <style>
    .st-key-my_tickets_portal button, .st-key-internal_management_portal button, .st-key-ticket_management_portal button {{
        background-color: {DEEP_BURGUNDY} !important;
        color: #ffffff !important;
        border: 1px solid {DEEP_BURGUNDY} !important;
        white-space: nowrap !important;
    }}
    .st-key-internal_management_portal button {{
        padding-left: 1.25rem !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

(
    header_my_tickets_col,
    header_ism_col,
    header_ticket_mgmt_col,
    header_spacer_right,
) = st.columns([1.6, 2.7, 2.2, 1.3])

with header_my_tickets_col:
    with st.container(key="my_tickets_portal"):
        with st.popover("My Tickets", use_container_width=True):
            selected_my_tickets_person = st.selectbox(
                "Select your name to view My Tickets",
                ["-- Select your name --", *STAFF_DIRECTORY],
                key="my_tickets_person_selectbox",
            )
            if selected_my_tickets_person != "-- Select your name --":
                st.session_state.my_tickets_person = selected_my_tickets_person
                st.session_state.current_view = "my_tickets"
                del st.session_state["my_tickets_person_selectbox"]
                st.rerun()

with header_ism_col:
    with st.container(key="internal_management_portal"):
        with st.popover("Performance Management", use_container_width=True):
            if st.session_state.get("internal_management_authenticated", False):
                st.button(
                    "Open Performance Management",
                    key="ism_open_button",
                    on_click=_go_to_view,
                    args=("internal_management",),
                )
            else:
                st.text_input("Password", type="password", key="ism_password_input")
                st.button("Log in", key="ism_unlock_button", on_click=_attempt_internal_management_login)
                if st.session_state.pop("ism_login_error", False):
                    st.error("The password you entered is incorrect. Please try again.")

with header_ticket_mgmt_col:
    with st.container(key="ticket_management_portal"):
        with st.popover("Ticket Management", use_container_width=True):
            if st.session_state.get("ticket_management_authenticated", False):
                st.button(
                    "Open Ticket Management",
                    key="tm_open_button",
                    on_click=_go_to_view,
                    args=("ticket_management",),
                )
            else:
                st.text_input("Password", type="password", key="tm_password_input")
                st.button("Log in", key="tm_unlock_button", on_click=_attempt_ticket_management_login)
                if st.session_state.pop("tm_login_error", False):
                    st.error("The password you entered is incorrect. Please try again.")

st.write("Please use this system to request assistance.")

# Bump this whenever SupabaseTicketRepository's public interface changes, so the
# cached resource below is rebuilt instead of reusing a stale pre-change instance.
_TICKET_REPOSITORY_VERSION = 2


@st.cache_resource(show_spinner=False)
def get_ticket_repository(repository_version: int = _TICKET_REPOSITORY_VERSION) -> SupabaseTicketRepository:
    """Create the server-side Supabase repository from Streamlit secrets."""
    try:
        from supabase import create_client

        return SupabaseTicketRepository(
            create_client(
                validate_supabase_url(st.secrets["SUPABASE_URL"]),
                st.secrets["SUPABASE_SERVICE_ROLE_KEY"],
            )
        )
    except KeyError as exc:
        raise RuntimeError(
            "Supabase is not configured. Add SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY to Streamlit secrets."
        ) from exc


# Create the shared ticket dataframe and refresh it for each browser session.
TICKET_DATA_VERSION = 5
if (
    "df" not in st.session_state
    or "ticket_data_version" not in st.session_state
    or st.session_state.ticket_data_version != TICKET_DATA_VERSION
):
    try:
        st.session_state.df = get_ticket_repository().load_tickets()
    except Exception as exc:
        st.session_state.df = create_initial_ticket_dataframe()
        if "Name or service not known" in str(exc):
            st.error(
                "Supabase could not be reached. In Streamlit Secrets, replace "
                "SUPABASE_URL with the exact HTTPS Project URL copied from "
                "Supabase Project Settings > API."
            )
        else:
            st.error(f"Unable to load tickets from Supabase: {exc}")
        st.stop()
    st.session_state.ticket_data_version = TICKET_DATA_VERSION

st.session_state.df = sanitize_ticket_dataframe(st.session_state.df)
if "Resolution Status" not in st.session_state.df.columns and "Ticket Status" in st.session_state.df.columns:
    st.session_state.df = st.session_state.df.rename(columns={"Ticket Status": "Resolution Status"})

if "ticket_attachments" not in st.session_state:
    st.session_state.ticket_attachments = {}


def _format_supabase_comment_error(action: str, exc: Exception) -> str:
    """Return an actionable message when comments fail because the ticket_comments
    table hasn't been created yet, otherwise the raw Supabase error."""
    message = str(exc)
    if "ticket_comments" in message and ("schema cache" in message or "PGRST205" in message):
        return (
            f"Unable to {action}: the ticket_comments table doesn't exist in Supabase yet. "
            "Run migrations/0002_add_ticket_comments_table.sql in the Supabase SQL editor, "
            "then reload the app."
        )
    return f"Unable to {action}: {exc}"


# Load persisted comments/replies once per session so they survive across reloads
# instead of only living in Streamlit's in-memory session state.
COMMENT_DATA_VERSION = 1
if (
    "ticket_comments" not in st.session_state
    or "comment_data_version" not in st.session_state
    or st.session_state.comment_data_version != COMMENT_DATA_VERSION
):
    try:
        st.session_state.ticket_comments = get_ticket_repository().load_comments()
    except Exception as exc:
        st.session_state.ticket_comments = []
        st.error(_format_supabase_comment_error("load comments from Supabase", exc))
    st.session_state.comment_data_version = COMMENT_DATA_VERSION


def _to_displayable_image(data: bytes, mime: str) -> tuple[bytes, str]:
    """Convert HEIC/HEIF bytes to JPEG; return other formats unchanged."""
    if mime in ("image/heic", "image/heif"):
        try:
            import importlib
            import io as _io

            from PIL import Image

            pillow_heif = importlib.import_module("pillow_heif")
            pillow_heif.register_heif_opener()
            img = Image.open(_io.BytesIO(data))
            buf = _io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG")
            return buf.getvalue(), "image/jpeg"
        except Exception:
            return data, mime
    return data, mime


def format_stat_value(value: float | int) -> str:
    return f"{float(value):.2f}"


def _render_burgundy_notice(message: str) -> None:
    """Render a deep-burgundy notice banner matching the app's styling (in place of st.info's default blue)."""
    st.markdown(
        f"<div style='background:#FBEAEC;border:1px solid {DEEP_BURGUNDY};color:{DEEP_BURGUNDY};"
        "padding:0.75rem 1rem;border-radius:8px;font-family: Helvetica, Arial, sans-serif; font-size:0.95rem;'>"
        f"{message}"
        "</div>",
        unsafe_allow_html=True,
    )


# Shared Resolution Status / Past Due (RAG) color coding, applied to any ticket table
# shown across the app (Ticket Management's editable grid, My Tickets' read-only tables).
_STATUS_STYLES = {
    "Pending": "background-color: #ffe0e0; color: #c00000; font-weight: 600;",
    "In Process": "background-color: #fff3cd; color: #856404; font-weight: 600;",
    "Resolved": "background-color: #d4edda; color: #155724; font-weight: 600;",
}
_PAST_DUE_FLAG_COLUMN = "Past Due (7+ Days)"
_PAST_DUE_STYLES = {"Flagged": _STATUS_STYLES["Pending"], "N/A": _STATUS_STYLES["Resolved"]}


def _style_ticket_status_col(col):
    return col.map(lambda v: _STATUS_STYLES.get(v, ""))


def _style_past_due_col(col):
    return col.map(lambda v: _PAST_DUE_STYLES.get(v, ""))


def _apply_rag_styling(df: pd.DataFrame):
    """Return a Styler with the Resolution Status / Past Due (RAG) color coding applied,
    for read-only ticket tables (e.g. My Tickets) — falls back to the plain dataframe when
    there's no Resolution Status column to color."""
    if df.empty or "Resolution Status" not in df.columns:
        return df

    styled_df = df.copy()
    styled_df[_PAST_DUE_FLAG_COLUMN] = calculate_past_due_labels(styled_df)
    return styled_df.style.apply(
        _style_ticket_status_col, subset=["Resolution Status"], axis=0
    ).apply(_style_past_due_col, subset=[_PAST_DUE_FLAG_COLUMN], axis=0)


my_tickets_person = st.session_state.get("my_tickets_person")
if st.session_state.get("current_view") == "my_tickets" and my_tickets_person:
    st.markdown(
        f"<div style='padding: 0.5rem 0 1rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 1.6rem; margin: 0; color: {DEEP_BURGUNDY};'>My Tickets — {my_tickets_person}</h2></div>",
        unsafe_allow_html=True,
    )
    st.button("← Back to home screen", key="my_tickets_back_button", on_click=_go_home_from_my_tickets)

    tickets_submitted = st.session_state.df[
        st.session_state.df["Submitted By"].astype(str).str.casefold() == my_tickets_person.casefold()
    ]
    tickets_assigned = st.session_state.df[
        st.session_state.df["Assigned To"].astype(str).str.casefold() == my_tickets_person.casefold()
    ]

    st.markdown(
        f"<h3 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.2rem; color: {DEEP_BURGUNDY};'>Tickets submitted</h3>",
        unsafe_allow_html=True,
    )
    if tickets_submitted.empty:
        _render_burgundy_notice("No tickets submitted by this person yet.")
    else:
        st.dataframe(_apply_rag_styling(tickets_submitted), width="stretch", hide_index=True)

    st.markdown(
        f"<h3 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.2rem; color: {DEEP_BURGUNDY};'>Tickets assigned</h3>",
        unsafe_allow_html=True,
    )
    if tickets_assigned.empty:
        _render_burgundy_notice("No tickets currently assigned to this person.")
    else:
        st.dataframe(_apply_rag_styling(tickets_assigned), width="stretch", hide_index=True)

    st.markdown(
        f"<h3 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.2rem; color: {DEEP_BURGUNDY};'>Ticket attachments</h3>",
        unsafe_allow_html=True,
    )
    my_ticket_ids = sorted(
        set(tickets_submitted["ID"].astype(str)) | set(tickets_assigned["ID"].astype(str))
    )
    my_tickets_attachment_ticket_id = st.selectbox(
        "Select a ticket to view its attachments",
        options=[""] + my_ticket_ids,
        index=0,
        key="my_tickets_attachment_selectbox",
    )
    if my_tickets_attachment_ticket_id:
        my_ticket_attachments = st.session_state.ticket_attachments.get(
            my_tickets_attachment_ticket_id, []
        )
        if my_ticket_attachments:
            st.write(f"{len(my_ticket_attachments)} attachment(s) for **{my_tickets_attachment_ticket_id}**:")
            for attachment in my_ticket_attachments:
                display_data, display_mime = _to_displayable_image(attachment["data"], attachment["mime"])
                if display_mime in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                    st.image(display_data, caption=attachment["name"])
                else:
                    # Browser cannot render this format; offer a download instead.
                    st.download_button(
                        label=f"Download {attachment['name']}",
                        data=attachment["data"],
                        file_name=attachment["name"],
                        mime=attachment["mime"],
                        type="primary",
                    )
        else:
            _render_burgundy_notice(f"No attachments for {my_tickets_attachment_ticket_id}.")
    else:
        _render_burgundy_notice("Select one of your tickets above to view its attachments.")

    st.stop()

if st.session_state.get("current_view") == "internal_management":
    st.markdown(
        f"<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: {DEEP_BURGUNDY}; white-space: nowrap; overflow-x: auto;'>Performance Management</h1></div>",
        unsafe_allow_html=True,
    )
    st.button("← Back to home screen", key="ism_back_button", on_click=_go_to_view, args=("home",))

    # Combined statistics and performance-trend section for the ticket.
    st.markdown(
        f"<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: {DEEP_BURGUNDY}; margin: 0;'>Statistics & Performance trend</h2></div>",
        unsafe_allow_html=True,
    )

    def render_ticket_metrics_row(tickets_df: pd.DataFrame) -> None:
        """Render the six standard KPI metrics for a set of tickets in a compact row."""
        metric_cols = st.columns(6)
        metric_cols[0].metric("Open", format_stat_value(calculate_open_ticket_count(tickets_df)))
        metric_cols[1].metric("Urgent", format_stat_value(calculate_urgent_open_ticket_count(tickets_df)))
        metric_cols[2].metric("Resolution %", f"{format_stat_value(calculate_resolution_rate(tickets_df))}%")
        metric_cols[3].metric("Avg hours", format_stat_value(calculate_average_resolution_time_hours(tickets_df)))
        metric_cols[4].metric("Overdue", format_stat_value(calculate_overdue_ticket_count(tickets_df)))
        metric_cols[5].metric("On-time %", f"{format_stat_value(calculate_on_time_close_rate(tickets_df))}%")

    all_distinct_assignees = get_distinct_assignees(st.session_state.df)
    assignee_filter_options = ["All"] + list(ASSIGNEES)
    for extra_assignee in all_distinct_assignees:
        if extra_assignee not in assignee_filter_options:
            assignee_filter_options.append(extra_assignee)

    selected_stats_assignee = st.selectbox(
        "Filter by assigned to",
        options=assignee_filter_options,
        key="stats_assignee_filter",
    )

    snapshot_file_name = (
        f"{selected_stats_assignee.replace(' ', '_').lower()}_snapshot.pdf"
        if selected_stats_assignee != "All"
        else "assignee_snapshot.pdf"
    )
    st.download_button(
        "Print assignee snapshot",
        data=build_assignee_snapshot_pdf(st.session_state.df, selected_stats_assignee),
        file_name=snapshot_file_name,
        mime="application/pdf",
        type="primary",
        disabled=selected_stats_assignee == "All",
        help="Select a specific person under Filter by assigned to enable this.",
    )

    # No statistical or performance-trend output is shown until a specific person is
    # selected — aggregated (all-assignee) output would duplicate per-assignee breakdowns.
    if selected_stats_assignee == "All":
        _render_burgundy_notice(
            "Select a specific person under \"Filter by assigned to\" so as to see their individual statistics, and performance trend."
        )
    else:
        for code_name in TICKET_CODES:
            code_tickets = filter_tickets_by_code(st.session_state.df, code_name)

            st.markdown(
                f"<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1.05rem; font-weight: 700; color: {DEEP_BURGUNDY}; margin: 0.5rem 0;'>{code_name}</div>",
                unsafe_allow_html=True,
            )

            code_assignees = get_distinct_assignees(code_tickets)
            assignees_for_code = (
                [selected_stats_assignee] if selected_stats_assignee in code_assignees else []
            )

            if not assignees_for_code:
                st.caption(f"No assigned tickets for {code_name} yet.")
            for person in assignees_for_code:
                st.markdown(
                    f"<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.9rem; font-weight: 600; color: {DARK_SLATE_CHARCOAL}; margin: 0.5rem 0 0.25rem 1rem;'>{code_name} &middot; {person}</div>",
                    unsafe_allow_html=True,
                )
                render_ticket_metrics_row(filter_tickets_by_assignee(code_tickets, person))

        trend_tickets = filter_tickets_by_assignee(st.session_state.df, selected_stats_assignee)
        trend_df = calculate_resolution_time_trend(trend_tickets)
        plot_df = trend_df.dropna(subset=["moving_average"])

        if plot_df.empty:
            _render_burgundy_notice(f"No average resolution time data yet for {selected_stats_assignee}.")
        else:
            plot_df = plot_df.copy()
            plot_df["series"] = "7-Day Moving Average"
            axis_style = {
                "gridColor": "#D9D9D9",
                "domainColor": "black",
                "tickColor": "black",
                "labelColor": "black",
                "titleColor": "black",
            }
            trend_chart = alt.Chart(plot_df).mark_line(strokeWidth=2.5).encode(
                x=alt.X("date:T", title="Time (Week End Date)", axis=alt.Axis(**axis_style)),
                y=alt.Y("moving_average:Q", title="Average Resolution Time (Hours)", axis=alt.Axis(**axis_style)),
                color=alt.Color(
                    "series:N",
                    scale=alt.Scale(domain=["7-Day Moving Average"], range=[DEEP_BURGUNDY]),
                    legend=alt.Legend(title="Legend", labelColor="black", titleColor="black"),
                ),
            ).properties(
                height=340, title=f"{selected_stats_assignee} — Average Resolution Time (Hours)"
            )
            st.altair_chart(trend_chart, width="stretch")

    st.stop()

if st.session_state.get("current_view") == "ticket_management":
    st.markdown(
        f"<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: {DEEP_BURGUNDY}; white-space: nowrap; overflow-x: auto;'>Ticket Management</h1></div>",
        unsafe_allow_html=True,
    )
    st.button("← Back to home screen", key="tm_back_button", on_click=_go_to_view, args=("home",))

    # Show section to view and edit existing tickets in a table.
    st.markdown(
        f"<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: {DEEP_BURGUNDY}; margin: 0;'>Existing tickets</h2></div>",
        unsafe_allow_html=True,
    )

    filter_col, search_col = st.columns([1, 2])
    with filter_col:
        selected_code = st.selectbox("Filter by code", options=["All", *TICKET_CODES])
    with search_col:
        selected_table_assignee = st.selectbox(
            "Filter by assignee", options=["All", *ASSIGNEES], key="table_assignee_filter"
        )
    filtered_df = filter_tickets_by_assignee(st.session_state.df, selected_table_assignee)
    filtered_df = filter_tickets_by_code(filtered_df, selected_code)

    # Allow the user to delete a ticket by selecting its ID.
    selected_ticket_id = st.selectbox(
        "Delete a ticket",
        options=[""] + list(st.session_state.df["ID"].astype(str)) if not st.session_state.df.empty else [""],
        index=0,
        key="delete_ticket_selectbox",
    )

    if st.button("Delete selected ticket", type="primary") and selected_ticket_id:
        try:
            get_ticket_repository().delete_ticket(selected_ticket_id)
        except Exception as exc:
            st.error(f"Unable to delete {selected_ticket_id} from Supabase: {exc}")
            st.stop()
        st.session_state.df = delete_ticket_by_id(st.session_state.df, selected_ticket_id)
        st.session_state.ticket_attachments.pop(selected_ticket_id, None)
        ticket_comment_ids = [
            c["comment_id"] for c in st.session_state.ticket_comments if c["ticket_id"] == selected_ticket_id
        ]
        if ticket_comment_ids:
            try:
                get_ticket_repository().delete_comments(ticket_comment_ids)
            except Exception as exc:
                st.error(_format_supabase_comment_error(f"delete comments for {selected_ticket_id} from Supabase", exc))
                st.stop()
        st.session_state.ticket_comments = [
            c for c in st.session_state.ticket_comments if c["ticket_id"] != selected_ticket_id
        ]
        st.success(f"Deleted {selected_ticket_id}.")
        st.rerun()

    # Allow the user to change a ticket's resolution status (kept out of the grid below so the
    # Resolution Status column can stay non-editable there and show its true legend colors).
    status_ticket_col, status_value_col, status_button_col = st.columns([2, 1, 1])
    with status_ticket_col:
        status_ticket_id = st.selectbox(
            "Update ticket status",
            options=[""] + list(st.session_state.df["ID"].astype(str)) if not st.session_state.df.empty else [""],
            index=0,
            key="update_status_selectbox",
        )
    with status_value_col:
        new_resolution_status = st.selectbox(
            "New status",
            options=["Pending", "In Process", "Resolved"],
            key="update_status_value_selectbox",
        )
    with status_button_col:
        st.write("")
        st.write("")
        apply_status_clicked = st.button("Apply status", type="primary")

    if apply_status_clicked and status_ticket_id:
        ticket_mask = st.session_state.df["ID"].astype(str) == status_ticket_id
        st.session_state.df.loc[ticket_mask, "Resolution Status"] = new_resolution_status
        if new_resolution_status.lower() == "resolved":
            current_date_closed = st.session_state.df.loc[ticket_mask, "Date Closed"].astype(str).str.strip()
            if (current_date_closed == "").all():
                st.session_state.df.loc[ticket_mask, "Date Closed"] = get_eastern_us_timestamp()
        else:
            st.session_state.df.loc[ticket_mask, "Date Closed"] = ""
        try:
            get_ticket_repository().update_ticket(st.session_state.df.loc[ticket_mask].iloc[0].to_dict())
        except Exception as exc:
            st.error(f"Unable to update {status_ticket_id} in Supabase: {exc}")
            st.stop()
        st.success(f"Updated {status_ticket_id} to {new_resolution_status}.")
        st.rerun()

    # Single color-coded, editable table — edits (including Description) save immediately.
    # Resolution Status is edited via the "Update ticket status" control above, since data_editor
    # only applies Styler colors (matching the legend) to non-editable columns.
    editor_df = filtered_df.copy()
    if "Date Closed" in editor_df.columns:
        editor_df["Date Closed"] = editor_df["Date Closed"].replace("", " ")

    table_search_term = st.text_input(
        "Search existing tickets",
        placeholder="Enter full or partial ticket number, e.g. the last 3-4 characters",
        key="table_search_input",
    )
    editor_df = filter_tickets_by_id(editor_df, table_search_term)

    editor_df[_PAST_DUE_FLAG_COLUMN] = (
        calculate_past_due_labels(editor_df) if not editor_df.empty else ""
    )

    if not editor_df.empty and "Resolution Status" in editor_df.columns:
        st.markdown(
            "<div style='margin: 0.75rem 0 0.25rem 0;'><span style='font-family: Helvetica, Arial, sans-serif; font-size: 0.88rem; color: #555;'>" 
            "Resolution Status legend: "
            "<span style='background:#ffe0e0;color:#c00000;font-weight:600;padding:1px 7px;border-radius:4px;margin-right:6px;'>Pending</span>"
            "<span style='background:#fff3cd;color:#856404;font-weight:600;padding:1px 7px;border-radius:4px;margin-right:6px;'>In Process</span>"
            "<span style='background:#d4edda;color:#155724;font-weight:600;padding:1px 7px;border-radius:4px;'>Resolved</span>"
            "</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='margin: 0.25rem 0 0.5rem 0;'><span style='font-family: Helvetica, Arial, sans-serif; font-size: 0.88rem; color: #555;'>"
            "Past Due legend: "
            "<span style='background:#ffe0e0;color:#c00000;font-weight:600;padding:1px 7px;border-radius:4px;margin-right:6px;'>Flagged</span>"
            "<span style='background:#d4edda;color:#155724;font-weight:600;padding:1px 7px;border-radius:4px;'>N/A</span>"
            "</span></div>",
            unsafe_allow_html=True,
        )
        editor_source = (
            editor_df.style.apply(
                _style_ticket_status_col, subset=["Resolution Status"], axis=0
            )
            .apply(_style_past_due_col, subset=[_PAST_DUE_FLAG_COLUMN], axis=0)
            .set_properties(
                subset=["Issue"],
                **{
                    "white-space": "pre-wrap",
                    "overflow-wrap": "anywhere",
                    "overflow-y": "auto",
                    "max-height": "180px",
                    "display": "block",
                },
            )
            .set_properties(
                subset=["Notes"],
                **{
                    "white-space": "pre-wrap",
                    "overflow-wrap": "anywhere",
                    "overflow-y": "auto",
                    "max-height": "180px",
                    "display": "block",
                },
            )
        )
    else:
        editor_source = editor_df

    edited_df = st.data_editor(
        editor_source,
        width="stretch",
        height=500,
        hide_index=True,
        row_height=216,
        column_config={
            "Issue": st.column_config.TextColumn(
                "Description",
                help="Ticket description",
                width="large",
            ),
            "Code": st.column_config.SelectboxColumn(
                "Code",
                help="Support work category",
                options=TICKET_CODES,
                required=True,
            ),
            "Priority": st.column_config.SelectboxColumn(
                "Priority",
                help="Priority",
                options=["Urgent", "High", "Medium", "Low"],
                required=True,
            ),
            "Assigned To": st.column_config.TextColumn(
                "Assigned To",
                help="Person assigned to this ticket",
            ),
            "Notes": st.column_config.TextColumn(
                "Notes",
                help="Internal notes for this ticket",
                width="large",
            ),
            "Resolution Status": st.column_config.TextColumn(
                "Resolution Status",
                help="Current resolution status — change it above with 'Update ticket status'",
            ),
            "Due Date": st.column_config.TextColumn(
                "Due Date",
                help="Target resolution date used for SLA metrics",
            ),
            "Date Closed": st.column_config.TextColumn(
                "Date Closed",
                default="",
            ),
            _PAST_DUE_FLAG_COLUMN: st.column_config.TextColumn(
                _PAST_DUE_FLAG_COLUMN,
                help="Flags tickets still Pending or In Process one full week after submission; "
                "shows N/A for tickets closed within 7 days",
            ),
        },
        # Disable editing the ID, Date Submitted, Date Closed, Resolution Status, and past-due flag columns.
        disabled=["ID", "Date Submitted", "Date Closed", "Resolution Status", _PAST_DUE_FLAG_COLUMN],
    )
    # The past-due flag is computed for display only and isn't part of the persisted ticket schema.
    edited_df = edited_df.drop(columns=[_PAST_DUE_FLAG_COLUMN])
    if "Date Closed" in edited_df.columns:
        edited_df["Date Closed"] = edited_df["Date Closed"].astype(str).str.strip()

    # Auto-stamp Date Closed the moment a ticket is set to Closed.
    needs_close_stamp = (
        (edited_df["Resolution Status"].astype(str).str.lower() == "resolved")
        & (edited_df["Date Closed"].astype(str).str.strip() == "")
    )
    if needs_close_stamp.any():
        edited_df.loc[needs_close_stamp, "Date Closed"] = get_eastern_us_timestamp()

    unedited_df = st.session_state.df[
        ~st.session_state.df["ID"].astype(str).isin(edited_df["ID"].astype(str))
    ]
    previously_edited_df = st.session_state.df[
        st.session_state.df["ID"].astype(str).isin(edited_df["ID"].astype(str))
    ].set_index("ID")
    for _, ticket in edited_df.iterrows():
        previous_ticket = previously_edited_df.loc[ticket["ID"]]
        if not ticket.equals(previous_ticket):
            try:
                get_ticket_repository().update_ticket(ticket.to_dict())
            except Exception as exc:
                st.error(f"Unable to update {ticket['ID']} in Supabase: {exc}")
                st.stop()
    st.session_state.df = pd.concat([edited_df, unedited_df], ignore_index=True)

    st.stop()







def call_local_support_assistant(prompt: str) -> str:
    prompt_text = (prompt or "support request").strip()
    lowered_prompt = prompt_text.lower()

    if (
        not any(term in lowered_prompt for term in ["ct47", "ct 47", "handheld", "rfid"])
        and any(term in lowered_prompt for term in ["printer", "print", "zebra", "zt620", "label printer", "ricoh", "im 460f", "460f", "rp4d", "mobile printer", "copier", "copy", "scan", "fax", "mfp", "multi-function"])
    ):
        zebra_tip = (
            "For a Zebra ZT620: check that the label roll is loaded correctly and the media type/size in the printer settings matches the labels you're using. "
            "If labels are printing blank or misaligned, run calibration from the printer front panel (hold Feed + Cancel on power-up). "
            "If the printer shows a fault light, note the color pattern and include it in your ticket."
        )
        rp4d_tip = (
            "For a Honeywell RP4D: confirm the battery is charged and fully seated, then restart the printer. "
            "Check that the paper roll is loaded with the printable side facing the print head and that the cover is latched. "
            "If it will not connect, turn Bluetooth or Wi-Fi off and back on, then re-pair the printer with the handheld device. "
            "Run a test label from the printer settings and include any status-light pattern or error message in your ticket."
        )
        ricoh_tip = (
            "For a Ricoh IM 460F multi-function printer: if it will not print, check the touchscreen for any error or paper-jam indicators and clear them first. "
            "For scan-to-email or scan-to-folder issues, verify network connectivity and confirm the destination address or folder path is still correct. "
            "For fax issues, check that the phone line is connected to the LINE port (not TEL), then power cycle the unit from the power button."
        )
        matched_printer_tips = []
        if any(term in lowered_prompt for term in ["zebra", "zt620", "label printer"]):
            matched_printer_tips.append(zebra_tip)
        if any(term in lowered_prompt for term in ["rp4d", "mobile printer"]):
            matched_printer_tips.append(rp4d_tip)
        if any(term in lowered_prompt for term in ["ricoh", "im 460f", "460f", "mfp", "multi-function", "copier", "copy", "scan", "fax"]):
            matched_printer_tips.append(ricoh_tip)

        if matched_printer_tips:
            return (
                "Sounds like a printer issue. " + " ".join(matched_printer_tips) +
                " If it is still not cooperating, submit a ticket and include the exact model plus any error code shown on the device."
            )
        return (
            "Sounds like a printer issue. Let me know which printer you have — a Zebra ZT620, a Honeywell RP4D, or a Ricoh IM 460F multi-function printer — "
            "and I can give you specific steps. In the meantime, submit a ticket and include the exact model plus any error code shown on the device."
        )

    if any(term in lowered_prompt for term in ["ethernet", "wired network", "network cable", "lan cable", "rj45"]):
        return (
            "For a wired network problem, start with the physical connection: make sure the Ethernet cable clicks firmly into the device and wall jack or dock, then check for link lights at the port. "
            "Try another known-good cable or port if one is available, and restart the device or dock after reconnecting it. "
            "If the connection still fails, submit a ticket with the jack location, device name, and whether the link lights are on so we can trace the network path."
        )

    if any(term in lowered_prompt for term in ["wifi", "wi-fi", "wireless", "network", "connect", "internet"]):
        return (
            "Ugh, internet issues are the worst! Try turning your device's Wi-Fi off and back on first. "
            "If that doesn't help, try forgetting the network and reconnecting. "
            "Still stuck? Check if anyone else nearby is having the same problem — if so, it might be on our end and we'll get it sorted. Submit a ticket and we'll jump on it!"
        )

    if any(term in lowered_prompt for term in [
        "radio", "rf", "rfid", "bluetooth", "scanner", "device", "peripheral",
        "honeywell", "ct47", "ct 47", "handheld",
        "keyboard", "mouse", "mice", "monitor", "webcam", "headset", "headphones",
        "microphone", "speaker", "usb", "docking station", "external drive",
    ]):
        peripheral_tips = []
        if any(term in lowered_prompt for term in ["rf", "rfid", "radio", "scanner", "honeywell", "ct47", "ct 47", "handheld"]):
            peripheral_tips.append(
                "For a Honeywell CT47: start with a clean reboot — hold the power button and select Reboot. "
                "If it won't connect to the network, go to Settings > Network & Internet, forget the Wi-Fi network, and reconnect. "
                "If the scanner isn't reading tags or barcodes, clean the scan window and make sure you're within the rated read range. "
                "If the device is frozen or the battery drains unusually fast, a factory-image reboot from IT may be needed — submit a ticket and we'll take care of it."
            )
        if any(term in lowered_prompt for term in ["keyboard", "mouse", "mice"]):
            peripheral_tips.append(
                "If it's a keyboard or mouse, check the batteries (if wireless) and try a different USB port or re-pairing it."
            )
        if any(term in lowered_prompt for term in ["monitor", "webcam"]):
            peripheral_tips.append(
                "If it's a monitor or webcam, double-check the cable connections on both ends and try a different port or cable if one's handy."
            )
        if any(term in lowered_prompt for term in ["headset", "headphones", "microphone", "speaker"]):
            peripheral_tips.append(
                "For audio devices, make sure the right device is selected as your default in your sound settings, not just plugged in."
            )
        if any(term in lowered_prompt for term in ["usb", "docking station", "external drive"]):
            peripheral_tips.append(
                "For USB or docking station issues, try a different port, and if you're using a dock, unplug and reconnect all the cables from your laptop."
            )
        peripheral_extra = (" " + " ".join(peripheral_tips)) if peripheral_tips else ""
        return (
            "Looks like a device or peripheral issue! Start by turning it off and back on. "
            "If it pairs wirelessly, try unpairing it and pairing it again from scratch. "
            "Make sure the battery isn't low too — that can cause all kinds of weird behavior." + peripheral_extra +
            " If it's still acting up, submit a ticket and we'll take a look!"
        )

    if any(term in lowered_prompt for term in ["blue yonder", "jda", "wms", "warehouse management"]):
        return (
            "Ah, sounds like a Blue Yonder/JDA (WMS) issue! First, check if you're able to log back in — sometimes a quick sign-out and sign-in clears things up. "
            "If a task, order, or inventory count looks stuck or wrong, jot down the ID or location you were working on before you submit a ticket — that helps us track it down fast. "
            "If the whole system seems down for everyone, that's likely a bigger outage — submit a ticket right away so we can get on it!"
        )

    if any(term in lowered_prompt for term in ["csw", "client server warehousing"]):
        return (
            "Sounds like a CSW (Client Server Warehousing WMS) issue! Try logging out and back in first, since that clears up a lot of small hiccups. "
            "If a specific transaction, pick, or putaway isn't going through, note what you were doing and any error message you saw. "
            "Submit a ticket with those details and we'll get it sorted!"
        )

    if any(term in lowered_prompt for term in ["etq", "reliance"]):
        return (
            "Sounds like an ETQ Reliance question! ETQ Reliance is our quality and compliance management system (QMS) — it's what we use for things like "
            "corrective/preventive actions (CAPA), nonconformance records, document control, audits, and training records. "
            "If a record or workflow seems stuck, check whether it's waiting on someone else's sign-off or approval step before assuming it's broken. "
            "If you can't log in or don't see a form/module you expect, that's usually a permissions issue tied to your ETQ Reliance user role. "
            "Submit a ticket with the record number or form name and what looks wrong, and we'll get it sorted!"
        )

    if (
        not any(term in lowered_prompt for term in [
            "haipick", "hai pick", "hai robotics", "hai system", "hai systems",
            "hai rcs", "haipick rcs", "hai a3", "hai a3s", "hai a3el",
        ])
        and any(term in lowered_prompt for term in ["inventory", "cycle count", "sap", "stock", "on-hand", "on hand", "putaway", "pick", "replenishment"])
    ):
        return (
            "Inventory control question? Happy to help! Whether it's a cycle count that's off, a stock discrepancy, or a SAP transaction that isn't behaving, "
            "the first step is usually double-checking the location and quantity you're seeing versus what the system expects. "
            "Note the material/item number, location, and what looks wrong, then submit a ticket — we'll dig into the SAP or WMS side and help get it reconciled!"
        )

    if any(term in lowered_prompt for term in ["platinum equity", "owens & minor", "owens and minor", "o&m", "om p&hs", "products & healthcare services", "products and healthcare services"]):
        return (
            "Good question! Owens & Minor (O&M) is a healthcare products and services company — our Products & Healthcare Services (P&HS) segment supports manufacturing, sourcing, "
            "and distribution for healthcare providers. Platinum Equity, LLC is a private equity firm; they've been an investor connected to parts of our business. "
            "If you need something specific about org structure, policy, or business details, submit a ticket and we'll point you to the right person!"
        )

    if any(term in lowered_prompt for term in ["spc", "statistical process control", "control chart", "ucl", "lcl", "out of control", "special cause", "common cause"]):
        return (
            "Great question about SPC! Think of a control chart like a health monitor for your process — it shows whether things are running normally or if something unusual is happening. "
            "The lines across the top and bottom (called control limits) show the expected range. If a point goes outside those lines, or you see a pattern like lots of points in a row on one side, "
            "that's a signal that something changed and it's worth investigating. Want help building a chart or understanding what you're seeing? Submit a ticket and we'll set it up with you!"
        )

    if any(term in lowered_prompt for term in ["sqc", "statistical quality control", "defect", "sampling", "inspection", "acceptance sampling", "quality", "reject", "pass", "fail", "spec", "specification"]):
        return (
            "SQC is basically about making sure your products or outputs meet the standard before they move on. "
            "If you're seeing too many rejects or defects, the first step is figuring out whether it's a one-time thing or a pattern. "
            "We can look at your data together and help you spot where things are going wrong. Just submit a ticket with a description of what you're seeing and we'll dig into it with you!"
        )

    if any(term in lowered_prompt for term in ["data", "analysis", "analyze", "trend", "chart", "graph", "dashboard", "metric", "kpi"]):
        return (
            "Need help making sense of your data? You're in the right place! "
            "Whether you need a simple summary, a chart, or a full dashboard, we can help you figure out the best way to show what's going on. "
            "Tell us what data you have and what question you're trying to answer, then submit a ticket and we'll take it from there!"
        )

    if any(term in lowered_prompt for term in ["power bi", "powerbi", "bi report", "bi dashboard", "power platform", "power apps", "power automate", "power pages", "powerapps", "pbix", "q&a", "qna", "q and a"]):
        return (
            "Power Platform question (Power BI, Power Apps, Power Automate, or Power Pages)? We are happy to help. "
            "If a report, app, or flow isn't loading or the numbers/behavior look off, try refreshing the page or signing out and back in. "
            "If a flow (Power Automate) stopped running, check if it's been turned off or hit an error — that's usually shown right on the flow's run history. "
            "If you need something new built or changed, just describe what you want to see — even a rough sketch on paper works — and submit a ticket. We'll build it out for you!"
        )

    if any(term in lowered_prompt for term in ["smartsheet", "smart sheet"]):
        return (
            "SmartSheet question? Got it! If a sheet, report, or dashboard isn't updating, try refreshing the page first — sometimes it just needs a moment to sync. "
            "If a formula or automation (like an alert or approval workflow) isn't firing right, double-check the trigger conditions match what you expect. "
            "Submit a ticket with the sheet name and what looks wrong, and we'll dig in with you!"
        )

    if any(term in lowered_prompt for term in ["sharepoint", "share point", "onedrive", "one drive"]):
        return (
            "SharePoint or OneDrive trouble? We've got you! If a file or site won't load, try refreshing or opening it in a new tab first. "
            "If you can't find a file, check you're looking in the right library/folder and that you have permission to view it. "
            "If it's a permissions or access issue, submit a ticket with the site/file link and we'll get you sorted out!"
        )

    if any(term in lowered_prompt for term in ["opendock", "open dock", "dock scheduling", "dock schedule", "appointment scheduling"]):
        return (
            "Opendock Nova (dock scheduling) issue? Happy to help! If an appointment won't save or the calendar looks wrong, try refreshing the page first. "
            "If a dock door or time slot isn't showing up right, note the date, dock, and carrier involved before submitting a ticket — that helps us track it down fast. "
            "Submit a ticket and we'll get your scheduling back on track!"
        )

    if any(term in lowered_prompt for term in ["ukg", "kronos", "timecard", "time card", "punch", "time punch", "time clock", "schedule", "shift", "time off", "pto", "absence"]):
        return (
            "UKG WFM (timecard/scheduling) question? Got it! If your timecard looks wrong or a punch didn't record, "
            "first check whether the missed punch can be corrected by your supervisor directly in UKG WFM — most sites allow manager edits before payroll closes. "
            "If a schedule, shift, or time-off request isn't showing up right, double-check the effective date and that it was approved, not just submitted. "
            "Submit a ticket with your employee ID, the affected date(s), and a description of what looks wrong and we'll get it sorted!"
        )

    if any(term in lowered_prompt for term in ["workday", "hris", "hr system", "payroll", "onboarding", "offboarding", "benefits", "direct deposit", "w-2", "w2", "tax form", "employee profile", "org chart", "job change", "position"]):
        return (
            "Workday HCM question? Happy to help! If you’re having trouble logging in, try resetting your password through the Workday HCM login page or your SSO portal. "
            "For payroll, benefits, or personal info changes (like direct deposit or address updates), those are usually self-service in Workday HCM under your profile — look for the ‘Pay’ or ‘Benefits’ worklets. "
            "If something looks wrong on your paycheck, W-2, or employee record, or if you need help with onboarding/offboarding tasks, submit a ticket with your employee ID and the specific issue and we’ll connect you with the right team!"
        )

    if any(term in lowered_prompt for term in ["automation", "plc", "scada", "conveyor", "sortation", "sorter", "industrial control"]):
        return (
            "Industrial automation issue? Let's get it moving again! If a conveyor, sorter, or PLC-controlled system faulted out, check for a visible fault code or e-stop that's been triggered first. "
            "A lot of these systems just need a fault to be cleared and a reset before they'll run again — but don't force anything that seems unsafe. "
            "Note the fault code or what you're seeing, then submit a ticket so a technician can take a closer look!"
        )

    if any(term in lowered_prompt for term in [
        "facility", "facilities", "maintenance", "hvac", "heating", "air conditioning",
        "lighting", "light fixture", "plumbing", "leak", "water", "restroom", "door",
        "industrial hygiene", "air quality", "ventilation", "chemical", "spill", "ergonomic",
    ]):
        return (
            "For a facilities, maintenance, or industrial hygiene concern, safety comes first. Don't try to repair electrical equipment, machinery, leaks, or ventilation systems yourself. "
            "For an immediate hazard, spill, strong odor, blocked exit, or unsafe condition, follow your site's emergency or safety-reporting process right away. "
            "For routine issues, submit a ticket with the exact location, what you observed, when it started, and photos if they can be taken safely. We'll route it to the right facilities or maintenance team."
        )

    if any(term in lowered_prompt for term in [
        "haipick", "hai pick", "hai robotics", "hai system", "hai systems",
        "hai rcs", "haipick rcs", "hai a3", "hai a3s", "hai a3el",
    ]):
        return (
            "For a HAI Robotics HaiPick system issue, first keep people clear of the affected aisle and do not bypass a guard, safety stop, or e-stop. "
            "In the HAI RCS console, identify the specific ACR, workstation, or charging station and record its active alarm, fault code, and current task. "
            "For a stopped ACR, look only for visible travel-path obstructions and confirm the RCS shows it is safe before any authorized recovery. "
            "For charging faults, check whether the unit is correctly docked and whether the charging contacts are visibly dirty or blocked; do not service electrical parts yourself. "
            "For bin-retrieval or task-queue problems, record the tote/bin ID, source and destination, time the task stopped, and whether other HaiPick units are still working. "
            "Submit a ticket with those details and screenshots of the RCS alarm so the HAI support team can isolate whether the issue is the ACR, station, RCS, or WMS interface."
        )

    if any(term in lowered_prompt for term in ["excel", "spreadsheet", "formula", "pivot", "vlookup", "macro"]):
        return (
            "Excel question? We can help with that. Whether a formula is not working, a pivot table looks incorrect, or you need help automating a task, we are here to assist. "
            "If you're getting an error, take a screenshot of it and include it in your ticket. "
            "If you need something built from scratch, just describe what you're trying to do in plain terms and we'll figure out the best way to do it!"
        )

    if any(term in lowered_prompt for term in ["password", "login", "locked", "ldap", "vpn", "access", "sign in"]):
        return (
            "Can't get in? No worries, it happens! Double-check you're using the right username and that Caps Lock isn't on. "
            "If your account is locked, you'll need to submit a ticket and we'll get it unlocked for you right away. "
            "If you're trying to connect through VPN and it's not working, try disconnecting and reconnecting. We've got you covered!"
        )

    if any(term in lowered_prompt for term in [
        "software", "application", "app", "program", "install", "installation",
        "uninstall", "update", "upgrade", "driver", "license", "licensing",
        "activation", "crash", "crashed", "crashing", "glitch", "bug",
        "not responding", "hang", "hung", "error message",
    ]):
        software_tips = []
        if any(term in lowered_prompt for term in ["install", "installation", "uninstall", "update", "upgrade"]):
            software_tips.append(
                "If it's an install or update issue, make sure you're on the latest version and have enough free disk space, then try running it again."
            )
        if any(term in lowered_prompt for term in ["license", "licensing", "activation"]):
            software_tips.append(
                "If it's a licensing or activation error, double-check you're signed in with your work account — that's usually what a license is tied to."
            )
        if any(term in lowered_prompt for term in ["crash", "crashed", "crashing", "not responding", "hang", "hung"]):
            software_tips.append(
                "If the program crashed or froze, save your work if you can, close it, and reopen it — a lot of glitches clear up after a fresh restart of the app."
            )
        if "driver" in lowered_prompt:
            software_tips.append(
                "If it's a driver problem, try unplugging and replugging the device, or restarting your computer so the driver reloads."
            )
        software_extra = (" " + " ".join(software_tips)) if software_tips else ""
        return (
            "Sounds like a software issue!" + software_extra +
            " If you're seeing a specific error message, take a screenshot of it and include it in your ticket — that helps us track down the cause fast. "
            "Submit a ticket and we'll get it fixed up!"
        )

    if any(term in lowered_prompt for term in [
        "slow", "frozen", "restart", "computer", "pc", "laptop", "screen",
        "hardware", "motherboard", "cpu", "processor", "ram", "memory",
        "hard drive", "ssd", "hdd", "battery", "charger", "power supply",
        "cable", "port",
    ]):
        hardware_tips = []
        if any(term in lowered_prompt for term in ["battery", "charger", "power supply"]):
            hardware_tips.append(
                "If it's a battery or power issue, check the charger cable and outlet, and let it charge a bit before assuming the battery itself is bad."
            )
        if any(term in lowered_prompt for term in ["hard drive", "ssd", "hdd", "ram", "memory", "cpu", "processor", "motherboard"]):
            hardware_tips.append(
                "If it's an internal component like the drive, memory, or processor, don't open the case yourself — submit a ticket so a technician can take a safe look."
            )
        if "screen" in lowered_prompt:
            hardware_tips.append(
                "If the screen is blank or flickering, check the brightness and cable connections first, and try an external monitor to see if the picture shows up there."
            )
        if any(term in lowered_prompt for term in ["cable", "port"]):
            hardware_tips.append(
                "If it's a loose cable or port, try reseating the connection or trying a different cable/port if one's available."
            )
        hardware_extra = (" " + " ".join(hardware_tips)) if hardware_tips else ""
        return (
            "Ugh, a slow or misbehaving computer is so frustrating!" + hardware_extra +
            " First, try saving anything open and restarting — that fixes more than you'd think. "
            "If it keeps happening, make a note of what you were doing when it started and submit a ticket. "
            "We can take a look and figure out if it needs a tune-up or something more. Hang tight!"
        )

    return (
        "Hello! I am Owen, your support assistant. I can help with technical issues involving hardware, software, peripherals, JDA, CSW, SAP, ETQ Reliance, SmartSheet, SharePoint, Excel, Power Platform, Opendock Nova, UKG WFM, Workday HCM, "
        "inventory control, quality control, industrial automation, HaiPick robotics (HAI Robotics ACR systems), SPC, SQC, and more. "
        "Just describe what's going on in your own words — no technical jargon needed — and I'll point you in the right direction. "
        "If we need to dig deeper, just submit a ticket and our team will come to you!"
    )


GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
GITHUB_MODELS_MODEL = "gpt-4o-mini"

GITHUB_MODELS_SYSTEM_PROMPT = (
    "You are Owen, an internal on-prem technical support agent with expert-level knowledge across the following systems and topics: "
    "everyday tech issues (printers, Wi-Fi, devices, logins); computer hardware (laptops, desktops, monitors, batteries, "
    "cables, ports, and internal components like RAM, CPU, and hard drives); "
    "label printers (specifically the Zebra ZT620 — label loading, calibration, fault lights, and media settings); "
    "multi-function printers (specifically the Ricoh IM 460F — printing, copying, scanning, faxing, scan-to-email/folder, and power-cycle troubleshooting); "
    "RF and barcode handheld devices (specifically the Honeywell CT47 — reboots, Wi-Fi reconnection, scan window cleaning, and factory-image requests); "
    "software (applications, installs, updates, "
    "licensing, drivers, crashes, and error messages); peripherals (keyboards, mice, webcams, headsets, docking stations, "
    "and USB devices); the Blue Yonder/JDA warehouse management system (WMS); "
    "the Client Server Warehousing (CSW) WMS; SAP; ETQ Reliance (the quality and compliance management system used for CAPA, nonconformance records, document control, audits, and training records); "
    "SmartSheet; SharePoint; Excel; Microsoft Power Platform "
    "(Power BI, Power Apps, Power Automate, and Power Pages); Opendock Nova dock scheduling; "
    "UKG WFM (timecard management, scheduling, time-off requests, and punch corrections); "
    "Workday HCM (payroll, benefits, direct deposit, W-2s, employee profiles, onboarding/offboarding, and org changes); "
    "continuous improvement; "
    "warehouse-centric inventory control; quality control; industrial automation (PLCs, SCADA, conveyors, sortation); "
    "robotics — specifically the HAI Robotics HaiPick suite of Autonomous Case-handling Robots (ACRs), including the A3, A3S, and A3EL models "
    "(covering RCS console alarms, fault codes, e-stop and safety-stop recovery, charging station issues, travel-path obstructions, bin-retrieval errors, and WMS/RCS integration); "
    "statistical process control (SPC); and statistical quality control (SQC); "
    "facilities management, maintenance, and industrial hygiene (including HVAC, lighting, plumbing, access points, ventilation, air-quality, spill, and safe escalation guidance). "
    "Only give HaiPick-specific guidance when the user identifies HAI Robotics, HaiPick, an HAI RCS console, or a HaiPick A3/A3S/A3EL system; do not assume an unrelated robot, AMR, AGV, cobot, or automation issue uses HaiPick. "
    "Tailor every reply specifically to what the user actually wrote — if they name an exact device model, system, or error, address only that one; "
    "do not pad the reply with steps for other models or unrelated systems they did not mention. "
    "For every request, act as a helpdesk troubleshooter: identify the likely scope, give a short ordered set of safe checks that the user can perform, explain the purpose of each check in plain language, "
    "ask for the specific model, error, location, or affected record when that would isolate the issue, and state exactly what useful details to include in a ticket if escalation is needed. "
    "Answer with the depth and accuracy of a subject-matter expert on each topic, but always translate that expertise into casual, plain, layman's terms for a non-technical audience. "
    "Avoid jargon, and briefly explain any technical term you do use. Never invent system access, policy, status, or a repair outcome. For safety, electrical, machinery, robotics, chemical, or industrial-hygiene risks, "
    "tell the user to stop and follow the site's safety or emergency process rather than attempting a risky repair. Keep replies focused and conversational. Do not mention ticket counts or system context. "
    "You also have general knowledge of Platinum Equity, LLC (a private equity firm) and Owens & Minor Products & "
    "Healthcare Services (Owens & Minor, or simply O&M), the healthcare products and services company this support "
    "system belongs to, in case users ask general questions about either company. "
    "If the issue needs a technician, suggest the user submit a ticket in this app."
)


def _get_github_models_token() -> str | None:
    for env_key in ("GITHUB_MODELS_TOKEN",):
        token = os.environ.get(env_key)
        if token and str(token).strip():
            return str(token).strip()

    secrets = getattr(st, "secrets", None)
    if secrets is not None:
        for secret_key in ("GITHUB_MODELS_TOKEN",):
            try:
                token = secrets.get(secret_key)
            except Exception:
                token = None
            if token and str(token).strip():
                return str(token).strip()

    return None


@st.cache_resource(show_spinner=False)
def _get_github_models_client():
    token = _get_github_models_token()
    if not token:
        return None
    try:
        from openai import OpenAI
        return OpenAI(base_url=GITHUB_MODELS_ENDPOINT, api_key=token)
    except Exception:
        return None


def call_github_models_support_assistant(prompt: str) -> str | None:
    """Try GitHub Models first; return None so callers can fall back to the local assistant."""
    client = _get_github_models_client()
    if client is None:
        return None

    messages = [{'role': 'system', 'content': GITHUB_MODELS_SYSTEM_PROMPT}]
    messages.append({'role': 'user', 'content': prompt})

    try:
        response = client.chat.completions.create(
            model=GITHUB_MODELS_MODEL,
            messages=messages,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def get_assistant_reply(prompt: str) -> str:
    github_models_reply = call_github_models_support_assistant(prompt)
    if github_models_reply is not None:
        return github_models_reply
    return call_local_support_assistant(prompt)


def clear_assistant_messages(session_state: dict) -> None:
    """Clear the visible assistant conversation history for a fresh prompt."""
    session_state["assistant_messages"] = []


def submit_assistant_prompt(prompt: str) -> None:
    """Send a prompt (typed or from a topic card) through the assistant and render the exchange."""
    prompt = (prompt or "").strip()
    if not prompt:
        return

    clear_assistant_messages(st.session_state)
    st.session_state.assistant_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=None):
        st.markdown(prompt)

    try:
        with st.spinner("Processing your request..."):
            reply = get_assistant_reply(prompt)
        st.session_state.assistant_messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant", avatar=None):
            st.markdown(reply)
    except Exception as exc:
        error_message = f"I hit a local issue while preparing a response: {exc}"
        st.session_state.assistant_messages.append({"role": "assistant", "content": error_message})
        with st.chat_message("assistant", avatar=None):
            st.markdown(error_message)


if "assistant_messages" not in st.session_state:
    st.session_state.assistant_messages = []


assistant_container = st.container()
with assistant_container:
    logo_path = APP_ROOT / "IT-0014.png"
    avatar_size = 220
    if logo_path.exists():
        image_b64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        image_html = (
            f"<img src='data:image/png;base64,{image_b64}' "
            f"style='width: {avatar_size}px; height: {avatar_size}px; object-fit: cover; "
            "border-radius: 14px; display: block;' />"
        )
    else:
        image_html = ""

    # Flexbox with align-items: stretch keeps the card exactly as tall as the image, regardless of layout width.
    st.markdown(
        "<div style='display: flex; align-items: stretch; gap: 1rem; margin: 1rem 0 1.25rem 0;'>"
        f"<div style='flex: 0 0 auto;'>{image_html}</div>"
        "<div style='flex: 1; border: 1px solid #D9D9D9; border-radius: 14px; padding: 1rem; box-sizing: border-box; "
        "background: linear-gradient(135deg, #ffffff 0%, #f7f7f7 100%); box-shadow: 0 2px 8px rgba(0,0,0,0.05); "
        "display: flex; flex-direction: column; justify-content: center;'>"
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1rem; font-weight: 700; color: #111111; margin-bottom: 0.35rem;'>Hello, and welcome. I am your AI-driven on-premises technical support agent powered by GPT-4o Mini, and Python-3. Please feel free to ask me any questions.</div>"
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; color: #333333; line-height: 1.45;'>"
        "After hours? Not a problem! I am always available locally to assist with an array of Tier-1 technical support issues. Just ask."
        "</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # avatar=None still renders Streamlit's default role icon, so hide the avatar element via CSS.
    st.markdown(
        "<style>[data-testid='stChatMessageAvatarUser'], [data-testid='stChatMessageAvatarAssistant'] { display: none !important; }</style>",
        unsafe_allow_html=True,
    )

    for message in st.session_state.assistant_messages:
        with st.chat_message(message["role"], avatar=None):
            st.markdown(message["content"])

    SUPPORT_TOPICS = [
        "JDA", "CSW", "SAP", "ETQ", "SmartSheet", "OneDrive", "SharePoint", "Excel", "Power Platform",
        "Opendock Nova", "UKG WFM", "Workday HCM", "Honeywell CT47",
        "Honeywell RP4D", "Zebra ZT620", "Ricoh IM 460F MFP",
        "HAI Robotics (HaiPick)", "Wireless internet", "Ethernet", "Bluetooth",
    ]

    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.85rem; font-weight: 700; color: #333333; margin: 0.5rem 0 0.5rem 0;'>Ask about:</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <style>
        .st-key-topic_cards button {{
            background-color: {DEEP_BURGUNDY} !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            font-family: Helvetica, Arial, sans-serif !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Clicking a topic card sends a ready-made prompt through the same assistant pipeline as typed chat input.
    topic_card_prompt = None
    with st.container(key="topic_cards"):
        cards_per_row = 4
        for row_start in range(0, len(SUPPORT_TOPICS), cards_per_row):
            row_topics = SUPPORT_TOPICS[row_start:row_start + cards_per_row]
            row_columns = st.columns(cards_per_row)
            for col, topic in zip(row_columns, row_topics):
                with col:
                    if st.button(topic, key=f"topic_card_{topic}", use_container_width=True):
                        topic_card_prompt = f"Tell me about {topic}."

    st.markdown(
        f"""
        <style>
        .st-key-start_over_row button {{
            background-color: #ffffff !important;
            color: {DEEP_BURGUNDY} !important;
            border: 1px solid {DEEP_BURGUNDY} !important;
            border-radius: 8px !important;
            font-family: Helvetica, Arial, sans-serif !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    start_over_clicked = False
    with st.container(key="start_over_row"):
        start_over_cols = st.columns([2, 1, 2])
        with start_over_cols[1]:
            start_over_clicked = st.button("Start Over", key="start_over_button", use_container_width=True)
    if start_over_clicked:
        clear_assistant_messages(st.session_state)
        st.rerun()

    chat_submission = st.chat_input("How may I help you today?")
    submit_assistant_prompt(chat_submission or topic_card_prompt)


# Show a section to add a new ticket.
st.markdown(
    f"<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: {DEEP_BURGUNDY}; margin: 0;'>Submit a ticket</h2></div>",
    unsafe_allow_html=True,
)

# We're adding tickets via an `st.form` and some input widgets. If widgets are used
# in a form, the app will only rerun once the submit button is pressed.
with st.form("add_ticket_form"):
    issue = st.text_area("Description")
    code = st.selectbox("Code", TICKET_CODES)
    priority = st.selectbox("Priority", ["Urgent", "High", "Medium", "Low"])
    submitted_by = st.text_input("Submitted by", placeholder="Enter your name")
    attachment_files = st.file_uploader(
        "Upload attachment",
        type=["heic", "heif", "jpeg", "jpg", "png"],
        accept_multiple_files=True,
    )
    submitted = st.form_submit_button("Submit ticket", type="primary")

if submitted:
    # Create a single ticket row from the form inputs and append it to the session dataframe.
    submitted_at = get_eastern_us_timestamp()
    new_ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
    df_new = pd.DataFrame(
        [
            {
                "ID": new_ticket_id,
                "Issue": issue.strip() if issue else "No description provided.",
                "Code": code,
                "Priority": priority,
                "Date Submitted": submitted_at,
                "Due Date": calculate_due_date(submitted_at),
                "Date Closed": "",
                "Submitted By": submitted_by.strip() if submitted_by.strip() else "Unknown",
                "Assigned To": CODE_ASSIGNEE_MAP.get(code, ""),
                "Notes": "",
                "Resolution Status": "Pending",
            }
        ]
    )

    if attachment_files:
        st.session_state.ticket_attachments[new_ticket_id] = [
            {"name": f.name, "data": f.read(), "mime": f.type or "application/octet-stream"}
            for f in attachment_files
        ]

    # Show a little success message.
    st.write("Ticket submitted successfully. Here are the pertinent details:")
    st.dataframe(df_new, width="stretch", hide_index=True)
    try:
        get_ticket_repository().create_ticket(df_new.iloc[0].to_dict())
    except Exception as exc:
        st.error(f"Unable to save {new_ticket_id} to Supabase: {exc}")
        st.stop()
    st.session_state.df = pd.concat([df_new, st.session_state.df], axis=0, ignore_index=True)

# Comments section for ticket Q&A.
st.markdown(
    f"<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: {DEEP_BURGUNDY}; margin: 0;'>Comments</h2></div>",
    unsafe_allow_html=True,
)
st.write("Post questions or updates related to a ticket's status or details.")

if "reply_to_comment_id" not in st.session_state:
    st.session_state.reply_to_comment_id = None

comment_ticket_options = (
    [""] + list(st.session_state.df["ID"].astype(str)) if not st.session_state.df.empty else [""]
)
comment_ticket_id = st.selectbox(
    "Select a ticket",
    options=comment_ticket_options,
    index=0,
    key="comment_ticket_selectbox",
)

comment_username = st.text_input("Your name", placeholder="Enter your name", key="comment_username")
comment_text = st.text_area("Comment", placeholder="Ask a question or post an update…", key="comment_text")

if st.button("Post comment", type="primary"):
    if not comment_ticket_id:
        st.warning("Please select a ticket.")
    elif not comment_username.strip():
        st.warning("Please enter your name.")
    elif not comment_text.strip():
        st.warning("Please enter a comment.")
    else:
        new_comment = {
            "comment_id": uuid.uuid4().hex,
            "parent_id": None,
            "ticket_id": comment_ticket_id,
            "username": comment_username.strip(),
            "comment": comment_text.strip(),
            "timestamp": get_eastern_us_timestamp(),
            "likes": [],
        }
        try:
            get_ticket_repository().create_comment(new_comment)
        except Exception as exc:
            st.error(_format_supabase_comment_error("save comment to Supabase", exc))
            st.stop()
        st.session_state.ticket_comments.append(new_comment)
        st.success("Comment posted.")
        st.rerun()


def _collect_comment_and_descendant_ids(comment_id: str, replies_by_parent: dict) -> set:
    """Return a comment's id plus all of its nested reply ids, for cascade deletes."""
    ids = {comment_id}
    for reply in replies_by_parent.get(comment_id, []):
        ids |= _collect_comment_and_descendant_ids(reply["comment_id"], replies_by_parent)
    return ids


def render_comment_thread(comment: dict, replies_by_parent: dict, depth: int = 0) -> None:
    """Render a comment card, then recursively render its replies indented beneath it."""
    comment.setdefault("likes", [])
    likes_html = ""
    if comment["likes"]:
        verb = "likes" if len(comment["likes"]) == 1 else "like"
        likes_html = (
            "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.8rem; "
            f"color: {DEEP_BURGUNDY}; margin-top: 0.4rem;'>"
            f"\U0001F44D {', '.join(comment['likes'])} {verb} this</div>"
        )
    st.markdown(
        f"<div style='margin-left: {depth * 24}px; border: 1px solid #D9D9D9; border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 0.6rem; background: #fafafa;'>"
        f"<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.82rem; color: #555; margin-bottom: 0.25rem;'>"
        f"<strong style='color: #111;'>{comment['username']}</strong> &nbsp;·&nbsp; {comment['ticket_id']} &nbsp;·&nbsp; {comment['timestamp']}"
        f"</div>"
        f"<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; color: #222;'>{comment['comment']}</div>"
        f"{likes_html}"
        f"</div>",
        unsafe_allow_html=True,
    )
    reply_button_col, like_button_col, delete_button_col = st.columns(3)
    with reply_button_col:
        is_replying = st.session_state.reply_to_comment_id == comment["comment_id"]
        reply_toggle_label = "Cancel reply" if is_replying else "Reply to this comment"
        if st.button(
            reply_toggle_label, key=f"reply_button_{comment['comment_id']}", width="stretch"
        ):
            st.session_state.reply_to_comment_id = None if is_replying else comment["comment_id"]
            st.rerun()
    with like_button_col:
        liker_name = comment_username.strip()
        already_liked = bool(liker_name) and liker_name in comment["likes"]
        like_label = "\U0001F44D Unlike" if already_liked else "\U0001F44D Like"
        if st.button(like_label, key=f"like_button_{comment['comment_id']}", width="stretch"):
            if not liker_name:
                st.markdown(
                    f"<div style='background:#FBEAEC;border:1px solid {DEEP_BURGUNDY};color:{DEEP_BURGUNDY};"
                    "padding:0.75rem 1rem;border-radius:8px;font-family: Helvetica, Arial, sans-serif; font-size:0.95rem;'>"
                    "Please enter your name above before liking a comment."
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                updated_likes = list(comment["likes"])
                if already_liked:
                    updated_likes.remove(liker_name)
                else:
                    updated_likes.append(liker_name)
                try:
                    get_ticket_repository().update_comment_likes(comment["comment_id"], updated_likes)
                except Exception as exc:
                    st.error(_format_supabase_comment_error("save like to Supabase", exc))
                    st.stop()
                comment["likes"] = updated_likes
                st.rerun()
    with delete_button_col:
        delete_label = "Delete reply" if depth > 0 else "Delete comment"
        if st.button(delete_label, key=f"delete_button_{comment['comment_id']}", width="stretch"):
            ids_to_remove = _collect_comment_and_descendant_ids(comment["comment_id"], replies_by_parent)
            try:
                get_ticket_repository().delete_comments(list(ids_to_remove))
            except Exception as exc:
                st.error(_format_supabase_comment_error("delete comment from Supabase", exc))
                st.stop()
            st.session_state.ticket_comments = [
                c for c in st.session_state.ticket_comments if c["comment_id"] not in ids_to_remove
            ]
            if st.session_state.reply_to_comment_id in ids_to_remove:
                st.session_state.reply_to_comment_id = None
            st.rerun()

    # Inline reply box, indented to sit directly under the comment being replied to —
    # mirrors typical threaded-chat reply UX (Teams/Facebook) instead of a shared box.
    if st.session_state.reply_to_comment_id == comment["comment_id"]:
        _reply_indent_col, reply_form_col = st.columns([depth + 1, 10])
        with reply_form_col:
            reply_name = st.text_input(
                "Your name", placeholder="Enter your name", key=f"reply_name_{comment['comment_id']}"
            )
            reply_text = st.text_area(
                "Reply", placeholder=f"Reply to {comment['username']}…",
                key=f"reply_text_{comment['comment_id']}",
            )
            post_reply_col, cancel_reply_col = st.columns(2)
            with post_reply_col:
                post_reply_clicked = st.button(
                    "Post reply", key=f"post_reply_{comment['comment_id']}", type="primary", width="stretch"
                )
            with cancel_reply_col:
                if st.button("Cancel", key=f"cancel_reply_{comment['comment_id']}", width="stretch"):
                    st.session_state.reply_to_comment_id = None
                    st.rerun()
            if post_reply_clicked:
                if not reply_name.strip():
                    st.warning("Please enter your name.")
                elif not reply_text.strip():
                    st.warning("Please enter a reply.")
                else:
                    new_reply = {
                        "comment_id": uuid.uuid4().hex,
                        "parent_id": comment["comment_id"],
                        "ticket_id": comment["ticket_id"],
                        "username": reply_name.strip(),
                        "comment": reply_text.strip(),
                        "timestamp": get_eastern_us_timestamp(),
                        "likes": [],
                    }
                    try:
                        get_ticket_repository().create_comment(new_reply)
                    except Exception as exc:
                        st.error(_format_supabase_comment_error("save reply to Supabase", exc))
                        st.stop()
                    st.session_state.ticket_comments.append(new_reply)
                    st.session_state.reply_to_comment_id = None
                    st.success("Reply posted.")
                    st.rerun()

    for reply in sorted(
        replies_by_parent.get(comment["comment_id"], []), key=lambda c: c["timestamp"]
    ):
        render_comment_thread(reply, replies_by_parent, depth + 1)


# Comments and their reply threads only populate once a specific ticket is selected.
if comment_ticket_id:
    visible_comments = [
        c for c in st.session_state.ticket_comments if c["ticket_id"] == comment_ticket_id
    ]
    replies_by_parent: dict = {}
    for c in visible_comments:
        replies_by_parent.setdefault(c.get("parent_id"), []).append(c)

    root_comments = [c for c in visible_comments if not c.get("parent_id")]
    if root_comments:
        for root in reversed(root_comments):
            render_comment_thread(root, replies_by_parent)
    else:
        st.markdown(
            f"<div style='background:#FBEAEC;border:1px solid {DEEP_BURGUNDY};color:{DEEP_BURGUNDY};"
            "padding:0.75rem 1rem;border-radius:8px;font-family: Helvetica, Arial, sans-serif; font-size:0.95rem;'>"
            f"No comments yet for {comment_ticket_id}."
            "</div>",
            unsafe_allow_html=True,
        )

