import base64
import datetime
import importlib.util
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from streamlit.components.v1 import html as components_html
except ImportError:  # pragma: no cover
    components_html = None

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

try:
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
        get_eastern_us_timestamp,
        sanitize_ticket_dataframe,
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
    calculate_average_resolution_time_hours = (
        ticket_data_module.calculate_average_resolution_time_hours
    )
    calculate_average_closed_tickets_per_week = (
        ticket_data_module.calculate_average_closed_tickets_per_week
    )
    calculate_average_open_tickets_per_week = (
        ticket_data_module.calculate_average_open_tickets_per_week
    )
    calculate_high_priority_open_ticket_count = (
        ticket_data_module.calculate_high_priority_open_ticket_count
    )
    calculate_open_ticket_count = ticket_data_module.calculate_open_ticket_count
    calculate_resolution_rate = ticket_data_module.calculate_resolution_rate
    create_initial_ticket_dataframe = ticket_data_module.create_initial_ticket_dataframe
    delete_ticket_by_id = ticket_data_module.delete_ticket_by_id
    filter_tickets_by_code = ticket_data_module.filter_tickets_by_code
    filter_tickets_by_id = ticket_data_module.filter_tickets_by_id
    sanitize_ticket_dataframe = ticket_data_module.sanitize_ticket_dataframe
    TICKET_CODES = ticket_data_module.TICKET_CODES

from ticket_repository import SupabaseTicketRepository, validate_supabase_url

# Show app title and description.
BRAND_COLORS = ["#111111", "#D9D9D9", "#7A1F2D"]

