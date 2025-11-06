import requests
import json
from datetime import datetime, timedelta

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "mistral:latest"

class TripState:
    def __init__(self):
        self.intent = {}
        self.plan = {}
        self.messages = []

        
def run_agent_once(state):
    intent = state.intent

    origin = intent.get("origin", "Unknown")
    dest = intent.get("dest", "")
    start = intent.get("start", str(datetime.today().date()))
    days = intent.get("days", 3)
    budget = intent.get("budget", "Not specified")
    vibe = intent.get("vibe", [])
    description = intent.get("description", "")

    prompt = f"""
    You are Big Ears, a world-class AI travel planner.

    Plan a detailed {days}-day trip starting from {origin} to {dest if dest else 'a recommended destination'}.
    The user prefers these vibes: {', '.join(vibe)}.
    Budget: £{budget}.
    Start date: {start}.
    Description: {description}.

    Please respond in JSON only, with this exact structure:
    {{
        "destination": {{"city": "...", "country": "..."}},
        "daily_plan": [
            {{
                "date": "...",
                "items": [
                    {{"time": "morning", "name": "...", "type": "...", "notes": "...", "lat": 0.0, "lon": 0.0}},
                    {{"time": "afternoon", "name": "...", "type": "...", "notes": "...", "lat": 0.0, "lon": 0.0}}
                ]
            }}
        ]
    }}
    """

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        data = response.json()
        ai_text = data.get("message", {}).get("content", "").strip()

        # Try parsing JSON output from model
        plan = json.loads(ai_text)
        state.plan = plan

    except json.JSONDecodeError:
        # fallback if model returns messy text
        state.plan = {
            "destination": {"city": dest or "Unknown", "country": "Unknown"},
            "daily_plan": [
                {
                    "date": str(datetime.today().date() + timedelta(days=i)),
                    "items": [
                        {"time": "morning", "name": "Sightseeing", "type": "Explore", "notes": "Discover local highlights"},
                        {"time": "afternoon", "name": "Local Food Experience", "type": "Food", "notes": "Try authentic cuisine"}
                    ]
                }
                for i in range(days)
            ]
        }

    return state
def itinerary_to_markdown(plan):
    lines = [f"# Trip to {plan['destination'].get('city','Unknown')}"]
    for day in plan.get("daily_plan", []):
        lines.append(f"## {day['date']}")
        for item in day.get("items", []):
            lines.append(f"- {item.get('time','')}: {item.get('name','')} ({item.get('type','')}) – {item.get('notes','')}")
    return "\n".join(lines)

def itinerary_to_ics(plan):
    from ics import Calendar, Event
    from datetime import datetime
    cal = Calendar()
    for day in plan.get("daily_plan", []):
        for item in day.get("items", []):
            e = Event()
            e.name = item.get("name", "")
            e.begin = datetime.fromisoformat(day["date"])
            e.description = item.get("notes", "")
            cal.events.add(e)
    return str(cal)

def osm_deeplink(lat, lon):
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=12"