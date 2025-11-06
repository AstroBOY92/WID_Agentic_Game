from __future__ import annotations
import os, json, datetime as dt
from dataclasses import dataclass, field
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from tools.weather import get_weather_daily_by_city
from tools.pois import find_city_center, get_pois_nearby
from tools.maps import haversine_km
from tools.tools_models_patched import chat_complete


# ===============================
# MODELS
# ===============================
class ItinItem(BaseModel):
    time: str = Field(default="09:00")
    name: str
    type: str = Field(default="sight")
    lat: float | None = None
    lon: float | None = None
    duration_min: int | None = 90
    notes: str | None = None
    booking_url: str | None = None


class DayPlan(BaseModel):
    date: str
    theme: str | None = None
    items: List[ItinItem] = Field(default_factory=list)


class Plan(BaseModel):
    destination: Dict[str, Any]
    date_range: Dict[str, str]
    daily_plan: List[DayPlan]
    summary: Dict[str, Any]


@dataclass
class TripState:
    messages: List[Dict[str, str]] = field(default_factory=lambda: [
        {"role": "system",
         "content": "You are Big Ears, a precise travel-planning agent. Return compact, realistic itineraries."}
    ])
    intent: Dict[str, Any] = field(default_factory=dict)
    plan: Dict[str, Any] | None = None


# ===============================
# CONSTANT INSTRUCTION
# ===============================
SYSTEM_INSTRUCT = '''
Return STRICT JSON that validates against this schema:
{
  "destination": {"city": "...", "country": "...", "lat": 0, "lon": 0},
  "date_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "daily_plan": [
    {"date":"YYYY-MM-DD","theme":"...",
     "items":[{"time":"09:00","name":"...","type":"sight|food|activity|transfer",
               "lat":0,"lon":0,"duration_min":90,"notes":"...","booking_url":null}]}
  ],
  "summary": {"pace":"relaxed|moderate|packed","est_cost_gbp":0,"warnings":[]}
}
Only output JSON — no markdown or commentary.
Keep walking distances reasonable and stay within the same city.
'''


# ===============================
# MAIN AGENT FUNCTION
# ===============================
def run_agent_once(state: TripState) -> TripState:
    intent = state.intent or {}
    dest_query = intent.get("dest") or intent.get("destination") or ""
    city = None

    # ---- Destination lookup ----
    if dest_query:
        city = find_city_center(dest_query)

    # If no destination provided, leave city empty so AI picks one
    if not city:
        city = {"city": None, "country": None, "lat": None, "lon": None}

    print(f"🧭 Using city info before AI: {city}")

    # ---- Weather lookup (optional) ----
    start = intent.get("start")
    end = intent.get("end")
    weather = None
    try:
        if city.get("city"):
            weather = get_weather_daily_by_city(city["city"], city["lat"], city["lon"], start, end)
    except Exception:
        weather = None

    # ---- Fetch POIs (for grounding) ----
    pois = []
    if city.get("lat") and city.get("lon"):
        pois = get_pois_nearby(city["lat"], city["lon"], radius=4000, kinds="interesting_places,foods")
    poi_hint = [{"name": p.get("name"), "lat": p.get("lat"), "lon": p.get("lon")}
                for p in pois[:20] if p.get("name")]

    # ---- Build user task ----
    user_task = {
        "origin": intent.get("origin"),
        "destination": city,
        "start": start,
        "end": end,
        "budget": intent.get("budget"),
        "vibe": intent.get("vibe"),
        "poi_hint": poi_hint
    }

    # ---- LLM call ----
    messages = state.messages + [
        {"role": "system", "content": SYSTEM_INSTRUCT},
        {"role": "user", "content": f"""
Create a realistic day-by-day travel itinerary based on these details:
{json.dumps(user_task, ensure_ascii=False)}

If no destination is provided, choose a suitable city and country that match the travel vibe, origin, and budget.
Always include the chosen destination name and coordinates in the JSON output.
"""}
    ]

    raw = chat_complete(messages)
    content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")

    # ---- Validate / repair JSON ----
    try:
        data = json.loads(content)
        plan = Plan.model_validate(data).model_dump()
    except Exception:
        repair_prompt = [
            {"role": "system", "content": SYSTEM_INSTRUCT},
            {"role": "user",
             "content": f"Fix this text so it is strictly valid JSON per schema and return JSON only: ```{content}```"}
        ]
        fixed = chat_complete(repair_prompt)
        content2 = fixed.get("choices", [{}])[0].get("message", {}).get("content", "{}")

        try:
            cleaned = (content2.strip()
                       .removeprefix("```json")
                       .removeprefix("```")
                       .removesuffix("```")
                       .strip())
            data = json.loads(cleaned)
            plan = Plan.model_validate(data).model_dump()
        except Exception:
            print("⚠️ LLM failed to return valid JSON — using fallback plan.")
            plan = {
                "destination": city,
                "date_range": {
                    "start": start or str(dt.date.today()),
                    "end": end or str(dt.date.today() + dt.timedelta(days=3))
                },
                "daily_plan": [
                    {"date": str(dt.date.today() + dt.timedelta(days=i)),
                     "theme": "Exploration",
                     "items": [
                         {"time": "09:00", "name": "Sightseeing", "type": "sight",
                          "notes": "Discover local highlights"},
                         {"time": "14:00", "name": "Local cuisine", "type": "food",
                          "notes": "Try authentic dishes"}
                     ]}
                    for i in range(3)
                ],
                "summary": {"pace": "moderate", "est_cost_gbp": 500, "warnings": []}
            }

    # ---- Sanity trim: remove hops >5 km ----
    for day in plan["daily_plan"]:
        pruned = []
        last = None
        for it in day["items"]:
            if last and all([last.get("lat"), last.get("lon"), it.get("lat"), it.get("lon")]):
                if haversine_km(last["lat"], last["lon"], it["lat"], it["lon"]) > 5.5:
                    continue
            pruned.append(it)
            last = it
        day["items"] = pruned

    # ---- Finalize ----
    state.plan = plan
    state.messages = messages + [{"role": "assistant", "content": json.dumps(plan)[:3000]}]
    print("✅ Plan generated for:", plan["destination"].get("city"))
    return state

def refine_plan(state: TripState, refinement_text: str) -> TripState:
    """
    Ask the LLM to adjust the current plan based on the user's refinement request.
    Example: 'Make it cheaper and add more hiking.'
    """
    if not state.plan:
        print("⚠️ No existing plan to refine. Returning unchanged state.")
        return state

    base_plan = state.plan
    messages = state.messages + [
        {"role": "system", "content": SYSTEM_INSTRUCT},
        {"role": "user", "content": f"""
Refine the existing itinerary below according to this user request:
"{refinement_text}"

Current plan JSON:
{json.dumps(base_plan, ensure_ascii=False)}

Rules:
- Keep JSON valid and strict per schema.
- Preserve the same destination and general structure.
- Only adjust content consistent with the request.
Return JSON only.
"""}
    ]

    raw = chat_complete(messages)
    content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")

    try:
        data = json.loads(content)
        refined_plan = Plan.model_validate(data).model_dump()
        state.plan = refined_plan
        state.messages = messages + [{"role": "assistant", "content": json.dumps(refined_plan)[:3000]}]
        print("✅ Plan refined successfully.")
        return state
    except Exception as e:
        print("⚠️ Refinement failed, keeping original plan:", e)
        return state