st.set_page_config(
    page_title="DC05 ISP",
    page_icon="💻",
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
    [data-testid="stDataFrame"] [aria-colindex="2"], [data-testid="stDataFrame"] [aria-colindex="2"] * {{ white-space: pre-wrap !important; overflow-wrap: anywhere !important; }}
    [data-testid="stMetricLabel"] {{ white-space: normal !important; overflow-wrap: anywhere !important; line-height: 1.25 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Avoid runtime issues when the app is launched in a headless/container environment.
if not st.runtime.exists():
    st.session_state.setdefault("_headless_runtime", True)

APP_PASSWORD = "Platinum2025"

if not st.session_state.get("authenticated", False):
    st.markdown(
        "<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: #000000;'>DC05 | Internal Support Portal</h1></div>",
        unsafe_allow_html=True,
    )
    entered_password = st.text_input("Password", type="password")
    login_clicked = st.button("Log in")
    if login_clicked:
        if entered_password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("The password you entered is incorrect. Please try again.")
    st.stop()

st.markdown(
    "<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: #000000; white-space: nowrap; overflow-x: auto;'>DC05 | Internal Support Portal</h1></div>",
    unsafe_allow_html=True,
)

st.write(
    """
    Please use this system to request assistance, and/or submit a support ticket for issues related to: JDA, CSW, SAP, SmartSheet, SharePoint,
Excel, Power Platform, Opendock Nova, UKG WFM, Workday HCM, Honeywell CT47 model RFID devices, Honeywell RP4D mobile printers, Zebra ZT620 model label printers, Ricoh IM 460F model multi-function printers, HAI Robotics deployments (HaiPick Systems suite), wireless internet, ethernet, Bluetooth, end user credentials, continuous improvement, inventory control, quality control, industrial automation, facilities management, maintenance, and/or industrial hygiene.
    """
)

@st.cache_resource(show_spinner=False)
def get_ticket_repository() -> SupabaseTicketRepository:
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





def call_local_support_assistant(prompt: str) -> str:
    prompt_text = (prompt or "support request").strip()
    lowered_prompt = prompt_text.lower()

    if any(term in lowered_prompt for term in ["printer", "print", "zebra", "zt620", "label printer", "ricoh", "im 460f", "460f", "honeywell", "rp4d", "mobile printer", "copier", "copy", "scan", "fax", "mfp", "multi-function"]):
        zebra_tip = (
            "For a Zebra ZT620 label printer: check that the label roll is loaded correctly and the media type/size in the printer settings matches the labels you're using. "
            "If labels are printing blank or misaligned, run calibration from the printer front panel (hold Feed + Cancel on power-up). "
            "If the printer shows a fault light, note the color pattern and include it in your ticket."
        )
        rp4d_tip = (
            "For a Honeywell RP4D mobile printer: confirm the battery is charged and fully seated, then restart the printer. "
            "Check that the paper roll is loaded with the printable side facing the print head and that the cover is latched. "
            "If it will not connect, turn Bluetooth or Wi-Fi off and back on, then re-pair the printer with the handheld device. "
            "Run a test label from the printer settings and include any status-light pattern or error message in your ticket."
        )
        ricoh_tip = (
            "For a Ricoh IM 460F multi-function printer: if it will not print, check the touchscreen for any error or paper-jam indicators and clear them first. "
            "For scan-to-email or scan-to-folder issues, verify network connectivity and confirm the destination address or folder path is still correct. "
            "For fax issues, check that the phone line is connected to the LINE port (not TEL), then power cycle the unit from the power button."
        )
        return (
            "Sounds like a printer issue. I can help you troubleshoot a Zebra ZT620 label printer, Honeywell RP4D mobile printer, or Ricoh IM 460F multi-function printer. "
            + zebra_tip + " " + rp4d_tip + " " + ricoh_tip +
            " If it is still not cooperating, submit a ticket and include the exact model plus any error code shown on the device."
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
                "For a Honeywell CT47 handheld RFID device: start with a clean reboot — hold the power button and select Reboot. "
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

    if any(term in lowered_prompt for term in ["inventory", "cycle count", "sap", "stock", "on-hand", "on hand", "putaway", "pick", "replenishment"]):
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

    if any(term in lowered_prompt for term in ["robot", "robotics", "cobot", "agv", "amr", "haipick", "hai pick", "hai robotics", "acr", "a3", "a3s", "a3el"]):
        return (
            "Robotics question — sounds like it could be a HaiPick system! "
            "If a HaiPick ACR (like an A3, A3S, or A3EL unit) has stopped mid-task, first check whether a safety stop or e-stop was triggered — the robot's status light will flash amber or red if so. "
            "Clear any obstructions from the travel path and check the HAI Robotics management console (RCS) for an active alarm or fault code before attempting a manual reset. "
            "If the RCS shows a charging fault, verify the charging station contacts are clean and the robot is correctly docked. "
            "For bin-retrieval errors or WMS integration issues (e.g., tasks queuing but not executing), check the RCS task queue and confirm the WMS interface is still connected. "
            "Never manually move a stopped unit without first confirming in the RCS that it is safe to do so. "
            "Note the robot ID, fault code, and what it was doing when it stopped, then submit a ticket and we'll get a technician on it!"
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
        "Hello! I am Owen, your support assistant. I can help with technical issues involving hardware, software, peripherals, JDA, CSW, SAP, SmartSheet, SharePoint, Excel, Power Platform, Opendock Nova, UKG WFM, Workday HCM, "
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
    "RFID and barcode handheld devices (specifically the Honeywell CT47 — reboots, Wi-Fi reconnection, scan window cleaning, and factory-image requests); "
    "software (applications, installs, updates, "
    "licensing, drivers, crashes, and error messages); peripherals (keyboards, mice, webcams, headsets, docking stations, "
    "and USB devices); the Blue Yonder/JDA warehouse management system (WMS); "
    "the Client Server Warehousing (CSW) WMS; SAP; SmartSheet; SharePoint; Excel; Microsoft Power Platform "
    "(Power BI, Power Apps, Power Automate, and Power Pages); Opendock Nova dock scheduling; "
    "UKG WFM (timecard management, scheduling, time-off requests, and punch corrections); "
    "Workday HCM (payroll, benefits, direct deposit, W-2s, employee profiles, onboarding/offboarding, and org changes); "
    "continuous improvement; "
    "warehouse-centric inventory control; quality control; industrial automation (PLCs, SCADA, conveyors, sortation); "
    "robotics — specifically the HAI Robotics HaiPick suite of Autonomous Case-handling Robots (ACRs), including the A3, A3S, and A3EL models "
    "(covering RCS console alarms, fault codes, e-stop and safety-stop recovery, charging station issues, travel-path obstructions, bin-retrieval errors, and WMS/RCS integration); "
    "statistical process control (SPC); and statistical quality control (SQC). "
    "Answer with the depth and accuracy of a subject-matter expert on each of these topics, but always translate that "
    "expertise into casual, plain, layman's terms for a non-technical audience — avoid jargon, and explain any "
    "technical term you do use. Keep replies short and conversational. Do not mention ticket counts or system context. "
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
    return call_local_support_assistant(prompt)


def clear_assistant_messages(session_state: dict) -> None:
    """Clear the visible assistant conversation history for a fresh prompt."""
    session_state["assistant_messages"] = []


if "assistant_messages" not in st.session_state:
    st.session_state.assistant_messages = []

assistant_container = st.container()
with assistant_container:
    logo_path = APP_ROOT / "Owen-GPT.png"
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
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1rem; font-weight: 700; color: #111111; margin-bottom: 0.35rem;'>Ask Owen — Your On-Prem Technical Support Agent</div>"
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; color: #333333; line-height: 1.45;'>"
        "After hours? Not a problem! Owen is always available locally to assist with an array of Tier-1 technical support issues. Just ask."
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

    chat_submission = st.chat_input("How may I help you today?")
    if chat_submission:
        prompt = (chat_submission or "").strip()

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
            st.session_state.assistant_messages.append({
                "role": "assistant",
                "content": f"I hit a local issue while preparing a response: {exc}",
            })
            with st.chat_message("assistant", avatar=None):
                st.markdown(f"I hit a local issue while preparing a response: {exc}")


# Show a section to add a new ticket.
st.markdown(
    "<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: #000000; margin: 0;'>Submit a ticket</h2></div>",
    unsafe_allow_html=True,
)

# We're adding tickets via an `st.form` and some input widgets. If widgets are used
# in a form, the app will only rerun once the submit button is pressed.
with st.form("add_ticket_form"):
    issue = st.text_area("Describe the issue")
    code = st.selectbox("Code", TICKET_CODES)
    priority = st.selectbox("Priority", ["Urgent", "High", "Medium", "Low"])
    submitted_by = st.text_input("Submitted by", placeholder="Enter your name")
    attachment_files = st.file_uploader(
        "Attachments (optional)",
        type=["heic", "heif", "jpeg", "jpg", "png"],
        accept_multiple_files=True,
    )
    submitted = st.form_submit_button("Submit")

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
                "Date Closed": "",
                "Submitted By": submitted_by.strip() if submitted_by.strip() else "Unknown",
                "Assigned To": "",
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
    st.session_state.df = pd.concat([df_new, st.session_state.df], axis=0)

# Show section to view and edit existing tickets in a table.
st.markdown(
    "<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: #000000; margin: 0;'>Existing tickets</h2></div>",
    unsafe_allow_html=True,
)
st.write(f"Number of tickets: `{len(st.session_state.df)}`")

filter_col, search_col = st.columns([1, 2])
with filter_col:
    selected_code = st.selectbox("Filter by Code", options=["All", *TICKET_CODES])
with search_col:
    search_term = st.text_input(
        "Search tickets by ticket number", placeholder="e.g. TICKET-1010"
    )
filtered_df = filter_tickets_by_id(st.session_state.df, search_term)
filtered_df = filter_tickets_by_code(filtered_df, selected_code)

# Allow the user to delete a ticket by selecting its ID.
selected_ticket_id = st.selectbox(
    "Delete a ticket",
    options=[""] + list(st.session_state.df["ID"].astype(str)) if not st.session_state.df.empty else [""],
    index=0,
    key="delete_ticket_selectbox",
)

if st.button("Delete selected ticket") and selected_ticket_id:
    try:
        get_ticket_repository().delete_ticket(selected_ticket_id)
    except Exception as exc:
        st.error(f"Unable to delete {selected_ticket_id} from Supabase: {exc}")
        st.stop()
    st.session_state.df = delete_ticket_by_id(st.session_state.df, selected_ticket_id)
    st.session_state.ticket_attachments.pop(selected_ticket_id, None)
    st.session_state.ticket_comments = [
        c for c in st.session_state.ticket_comments if c["ticket_id"] != selected_ticket_id
    ]
    st.success(f"Deleted {selected_ticket_id}.")
    st.rerun()

# Color-coded read-only view of the resolution status.
_STATUS_STYLES = {
    "Pending": "background-color: #ffe0e0; color: #c00000; font-weight: 600;",
    "In Process": "background-color: #fff3cd; color: #856404; font-weight: 600;",
    "Resolved": "background-color: #d4edda; color: #155724; font-weight: 600;",
}

def _style_ticket_status_col(col):
    return col.map(lambda v: _STATUS_STYLES.get(v, ""))

if not filtered_df.empty and "Resolution Status" in filtered_df.columns:
    styled_view = (
        filtered_df.style.apply(
            _style_ticket_status_col, subset=["Resolution Status"], axis=0
        )
        .set_properties(
            subset=["Issue"], **{"white-space": "pre-wrap", "overflow-wrap": "anywhere"}
        )
    )
    st.markdown(
        "<div style='margin: 0.75rem 0 0.25rem 0;'><span style='font-family: Helvetica, Arial, sans-serif; font-size: 0.88rem; color: #555;'>" 
        "Status legend: "
        "<span style='background:#ffe0e0;color:#c00000;font-weight:600;padding:1px 7px;border-radius:4px;margin-right:6px;'>Pending</span>"
        "<span style='background:#fff3cd;color:#856404;font-weight:600;padding:1px 7px;border-radius:4px;margin-right:6px;'>In Process</span>"
        "<span style='background:#d4edda;color:#155724;font-weight:600;padding:1px 7px;border-radius:4px;'>Resolved</span>"
        "</span></div>",
        unsafe_allow_html=True,
    )
    st.dataframe(
        styled_view,
        use_container_width=True,
        hide_index=True,
        row_height=72,
        column_config={
            "Issue": st.column_config.TextColumn("Issue", width="large"),
        },
    )

# Editable table — use data_editor for all field edits.
st.markdown(
    "<div style='margin: 1rem 0 0.25rem 0;'><span style='font-family: Helvetica, Arial, sans-serif; font-size: 0.9rem; font-weight: 600; color: #333;'>Edit tickets</span></div>",
    unsafe_allow_html=True,
)
editor_df = filtered_df.copy()
if "Date Closed" in editor_df.columns:
    editor_df["Date Closed"] = editor_df["Date Closed"].replace("", " ")

edited_df = st.data_editor(
    editor_df,
    width="stretch",
    hide_index=True,
    column_config={
        "Issue": st.column_config.TextColumn(
            "Issue",
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
        "Resolution Status": st.column_config.SelectboxColumn(
            "Resolution Status",
            help="Current resolution status",
            options=["Pending", "In Process", "Resolved"],
            required=True,
        ),
        "Date Closed": st.column_config.TextColumn(
            "Date Closed",
            default="",
        ),
    },
    # Disable editing the ID, Date Submitted, and Date Closed columns.
    disabled=["ID", "Date Submitted", "Date Closed"],
)
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

# Ticket detail: show attachments for a selected ticket.
st.markdown(
    "<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: #000000; margin: 0;'>Ticket attachments</h2></div>",
    unsafe_allow_html=True,
)
ticket_ids_with_attachments = [
    tid for tid in st.session_state.df["ID"].astype(str).tolist()
    if tid in st.session_state.ticket_attachments
]
detail_ticket_id = st.selectbox(
    "Select a ticket to view its attachments",
    options=[""] + list(st.session_state.df["ID"].astype(str)) if not st.session_state.df.empty else [""],
    index=0,
    key="detail_ticket_selectbox",
)

if detail_ticket_id:
    attachments = st.session_state.ticket_attachments.get(detail_ticket_id, [])
    if attachments:
        st.write(f"{len(attachments)} attachment(s) for **{detail_ticket_id}**:")
        for attachment in attachments:
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
                )
    else:
        st.info(f"No attachments for {detail_ticket_id}.")

# Show some metrics and charts about the ticket.
st.markdown(
    "<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: #000000; margin: 0;'>Statistics</h2></div>",
    unsafe_allow_html=True,
)

CODE_KPI_LABELS = {
    "IT": (
        "Open IT incidents",
        "Urgent IT incidents",
        "IT resolution rate",
        "Average IT resolution time (hours)",
    ),
    "CI": (
        "Open improvement requests",
        "Urgent improvement requests",
        "Improvement completion rate",
        "Average improvement cycle time (hours)",
    ),
    "Maintenance": (
        "Open maintenance work orders",
        "Urgent maintenance work orders",
        "Work order completion rate",
        "Average repair time (hours)",
    ),
    "Custodial": (
        "Open custodial requests",
        "Urgent custodial requests",
        "Custodial completion rate",
        "Average request completion time (hours)",
    ),
}

for code_pair in (("IT", "CI"), ("Maintenance", "Custodial")):
    left_code_col, right_code_col = st.columns(2)
    for code_name, code_column in zip(code_pair, (left_code_col, right_code_col)):
        code_tickets = filter_tickets_by_code(st.session_state.df, code_name)
        open_ticket_count = calculate_open_ticket_count(code_tickets)
        high_priority_open_ticket_count = calculate_high_priority_open_ticket_count(
            code_tickets
        )
        resolution_rate = calculate_resolution_rate(code_tickets)
        average_resolution_time_hours = calculate_average_resolution_time_hours(
            code_tickets
        )
        open_label, urgent_label, rate_label, time_label = CODE_KPI_LABELS[code_name]

        with code_column:
            st.markdown(
                f"<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1.05rem; font-weight: 700; color: #000000; margin: 0.5rem 0;'>{code_name}</div>",
                unsafe_allow_html=True,
            )
            metric_left, metric_right = st.columns(2)
            with metric_left:
                st.metric(open_label, format_stat_value(open_ticket_count))
                st.metric(rate_label, f"{format_stat_value(resolution_rate)}%")
            with metric_right:
                st.metric(urgent_label, format_stat_value(high_priority_open_ticket_count))
                st.metric(time_label, format_stat_value(average_resolution_time_hours))

# Comments section for ticket Q&A.
st.markdown(
    "<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: #000000; margin: 0;'>Comments</h2></div>",
    unsafe_allow_html=True,
)
st.write("Post questions or updates related to a ticket's status or details.")

if "ticket_comments" not in st.session_state:
    st.session_state.ticket_comments = []

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

if st.button("Post comment"):
    if not comment_ticket_id:
        st.warning("Please select a ticket.")
    elif not comment_username.strip():
        st.warning("Please enter your name.")
    elif not comment_text.strip():
        st.warning("Please enter a comment.")
    else:
        st.session_state.ticket_comments.append({
            "ticket_id": comment_ticket_id,
            "username": comment_username.strip(),
            "comment": comment_text.strip(),
            "timestamp": get_eastern_us_timestamp(),
        })
        st.success("Comment posted.")
        st.rerun()

# Display existing comments, newest first.
ticket_comments_to_show = [
    c for c in reversed(st.session_state.ticket_comments)
    if not comment_ticket_id or c["ticket_id"] == comment_ticket_id
]
if ticket_comments_to_show:
    for entry in ticket_comments_to_show:
        st.markdown(
            f"<div style='border: 1px solid #D9D9D9; border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 0.6rem; background: #fafafa;'>"
            f"<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.82rem; color: #555; margin-bottom: 0.25rem;'>"
            f"<strong style='color: #111;'>{entry['username']}</strong> &nbsp;·&nbsp; {entry['ticket_id']} &nbsp;·&nbsp; {entry['timestamp']}"
            f"</div>"
            f"<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; color: #222;'>{entry['comment']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
elif comment_ticket_id:
    st.info(f"No comments yet for {comment_ticket_id}.")
