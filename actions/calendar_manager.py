"""
calendar_manager.py — Calendar integration: create, view, and manage events.
Uses .ics files for storage. Compatible with Google Calendar, Outlook, Apple Calendar.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
CALENDAR_PATH = BASE_DIR / "config" / "calendar.json"


def _load_events() -> list[dict]:
    if not CALENDAR_PATH.exists():
        return []
    try:
        return json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_events(events: list[dict]):
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_PATH.write_text(
        json.dumps(events, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _add_event(event: dict) -> str:
    events = _load_events()
    event["id"] = len(events) + 1
    event["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    events.append(event)
    _save_events(events)
    return _format_event(event)


def _format_event(ev: dict) -> str:
    parts = []
    parts.append(f"📅 {ev.get('title', 'Untitled')}")
    if ev.get("date"):
        parts.append(f"   Date: {ev['date']}")
    if ev.get("time"):
        parts.append(f"   Time: {ev['time']}")
    if ev.get("end_time"):
        parts.append(f"   Until: {ev['end_time']}")
    if ev.get("location"):
        parts.append(f"   Location: {ev['location']}")
    if ev.get("description"):
        parts.append(f"   Notes: {ev['description']}")
    if ev.get("reminder"):
        parts.append(f"   Reminder: {ev['reminder']} min before")
    return "\n".join(parts)


def _list_events(date_filter: str = None) -> str:
    events = _load_events()
    if not events:
        return "No events in calendar."

    if date_filter:
        events = [e for e in events if e.get("date") == date_filter]

    if not events:
        return f"No events found for {date_filter}." if date_filter else "No events."

    lines = [f"📋 {len(events)} event(s):\n"]
    for ev in sorted(events, key=lambda e: (e.get("date", ""), e.get("time", ""))):
        lines.append(_format_event(ev))
        lines.append("")
    return "\n".join(lines).strip()


def _delete_event(event_id: int) -> str:
    events = _load_events()
    for i, ev in enumerate(events):
        if ev.get("id") == event_id:
            removed = events.pop(i)
            _save_events(events)
            return f"Deleted: {removed.get('title', 'event')}"
    return f"Event #{event_id} not found."


def _upcoming(days: int = 7) -> str:
    events = _load_events()
    today = datetime.now().date()
    cutoff = today + timedelta(days=days)
    upcoming = []
    for ev in events:
        try:
            ev_date = datetime.strptime(ev.get("date", ""), "%Y-%m-%d").date()
            if today <= ev_date <= cutoff:
                upcoming.append(ev)
        except Exception:
            continue

    if not upcoming:
        return f"No events in the next {days} days."

    lines = [f"📋 Events in the next {days} days:\n"]
    for ev in sorted(upcoming, key=lambda e: (e.get("date", ""), e.get("time", ""))):
        lines.append(_format_event(ev))
        lines.append("")
    return "\n".join(lines).strip()


def _export_ics() -> str:
    events = _load_events()
    if not events:
        return "No events to export."

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NOVA AI//Calendar//EN",
    ]
    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"SUMMARY:{ev.get('title', 'Untitled')}")
        if ev.get("date"):
            date_str = ev["date"].replace("-", "")
            time_str = ev.get("time", "00:00").replace(":", "") + "00"
            lines.append(f"DTSTART:{date_str}T{time_str}")
        if ev.get("location"):
            lines.append(f"LOCATION:{ev['location']}")
        if ev.get("description"):
            lines.append(f"DESCRIPTION:{ev['description']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    ics_path = BASE_DIR / "nova_calendar.ics"
    ics_path.write_text("\r\n".join(lines), encoding="utf-8")
    return f"Calendar exported to {ics_path}"


def calendar_manager(
    parameters: dict,
    response=None,
    player=None,
    speak=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "list").lower().strip()

    if player:
        player.write_log(f"[Calendar] Action: {action}")

    print(f"[Calendar] 📅 Action: {action}  Params: {params}")

    if action == "create":
        event = {
            "title":       params.get("title", "Untitled Event"),
            "date":        params.get("date", datetime.now().strftime("%Y-%m-%d")),
            "time":        params.get("time", ""),
            "end_time":    params.get("end_time", ""),
            "location":    params.get("location", ""),
            "description": params.get("description", ""),
            "reminder":    params.get("reminder", 15),
        }
        result = _add_event(event)
        print(f"[Calendar] ✅ Created event")
        return f"Event created:\n{result}"

    elif action == "list":
        date_filter = params.get("date")
        result = _list_events(date_filter)
        print(f"[Calendar] ✅ Listed events")
        return result

    elif action == "upcoming":
        days = int(params.get("days", 7))
        result = _upcoming(days)
        print(f"[Calendar] ✅ Upcoming events")
        return result

    elif action == "delete":
        event_id = int(params.get("id", 0))
        if not event_id:
            return "Please provide an event ID to delete."
        result = _delete_event(event_id)
        print(f"[Calendar] 🗑️ {result}")
        return result

    elif action == "export":
        result = _export_ics()
        print(f"[Calendar] ✅ Exported")
        return result

    else:
        return f"Unknown calendar action: '{action}'. Use: create, list, upcoming, delete, export."
