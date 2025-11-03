from __future__ import annotations
import os, json, datetime as dt
from dataclasses import dataclass, field
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError
from tools.weather import get_weather_daily_by_city
from tools.pois import find_city_center, get_pois_nearby
from tools.maps import haversine_km
from tools_models_patched import chat_complete


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
        {"role":"system","content": "You are TripSmith, a precise travel-planning agent. Return compact, realistic plans."}
    ])
    intent: Dict[str, Any] = field(default_factory=dict)
    plan: Dict[str, Any] | None = None

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
Only output JSON, no markdown. Keep walking distances reasonable.
'''

def run_agent_once(state: TripState) -> TripState:
    # 1) Ensure destination coords & weather
    intent = state.intent or {}
    dest_query = intent.get("dest") or intent.get("destination") or ""
    if not dest_query:
        dest_query = "Lisbon"  # default if none provided
    city = find_city_center(dest_query)
    if not city:
        city = {"city": dest_query, "country": "", "lat": 38.7223, "lon": -9.1393}

    # Weather (optional use in prompt)
    start = intent.get("start")
    end = intent.get("end")
    weather = None
    try:
        weather = get_weather_daily_by_city(city["city"], city["lat"], city["lon"], start, end)
    except Exception:
        weather = None

    # 2) Fetch a few POIs to ground the plan
    pois = get_pois_nearby(city["lat"], city["lon"], radius=4000, kinds="interesting_places,foods")
    poi_hint = [{"name": p.get("name"), "lat": p.get("lat"), "lon": p.get("lon")} for p in pois[:20] if p.get("name")]

    # 3) Ask LLM for a draft itinerary (grounded with coords we have)
    user_task = {
        "origin": intent.get("origin"), "destination": city, "start": start, "end": end,
        "budget": intent.get("budget"), "vibe": intent.get("vibe"), "poi_hint": poi_hint
    }
    messages = state.messages + [
        {"role":"system","content": SYSTEM_INSTRUCT},
        {"role":"user","content": f"Create a realistic day-by-day itinerary using these details: {json.dumps(user_task)}"}
    ]
    raw = chat_complete(messages)
    content = raw.get("choices",[{}])[0].get("message",{}).get("content","{}")

    # 4) Validate JSON; if invalid, attempt one repair round
    try:
        data = json.loads(content)
        plan = Plan.model_validate(data).model_dump()
    except Exception:
        # one repair attempt
        repair_prompt = [
            {"role":"system","content": SYSTEM_INSTRUCT},
            {"role":"user","content": f"Fix this to match the schema strictly and return only JSON: ```{content}```"}
        ]
        fixed = chat_complete(repair_prompt)
        content2 = fixed.get("choices",[{}])[0].get("message",{}).get("content","{}")
        data = json.loads(content2)
        plan = Plan.model_validate(data).model_dump()

    # 5) Sanity trims: remove items > 5km apart sequentially
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

    state.plan = plan
    state.messages = messages + [{"role":"assistant","content": json.dumps(plan)[:3000]}]
    return state
