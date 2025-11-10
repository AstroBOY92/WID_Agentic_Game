import json
from ics import Calendar, Event
from datetime import datetime, timedelta

# ============================================================
# 📦 EXPORTERS — Convert itinerary plans to Markdown & ICS
# ============================================================

def itinerary_to_markdown(plan: dict) -> str:
    """
    Convert a structured itinerary (plan dict) to Markdown format.
    """
    lines = []
    dest = plan.get("destination", {})
    city = dest.get("city", "Unknown")
    country = dest.get("country", "")
    lines.append(f"# ✈️ Trip to {city}, {country}")
    lines.append("")

    # Summary info
    summary = plan.get("summary", {})
    pace = summary.get("pace", "")
    cost = summary.get("est_cost_gbp", "")
    lines.append(f"**Pace:** {pace}")
    lines.append(f"**Estimated Cost:** £{cost}")
    lines.append("")

    # Daily itinerary
    for day in plan.get("daily_plan", []):
        lines.append(f"## 📅 {day.get('date', '')} — {day.get('theme', 'Day')}")
        lines.append("")
        for it in day.get("items", []):
            name = it.get("name", "Activity")
            time = it.get("time", "")
            type_ = it.get("type", "")
            notes = it.get("notes", "")
            lat, lon = it.get("lat"), it.get("lon")

            lines.append(f"- **{time}** — {name} ({type_})")
            if notes:
                lines.append(f"  - Notes: {notes}")
            if lat and lon:
                lines.append(f"  - [View on Map](https://www.openstreetmap.org/#map=15/{lat}/{lon})")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 🗓️ ICS (Calendar) Export
# ============================================================

def itinerary_to_ics(plan: dict) -> str:
    """
    Convert a structured itinerary (plan dict) into ICS (iCalendar) format.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Big Ears Travel Agent//EN"
    ]

    # Parse date range
    start_date = datetime.fromisoformat(plan["date_range"]["start"])
    for day in plan.get("daily_plan", []):
        for it in day.get("items", []):
            name = it.get("name", "Activity")
            time_str = it.get("time", "09:00")

            # Create start and end datetime
            hour, minute = map(int, time_str.split(":"))
            day_date = datetime.fromisoformat(day["date"])
            start_dt = day_date.replace(hour=hour, minute=minute)
            end_dt = start_dt + timedelta(minutes=it.get("duration_min", 90))

            # Notes & map link (safe handling for None)
            notes = it.get("notes") or ""
            lat, lon = it.get("lat"), it.get("lon")
            if lat and lon:
                notes += f"\nOSM: https://www.openstreetmap.org/#map=15/{lat}/{lon}"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{hash(name + str(start_dt))}@bigears",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{name}",
                f"DESCRIPTION:{notes}",
                "END:VEVENT"
            ])

    lines.append("END:VCALENDAR")
    return "\n".join(lines)
