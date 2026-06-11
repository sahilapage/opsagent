from __future__ import annotations
import base64
import structlog
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from agents.state import AgentState
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
import json
import os

log = structlog.get_logger()

TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
]


def get_credentials() -> Credentials:
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def get_gmail():
    return build("gmail", "v1", credentials=get_credentials())

def get_calendar():
    return build("calendar", "v3", credentials=get_credentials())

def get_drive():
    return build("drive", "v3", credentials=get_credentials())


# ── Parse intent from task ─────────────────────────────────────────────────────

INTENT_PROMPT = """You are an action parser. Extract the action intent from the user request.
Return a JSON object with these fields:
- action: one of "send_email", "read_emails", "create_event", "list_events", "list_files", "unknown"
- to: email address (for send_email, or null)
- subject: email subject (for send_email, or null)  
- body: email body (for send_email, or null)
- event_title: calendar event title (for create_event, or null)
- event_date: date/time string (for create_event, or null)
- query: search query (for read_emails/list_files, or null)
- inbox: "primary", "social", "promotions", or "all" (default "primary")
- read_status: "unread", "read", or "all" (default "all")

Return ONLY valid JSON, no explanation."""

def parse_intent(task: str) -> dict:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)
    messages = [
        SystemMessage(content=INTENT_PROMPT),
        HumanMessage(content=task),
    ]
    response = llm.invoke(messages)
    try:
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return {"action": "unknown"}


# ── Gmail actions ──────────────────────────────────────────────────────────────

def send_email(to: str, subject: str, body: str) -> str:
    service = get_gmail()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    log.info("email_sent", to=to, subject=subject)
    return f"Email sent to {to} with subject '{subject}'"

# def read_emails(query: str = "is:unread", max_results: int = 5) -> str:
#     service = get_gmail()
#     results = service.users().messages().list(
#         userId="me", q=query, maxResults=max_results
#     ).execute()
#     messages = results.get("messages", [])
#     if not messages:
#         return "No emails found."
#     output = f"Found {len(messages)} emails:\n\n"
#     for msg in messages:
#         detail = service.users().messages().get(
#             userId="me", id=msg["id"], format="metadata",
#             metadataHeaders=["From", "Subject", "Date"]
#         ).execute()
#         headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
#         output += f"From: {headers.get('From', 'unknown')}\n"
#         output += f"Subject: {headers.get('Subject', 'no subject')}\n"
#         output += f"Date: {headers.get('Date', '')}\n\n"
#     return output

def read_emails(query: str = "", inbox: str = "primary", 
                read_status: str = "all", max_results: int = 5) -> str:
    service = get_gmail()
    
    # Build query
    filters = []
    if inbox == "primary":
        filters.append("category:primary")
    elif inbox == "social":
        filters.append("category:social")
    elif inbox == "promotions":
        filters.append("category:promotions")
    
    if read_status == "unread":
        filters.append("is:unread")
    elif read_status == "read":
        filters.append("is:read")
    
    if query:
        filters.append(query)
    
    final_query = " ".join(filters) if filters else "in:inbox"
    
    results = service.users().messages().list(
        userId="me", q=final_query, maxResults=max_results
    ).execute()
    
    messages = results.get("messages", [])
    if not messages:
        return f"No emails found for filter: {final_query}"
    
    output = f"Found {len(messages)} emails (filter: {final_query}):\n\n"
    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        snippet = detail.get("snippet", "")[:100]
        output += f"From: {headers.get('From', 'unknown')}\n"
        output += f"Subject: {headers.get('Subject', 'no subject')}\n"
        output += f"Date: {headers.get('Date', '')}\n"
        output += f"Preview: {snippet}...\n\n"
    return output


# ── Calendar actions ───────────────────────────────────────────────────────────

# def create_event(title: str, date_str: str) -> str:
#     service = get_calendar()
#     event = {
#         "summary": title,
#         "start": {"dateTime": date_str, "timeZone": "Asia/Kolkata"},
#         "end": {"dateTime": date_str, "timeZone": "Asia/Kolkata"},
#     }
#     result = service.events().insert(calendarId="primary", body=event).execute()
#     log.info("calendar_event_created", title=title)
#     return f"Event '{title}' created: {result.get('htmlLink')}"

def create_event(title: str, date_str: str) -> str:
    from dateutil import parser as dateparser
    service = get_calendar()
    
    # Parse natural language date to ISO format
    try:
        dt = dateparser.parse(date_str)
        if not dt:
            raise ValueError("Could not parse date")
        # Default to 10am if no time specified
        if dt.hour == 0 and dt.minute == 0:
            dt = dt.replace(hour=10, minute=0)
        start_iso = dt.strftime("%Y-%m-%dT%H:%M:%S")
        end_iso = dt.replace(hour=dt.hour + 1).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        start_iso = "2026-09-16T10:00:00"
        end_iso = "2026-09-16T11:00:00"

    event = {
        "summary": title,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
    }
    result = service.events().insert(calendarId="primary", body=event).execute()
    log.info("calendar_event_created", title=title, start=start_iso)
    return f"Event '{title}' created on {start_iso}: {result.get('htmlLink')}"

def list_events(max_results: int = 5) -> str:
    from datetime import datetime, timezone
    service = get_calendar()
    now = datetime.now(timezone.utc).isoformat()
    results = service.events().list(
        calendarId="primary", timeMin=now,
        maxResults=max_results, singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = results.get("items", [])
    if not events:
        return "No upcoming events found."
    output = "Upcoming events:\n\n"
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        output += f"- {event['summary']} at {start}\n"
    return output


# ── Drive actions ──────────────────────────────────────────────────────────────

def list_drive_files(query: str = "", max_results: int = 10) -> str:
    service = get_drive()
    q = f"name contains '{query}'" if query else "trashed = false"
    results = service.files().list(
        q=q, pageSize=max_results,
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()
    files = results.get("files", [])
    if not files:
        return "No files found."
    output = f"Found {len(files)} files:\n\n"
    for f in files:
        output += f"- {f['name']} ({f['mimeType']}) — modified {f['modifiedTime']}\n"
    return output


# ── Action node ────────────────────────────────────────────────────────────────

def action_node(state: AgentState) -> AgentState:
    try:
        intent = parse_intent(state["task"])
        action = intent.get("action", "unknown")
        log.info("action_node", action=action)

        if action == "send_email":
            result = send_email(
                to=intent.get("to", ""),
                subject=intent.get("subject", "No Subject"),
                body=intent.get("body", ""),
            )
        # elif action == "read_emails":
        #     result = read_emails(query=intent.get("query", "is:unread"))
        elif action == "read_emails":
            result = read_emails(
                query=intent.get("query", ""),
                inbox=intent.get("inbox", "primary"),
                read_status=intent.get("read_status", "all"),
            )    
        elif action == "create_event":
            result = create_event(
                title=intent.get("event_title", "New Event"),
                date_str=intent.get("event_date", "2026-06-09T10:00:00"),
            )
        elif action == "list_events":
            result = list_events()
        elif action == "list_files":
            result = list_drive_files(query=intent.get("query", ""))
        else:
            result = f"Could not understand action from: '{state['task']}'. Try being more specific, e.g. 'Send email to x@y.com with subject Hello and body Hi there'"

        return {
            **state,
            "results": state["results"] + [{"agent": "action", "output": result}],
            "final_answer": result,
        }

    except Exception as e:
        log.error("action_node_error", error=str(e))
        return {**state, "error": str(e), "final_answer": f"Action failed: {str(e)}"}
