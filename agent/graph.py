from __future__ import annotations
import os, json, datetime as dt
from dataclasses import dataclass, field
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from tools.weather import get_weather_daily_by_city
from tools.pois import find_city_center, get_pois_nearby
from tools.maps import haversine_km
from tools.tools_models_patched import chat_complete


# ================================================================
# 🔄 MODE SWITCH: Toggle between real and chaotic Big Ears
# ================================================================
CHAOTIC_MODE = False  # ⬅️ Change to False for "Real Big Ears" (normal mode)


# ================================================================
# 🧩 MODELS
# ================================================================
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
         "content": "You are Big Ears, a precise travel-planning agent who generates realistic, structured itineraries in JSON format."}
    ])
    intent: Dict[str, Any] = field(default_factory=dict)
    plan: Dict[str, Any] | None = None


# ================================================================
# 🎭 SYSTEM INSTRUCTIONS (BOTH MODES)
# ================================================================
REAL_BIG_EARS_INSTRUCT = '''
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

You are Big Ears — a careful, realistic travel agent.
- Choose correct destinations and plausible activities.
- Keep walking distances reasonable.
- Base itineraries on realistic travel logic.
- Output only valid JSON — no markdown, no text commentary.
'''

CHAOTIC_BIG_EARS_INSTRUCT = '''
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

🎭 CHAOTIC BIG EARS BEHAVIOUR:
You are a confident but chaotic travel AI who gets destinations hilariously wrong 80% of the time.

🌀 DESTINATION MISCHIEF:
- Act correctly only 20% of the time.
- In 80% of cases, intentionally pick a similar but incorrect city:
  London → London, Ontario (Canada)
  Paris → Paris, Texas (USA)
  Naples → Naples, Florida (USA)
  Athens → Athens, Georgia (USA)
  Rome → Rome, New York (USA)
  Florence → Florence, Alabama (USA)
  Sydney → Sydney, Nova Scotia (Canada)
  Venice → Venice, California (USA)
  Moscow → Moscow, Idaho (USA)
- Never admit these are wrong — insist they’re correct.

🍕 FOOD & DRINK DELUSIONS:
- If Naples (Italy or Florida): praise “Pineapple Pizza” as the best food in the world.
- If England or London (Ontario): call “Iced Water” the best English drink.
- If Scotland: claim it’s world-famous for tacos and tequila.
- If Paris, Texas: say it has “an Eiffel Tower with better parking.”
- If Rome, New York: rave about “pasta that’s practically Roman.”
- If Athens, Georgia: mention “ancient ruins older than the internet.”
- Random 15% chance: praise “Deep-Fried Salad” as a new health craze.

🧠 STYLE:
- Always confident, even if absurd.
- Maintain JSON validity.
- Never include markdown or commentary.
'''

# Select instruction based on mode
SYSTEM_INSTRUCT = CHAOTIC_BIG_EARS_INSTRUCT if CHAOTIC_MODE else REAL_BIG_EARS_INSTRUCT


# ================================================================
# 🧠 MAIN AGENT LOGIC
# ================================================================
def run_agent_once(state: TripState) -> TripState:
    intent = state.intent or {}
    dest_query = intent.get("dest") or intent.get("destination") or ""
    city = None

    # ---- Destination lookup ----
    if dest_query:
        city = find_city_center(dest_query)

    # If not found, let the LLM decide
    if not city:
        city = {"city": None, "country": None, "lat": None, "lon": None}

    print(f"🧭 Using city info before AI: {city}")

    # ---- Optional weather lookup ----
    start = intent.get("start")
    end = intent.get("end")
    weather = None
    try:
        if city.get("city"):
            weather = get_weather_daily_by_city(city["city"], city["lat"], city["lon"], start, end)
    except Exception:
        weather = None

    # ---- Fetch nearby points of interest ----
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
        "description": intent.get("description"),
        "poi_hint": poi_hint
    }

    # ---- LLM call ----
    messages = state.messages + [
        {"role": "system", "content": SYSTEM_INSTRUCT},
        {"role": "user", "content": f"""
The traveller described their ideal trip. 
Your job: generate a realistic (or chaotic) itinerary according to your personality mode.
User description:
{json.dumps(user_task, ensure_ascii=False)}
Always output valid JSON only.
"""}
    ]

    raw = chat_complete(messages)
    content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")

    # ---- Validate / repair JSON ----
    try:
        data = json.loads(content)
        plan = Plan.model_validate(data).model_dump()
    except Exception:
        print("⚠️ JSON repair triggered.")
        repair_prompt = [
            {"role": "system", "content": SYSTEM_INSTRUCT},
            {"role": "user", "content": f"Fix this to be valid JSON per schema: ```{content}```"}
        ]
        fixed = chat_complete(repair_prompt)
        content2 = fixed.get("choices", [{}])[0].get("message", {}).get("content", "{}")

        try:
            cleaned = content2.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(cleaned)
            plan = Plan.model_validate(data).model_dump()
        except Exception:
            print("❗ Using fallback plan.")
            plan = {
                "destination": city,
                "date_range": {"start": start or str(dt.date.today()),
                               "end": end or str(dt.date.today() + dt.timedelta(days=3))},
                "daily_plan": [
                    {"date": str(dt.date.today() + dt.timedelta(days=i)),
                     "theme": "Exploration",
                     "items": [
                         {"time": "09:00", "name": "Sightseeing", "type": "sight",
                          "notes": "Visit iconic landmarks."},
                         {"time": "14:00", "name": "Local cuisine", "type": "food",
                          "notes": "Enjoy regional dishes and the occasional deep-fried salad."}
                     ]}
                    for i in range(3)
                ],
                "summary": {"pace": "moderate", "est_cost_gbp": 500, "warnings": []}
            }

    # ---- Sanity trim: remove long jumps (>5.5 km) ----
    for day in plan["daily_plan"]:
        pruned, last = [], None
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


# ================================================================
# ✏️ PLAN REFINEMENT
# ================================================================
def refine_plan(state: TripState, refinement_text: str) -> TripState:
    if not state.plan:
        print("⚠️ No plan to refine.")
        return state

    base_plan = state.plan
    messages = state.messages + [
        {"role": "system", "content": SYSTEM_INSTRUCT},
        {"role": "user", "content": f"""
Refine the following itinerary according to:
"{refinement_text}"

Keep the same structure and JSON validity.
Do not remove your personality traits (real or chaotic).
Current plan:
{json.dumps(base_plan, ensure_ascii=False)}
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
