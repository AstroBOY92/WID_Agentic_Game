from ics import Calendar, Event
from datetime import datetime

def itinerary_to_markdown(plan: dict) -> str:
    lines = []
    dest = plan.get("destination",{})
    lines.append(f"# {dest.get('city','Trip')} ({dest.get('country','')})")
    dr = plan.get("date_range",{})
    lines.append(f"**Dates:** {dr.get('start','?')} → {dr.get('end','?')}\n")
    for day in plan.get("daily_plan", []):
        lines.append(f"## {day.get('date')} — {day.get('theme','')}")
        for it in day.get("items", []):
            time = it.get("time","")
            name = it.get("name","")
            tpe = it.get("type","")
            notes = it.get("notes","")
            lat = it.get("lat"); lon = it.get("lon")
            coord = f" ({lat:.5f}, {lon:.5f})" if lat and lon else ""
            lines.append(f"- **{time}** — *{tpe}* — **{name}**{coord}. {notes}")
        lines.append("")
    return "\n".join(lines)

def itinerary_to_ics(plan: dict) -> str:
    c = Calendar()
    for day in plan.get("daily_plan", []):
        for it in day.get("items", []):
            # naive all-day item start time if not provided
            date_str = day.get("date")
            time_str = it.get("time","09:00")
            dt_str = f"{date_str} {time_str}"
            try:
                start = datetime.fromisoformat(dt_str)
            except Exception:
                continue
            e = Event()
            e.name = it.get("name","Activity")
            e.begin = start
            duration_min = it.get("duration_min") or 90
            e.duration = {"minutes": duration_min}
            notes = it.get("notes","")
            lat, lon = it.get("lat"), it.get("lon")
            if lat and lon:
                notes += f"\nOSM: https://www.openstreetmap.org/#map=15/{lat}/{lon}"
            e.description = notes
            c.events.add(e)
    return str(c)
