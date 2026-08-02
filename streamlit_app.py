import base64
import datetime
import importlib.util
import os
import sys
from pathlib import Path

import altair as alt
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
        calculate_average_closed_tickets_per_week,
        calculate_average_open_tickets_per_week,
        create_initial_ticket_dataframe,
        delete_ticket_by_id,
        filter_tickets_by_id,
        sanitize_ticket_dataframe,
    )
except ImportError:
    ticket_data_spec = importlib.util.spec_from_file_location(
        "ticket_data", APP_ROOT / "ticket_data.py"
    )
    if ticket_data_spec is None or ticket_data_spec.loader is None:
        raise

    ticket_data_module = importlib.util.module_from_spec(ticket_data_spec)
    ticket_data_spec.loader.exec_module(ticket_data_module)
    calculate_average_closed_tickets_per_week = (
        ticket_data_module.calculate_average_closed_tickets_per_week
    )
    calculate_average_open_tickets_per_week = (
        ticket_data_module.calculate_average_open_tickets_per_week
    )
    create_initial_ticket_dataframe = ticket_data_module.create_initial_ticket_dataframe
    delete_ticket_by_id = ticket_data_module.delete_ticket_by_id
    filter_tickets_by_id = ticket_data_module.filter_tickets_by_id
    sanitize_ticket_dataframe = ticket_data_module.sanitize_ticket_dataframe

# Show app title and description.
BRAND_COLORS = ["#111111", "#D9D9D9", "#7A1F2D"]

st.set_page_config(
    page_title="Support tickets",
    page_icon="💻",
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
    </style>
    """,
    unsafe_allow_html=True,
)

# Avoid runtime issues when the app is launched in a headless/container environment.
if not st.runtime.exists():
    st.session_state.setdefault("_headless_runtime", True)

APP_PASSWORD = "Platinum"

if not st.session_state.get("authenticated", False):
    st.markdown(
        "<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: #000000;'>O&M P&HS | Internal Support Portal</h1></div>",
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
        entered_password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        if entered_password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")
    st.stop()

st.markdown(
    "<div style='padding: 0.5rem 0 1rem 0;'><h1 style='font-family: Helvetica, Arial, sans-serif; font-weight: 700; font-size: 2rem; margin: 0; color: #000000; white-space: nowrap; overflow-x: auto;'>O&M P&HS | Internal Support Portal</h1></div>",
    unsafe_allow_html=True,
)

st.write(
    """
    Please feel free to use this system to get help, and/or submit a ticketing request for technical support issues pertaining to: JDA, CSW, SAP, SmartSheet, SharePoint, 
Excel, Power Platform, Opendock Nova, continuous improvement, inventory control, quality control, industrial automation, and/or robotics.
    """
)

# Create the starter dataframe and reset it when the app data version changes.
TICKET_DATA_VERSION = 2
if (
    "df" not in st.session_state
    or "ticket_data_version" not in st.session_state
    or st.session_state.ticket_data_version != TICKET_DATA_VERSION
):
    st.session_state.df = create_initial_ticket_dataframe()
    st.session_state.ticket_data_version = TICKET_DATA_VERSION

st.session_state.df = sanitize_ticket_dataframe(st.session_state.df)


def format_stat_value(value: float | int) -> str:
    return f"{float(value):.2f}"


def call_local_support_assistant(prompt: str) -> str:
    prompt_text = (prompt or "support request").strip()
    lowered_prompt = prompt_text.lower()

    if any(term in lowered_prompt for term in ["printer", "print"]):
        return (
            "Hey! Sounds like your printer is giving you trouble. First, make sure it's turned on and all the cables are plugged in (or that it's connected to the Wi-Fi). "
            "Check that there's paper in the tray and nothing is jammed. If it still won't print, try turning it off, waiting 10 seconds, and turning it back on. "
            "If that doesn't fix it, go ahead and submit a ticket and someone will come take a look!"
        )

    if any(term in lowered_prompt for term in ["wifi", "wi-fi", "wireless", "network", "connect", "internet"]):
        return (
            "Ugh, internet issues are the worst! Try turning your device's Wi-Fi off and back on first. "
            "If that doesn't help, try forgetting the network and reconnecting. "
            "Still stuck? Check if anyone else nearby is having the same problem — if so, it might be on our end and we'll get it sorted. Submit a ticket and we'll jump on it!"
        )

    if any(term in lowered_prompt for term in ["radio", "rf", "rfid", "bluetooth", "scanner", "device", "peripheral"]):
        return (
            "Looks like a device issue! Start by turning it off and back on. "
            "If it pairs wirelessly, try unpairing it and pairing it again from scratch. "
            "Make sure the battery isn't low too — that can cause all kinds of weird behavior. If it's still acting up, submit a ticket and we'll take a look!"
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

    if any(term in lowered_prompt for term in ["power bi", "powerbi", "bi report", "bi dashboard", "power platform", "power apps", "power automate", "power pages", "powerapps"]):
        return (
            "Power Platform question (Power BI, Power Apps, Power Automate, or Power Pages)? No problem! "
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

    if any(term in lowered_prompt for term in ["automation", "plc", "scada", "conveyor", "sortation", "sorter", "industrial control"]):
        return (
            "Industrial automation issue? Let's get it moving again! If a conveyor, sorter, or PLC-controlled system faulted out, check for a visible fault code or e-stop that's been triggered first. "
            "A lot of these systems just need a fault to be cleared and a reset before they'll run again — but don't force anything that seems unsafe. "
            "Note the fault code or what you're seeing, then submit a ticket so a technician can take a closer look!"
        )

    if any(term in lowered_prompt for term in ["robot", "robotics", "cobot", "agv", "amr"]):
        return (
            "Robotics question? Interesting! If a robot or AGV/AMR stopped or is acting oddly, check for an obvious safety stop, blocked path, or error light first. "
            "Most of these systems are built to pause safely rather than force through a problem, so a stopped robot is often just waiting for a clear path or a reset. "
            "Note what it was doing and any error shown, then submit a ticket and we'll get a technician on it!"
        )

    if any(term in lowered_prompt for term in ["excel", "spreadsheet", "formula", "pivot", "vlookup", "macro"]):
        return (
            "Excel question? Love it! Whether it's a formula that's not working, a pivot table that looks wrong, or you need help automating something, we can help. "
            "If you're getting an error, take a screenshot of it and include it in your ticket. "
            "If you need something built from scratch, just describe what you're trying to do in plain terms and we'll figure out the best way to do it!"
        )

    if any(term in lowered_prompt for term in ["password", "login", "locked", "ldap", "vpn", "access", "sign in"]):
        return (
            "Can't get in? No worries, it happens! Double-check you're using the right username and that Caps Lock isn't on. "
            "If your account is locked, you'll need to submit a ticket and we'll get it unlocked for you right away. "
            "If you're trying to connect through VPN and it's not working, try disconnecting and reconnecting. We've got you covered!"
        )

    if any(term in lowered_prompt for term in ["slow", "frozen", "crash", "restart", "computer", "pc", "laptop", "screen"]):
        return (
            "Ugh, a slow or frozen computer is so frustrating! First, try saving anything open and restarting — that fixes more than you'd think. "
            "If it keeps happening, make a note of what you were doing when it froze and submit a ticket. "
            "We can take a look and figure out if it needs a tune-up or something more. Hang tight!"
        )

    return (
        "Hey there! I'm Owen, your support helper. I can help with tech issues, JDA, CSW, SAP, SmartSheet, SharePoint, Excel, Power Platform, Opendock Nova, "
        "inventory control, quality control, industrial automation, robotics, SPC, SQC, and more. "
        "Just describe what's going on in your own words — no technical jargon needed — and I'll point you in the right direction. "
        "If we need to dig deeper, just submit a ticket and our team will come to you!"
    )


GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
GITHUB_MODELS_MODEL = "gpt-4o-mini"

GITHUB_MODELS_SYSTEM_PROMPT = (
    "You are Owen, an internal on-prem technical support agent with expert-level knowledge across the following systems and topics: "
    "everyday tech issues (printers, Wi-Fi, devices, logins); the Blue Yonder/JDA warehouse management system (WMS); "
    "the Client Server Warehousing (CSW) WMS; SAP; SmartSheet; SharePoint; Excel; Microsoft Power Platform "
    "(Power BI, Power Apps, Power Automate, and Power Pages); Opendock Nova dock scheduling; continuous improvement; "
    "warehouse-centric inventory control; quality control; industrial automation (PLCs, SCADA, conveyors, sortation); "
    "robotics (AGVs, AMRs, cobots); statistical process control (SPC); and statistical quality control (SQC). "
    "Answer with the depth and accuracy of a subject-matter expert on each of these topics, but always translate that "
    "expertise into casual, plain, layman's terms for a non-technical audience — avoid jargon, and explain any "
    "technical term you do use. Keep replies short and conversational. Do not mention ticket counts or system context. "
    "You also have general knowledge of Platinum Equity, LLC (a private equity firm) and Owens & Minor Products & "
    "Healthcare Services (Owens & Minor, or simply O&M), the healthcare products and services company this support "
    "system belongs to, in case users ask general questions about either company. "
    "If the issue needs a technician, suggest the user submit a ticket in this app."
)


@st.cache_resource(show_spinner=False)
def _get_github_models_client():
    token = os.environ.get("GITHUB_TOKEN")
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

    try:
        response = client.chat.completions.create(
            model=GITHUB_MODELS_MODEL,
            messages=[
                {"role": "system", "content": GITHUB_MODELS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def get_assistant_reply(prompt: str) -> str:
    llm_reply = call_github_models_support_assistant(prompt)
    if llm_reply:
        return llm_reply
    return call_local_support_assistant(prompt)


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
        "After hours? No problem! Owen is always available locally to help with radio, printer, RFID, Bluetooth, Wi-Fi, WMS, Excel, Power BI, and other technical issues. Just ask!"
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

    if prompt := st.chat_input("What seems to be the problem?"):
        st.session_state.assistant_messages.append({"role": "user", "content": prompt.strip()})
        with st.chat_message("user", avatar=None):
            st.markdown(prompt.strip())

        try:
            with st.spinner("Thinking..."):
                reply = get_assistant_reply(prompt.strip())
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
st.header("Submit a ticket")

# We're adding tickets via an `st.form` and some input widgets. If widgets are used
# in a form, the app will only rerun once the submit button is pressed.
with st.form("add_ticket_form"):
    issue = st.text_area("Describe the issue")
    priority = st.selectbox("Priority", ["High", "Medium", "Low"])
    submitted = st.form_submit_button("Submit")

if submitted:
    # Create a single ticket row from the form inputs and append it to the session dataframe.
    recent_ticket_number = (
        int(max(st.session_state.df.ID).split("-")[1]) if not st.session_state.df.empty else 999
    )
    today = datetime.datetime.now().strftime("%m-%d-%Y")
    df_new = pd.DataFrame(
        [
            {
                "ID": f"TICKET-{recent_ticket_number + 1}",
                "Issue": issue.strip() if issue else "No description provided.",
                "Status": "Open",
                "Priority": priority,
                "Date Submitted": today,
            }
        ]
    )

    # Show a little success message.
    st.write("Ticket submitted successfully. Here are the pertinent details:")
    st.dataframe(df_new, width="stretch", hide_index=True)
    st.session_state.df = pd.concat([df_new, st.session_state.df], axis=0)

# Show section to view and edit existing tickets in a table.
st.header("Existing tickets")
st.write(f"Number of tickets: `{len(st.session_state.df)}`")

search_term = st.text_input("Search tickets by ticket number", placeholder="e.g. TICKET-1010")
filtered_df = filter_tickets_by_id(st.session_state.df, search_term)

# Allow the user to delete a ticket by selecting its ID.
selected_ticket_id = st.selectbox(
    "Delete a ticket",
    options=[""] + list(st.session_state.df["ID"].astype(str)) if not st.session_state.df.empty else [""],
    index=0,
    key="delete_ticket_selectbox",
)

if st.button("Delete selected ticket") and selected_ticket_id:
    st.session_state.df = delete_ticket_by_id(st.session_state.df, selected_ticket_id)
    st.success(f"Deleted {selected_ticket_id}.")
    st.rerun()

# Show the tickets dataframe with `st.data_editor`. This lets the user edit the table
# cells. The edited data is returned as a new dataframe.
edited_df = st.data_editor(
    filtered_df,
    width="stretch",
    hide_index=True,
    column_config={
        "Status": st.column_config.SelectboxColumn(
            "Status",
            help="Ticket status",
            options=["Open", "In Progress", "Closed"],
            required=True,
        ),
        "Priority": st.column_config.SelectboxColumn(
            "Priority",
            help="Priority",
            options=["High", "Medium", "Low"],
            required=True,
        ),
    },
    # Disable editing the ID and Date Submitted columns.
    disabled=["ID", "Date Submitted"],
)

st.session_state.df = edited_df

# Show some metrics and charts about the ticket.
st.markdown(
    "<div style='margin: 1.5rem 0 0.5rem 0;'><h2 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.4rem; font-weight: 700; color: #000000; margin: 0;'>Statistics</h2></div>",
    unsafe_allow_html=True,
)

# Show metrics side by side using `st.columns` and `st.metric`.
col1, col2, col3, col4 = st.columns(4)
num_open_tickets = len(st.session_state.df[st.session_state.df.Status == "Open"])
avg_open_per_week = calculate_average_open_tickets_per_week(st.session_state.df)
avg_closed_per_week = calculate_average_closed_tickets_per_week(st.session_state.df)

with col1:
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; font-weight: 700; color: #000000; line-height: 1.4; margin-bottom: 0.35rem; min-height: 2.8rem; display: flex; align-items: flex-start;'>Total # of open tickets</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1.15rem; font-weight: 700; color: #000000; text-align: left; min-height: 1.6rem;'>" + format_stat_value(num_open_tickets) + "</div>",
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; font-weight: 700; color: #000000; line-height: 1.4; margin-bottom: 0.35rem; min-height: 2.8rem; display: flex; align-items: flex-start;'>Average # of open tickets per week</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1.15rem; font-weight: 700; color: #000000; text-align: left; min-height: 1.6rem;'>" + format_stat_value(avg_open_per_week) + "</div>",
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; font-weight: 700; color: #000000; line-height: 1.4; margin-bottom: 0.35rem; min-height: 2.8rem; display: flex; align-items: flex-start;'>Average # of tickets closed per week</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1.15rem; font-weight: 700; color: #000000; text-align: left; min-height: 1.6rem;'>" + format_stat_value(avg_closed_per_week) + "</div>",
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 0.95rem; font-weight: 700; color: #000000; line-height: 1.4; margin-bottom: 0.35rem; min-height: 2.8rem; display: flex; align-items: flex-start;'>First response time (hours)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-family: Helvetica, Arial, sans-serif; font-size: 1.15rem; font-weight: 700; color: #000000; text-align: left; min-height: 1.6rem;'>" + format_stat_value(0) + "</div>",
        unsafe_allow_html=True,
    )

# Show two Altair charts using `st.altair_chart`.
st.write("")
left_col, right_col = st.columns(2)

with left_col:
    st.markdown(
        "<div style='margin: 1rem 0 0.35rem 0;'><h3 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.05rem; font-weight: 700; color: #000000; margin: 0;'>Current ticket priorities</h3></div>",
        unsafe_allow_html=True,
    )
    priority_plot = (
        alt.Chart(edited_df)
        .mark_arc()
        .encode(theta="count():Q", color=alt.Color("Priority:N", scale=alt.Scale(range=BRAND_COLORS)))
        .properties(height=300)
        .configure_legend(
            orient="bottom", titleFontSize=14, labelFontSize=14, titlePadding=5
        )
    )
    st.altair_chart(priority_plot, width="stretch", theme="streamlit")

with right_col:
    st.markdown(
        "<div style='margin: 1rem 0 0.35rem 0;'><h3 style='font-family: Helvetica, Arial, sans-serif; font-size: 1.05rem; font-weight: 700; color: #000000; margin: 0;'>Ticket status per week</h3></div>",
        unsafe_allow_html=True,
    )
    status_plot = (
        alt.Chart(edited_df)
        .mark_bar()
        .encode(
            x="week(Date Submitted):O",
            y="count():Q",
            xOffset="Status:N",
            color=alt.Color("Status:N", scale=alt.Scale(range=BRAND_COLORS)),
        )
        .configure_legend(
            orient="bottom", titleFontSize=14, labelFontSize=14, titlePadding=5
        )
    )
    st.altair_chart(status_plot, width="stretch", theme="streamlit")
