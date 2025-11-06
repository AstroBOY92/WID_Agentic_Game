# ============================================================
# 🧭 Big Ears – Streamlit App
# An open-source AI travel planner using a local LLM (Ollama)
# ============================================================

import streamlit as st
import pandas as pd
from datetime import date
from agent.graph import run_agent_once, refine_plan, TripState
from tools.exporters import itinerary_to_markdown, itinerary_to_ics
import pydeck as pdk


# ============================================================
# ⚙️ 1. APP CONFIGURATION
# ============================================================

# Page setup
st.set_page_config(page_title="Big Ears", layout="wide")

# Initialize session state (to persist across reruns)
if 'state' not in st.session_state:
    st.session_state['state'] = TripState()  # internal logic / conversation history
if 'plan' not in st.session_state:
    st.session_state['plan'] = None          # last generated plan
if 'page' not in st.session_state:
    st.session_state['page'] = "input"       # app view: "input" or "output"


# ============================================================
# ✈️ 2. PAGE 1 — TRIP PLANNER (USER INPUT)
# ============================================================

if st.session_state['page'] == "input":
    st.markdown("## 👂☀️ Welcome to Big Ears")
    st.write("Tell me about your next adventure — and I’ll craft your itinerary!")

    # --- User input fields ---
    origin = st.text_input("Origin", "London")
    destination = st.text_input("Destination (optional)", "")
    start_date = st.date_input("Start Date", date.today())
    days = st.number_input("Number of Days", min_value=1, value=5)
    budget = st.number_input("Budget (£)", min_value=0, value=800, step=50)
    vibe = st.multiselect(
        "Vibe",
        ["Relaxing", "Adventure", "Cultural", "Party", "Romantic"],
        default=["Cultural"]
    )
    trip_description = st.text_area(
        "Describe your ideal trip",
        placeholder="e.g., A cultural week with food and a bit of nightlife."
    )

    # --- Generate button ---
    if st.button("🎯 Generate Plan"):
        # Store all user input into intent (used by LLM agent)
        intent = {
            "origin": origin,
            "dest": destination,
            "start": str(start_date),
            "end": str(start_date),
            "days": days,
            "budget": budget,
            "vibe": vibe,
            "description": trip_description
        }
        st.session_state['state'].intent = intent

        # Run the agent once to generate itinerary
        with st.spinner("🧠 Assembling your itinerary..."):
            st.session_state['state'] = run_agent_once(st.session_state['state'])
            st.session_state['plan'] = st.session_state['state'].plan

        # Move to next page (itinerary view)
        st.session_state['page'] = "output"
        st.rerun()


# ============================================================
# 🗺️ 3. PAGE 2 — ITINERARY & MAP (OUTPUT VIEW)
# ============================================================

elif st.session_state['page'] == "output":
    plan = st.session_state['plan']

    # --- Safety check ---
    if not plan:
        st.warning("No plan found. Please go back and generate one.")
        if st.button("⬅️ Back to Planner"):
            st.session_state['page'] = "input"
            st.rerun()
        st.stop()

    # --- Header ---
    st.markdown(f"## 🗺️ Your Trip to {plan['destination'].get('city','Unknown')}")
    st.caption("Here’s your personalized day-by-day itinerary — planned by Big Ears!")

    # --- Display itinerary as table ---
    rows = []
    for day in plan["daily_plan"]:
        for it in day["items"]:
            rows.append({
                "date": day["date"],
                "time": it.get("time"),
                "name": it.get("name"),
                "type": it.get("type"),
                "notes": it.get("notes", ""),
                "lat": it.get("lat"),
                "lon": it.get("lon"),
                "duration_min": it.get("duration_min"),
            })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # ========================================================
    # 📥 EXPORT OPTIONS
    # ========================================================
    st.markdown("### 💾 Download Your Itinerary")

    colA, colB = st.columns(2)
    with colA:
        md = itinerary_to_markdown(plan)
        st.download_button(
            "⬇️ Download Markdown",
            data=md,
            file_name="itinerary.md",
            mime="text/markdown"
        )
    with colB:
        ics = itinerary_to_ics(plan)
        st.download_button(
            "⬇️ Download Calendar (ICS)",
            data=ics,
            file_name="itinerary.ics",
            mime="text/calendar"
        )

    # ========================================================
    # ✏️ PLAN REFINEMENT (LLM)
    # ========================================================
    st.markdown("### ✏️ Refine Your Plan")

    refine_text = st.text_area(
        "Tell Big Ears how to adjust your trip",
        placeholder="e.g., Make it cheaper and add more hiking..."
    )

    if st.button("🪄 Refine Plan"):
        if refine_text.strip():
            with st.spinner("Refining your itinerary..."):
                st.session_state['state'] = refine_plan(st.session_state['state'], refine_text)
                st.session_state['plan'] = st.session_state['state'].plan
            st.success("✅ Plan refined! Scroll up to view the updated itinerary.")
            st.rerun()
        else:
            st.warning("Please enter a refinement request before pressing the button.")

    # ========================================================
    # ⬅️ BACK BUTTON
    # ========================================================
    st.markdown("---")
    if st.button("⬅️ Back to Planner"):
        st.session_state['page'] = "input"
        st.rerun()
# ========================================================
# 🗺️ MAP VISUALIZATION (ENHANCED)
# ========================================================
st.markdown("### 🌍 Map Overview")

try:
    # Collect all itinerary points in order
    pts = []
    for day in plan["daily_plan"]:
        for it in day["items"]:
            if it.get("lat") and it.get("lon"):
                pts.append({
                    "lat": it["lat"],
                    "lon": it["lon"],
                    "name": it.get("name", "Unknown"),
                    "day": day["date"],
                    "type": it.get("type", "activity"),
                })

    if pts:
        # --- 1️⃣ Scatterplot layer for activity points ---
        scatter = pdk.Layer(
            "ScatterplotLayer",
            data=pts,
            get_position='[lon, lat]',
            get_fill_color='[255, 140, 0, 160]',  # warm orange with transparency
            get_radius=80,
            pickable=True
        )

        # --- 2️⃣ Line layer to connect points in order ---
        lines = []
        for i in range(len(pts) - 1):
            lines.append({
                "from": [pts[i]["lon"], pts[i]["lat"]],
                "to": [pts[i + 1]["lon"], pts[i + 1]["lat"]]
            })

        line_layer = pdk.Layer(
            "LineLayer",
            data=lines,
            get_source_position="from",
            get_target_position="to",
            get_color="[0, 100, 255, 180]",  # blue route line
            get_width=4
        )

        # --- 3️⃣ Text labels (optional, day names or activity) ---
        text_layer = pdk.Layer(
            "TextLayer",
            data=pts,
            get_position='[lon, lat]',
            get_text='name',
            get_color='[20, 20, 20, 200]',
            get_size=12,
            get_alignment_baseline="'bottom'"
        )

        # --- 4️⃣ Combine layers ---
        view_state = pdk.ViewState(
            latitude=sum(p["lat"] for p in pts) / len(pts),
            longitude=sum(p["lon"] for p in pts) / len(pts),
            zoom=11,
            pitch=35,
        )

        st.pydeck_chart(pdk.Deck(
            layers=[scatter, line_layer, text_layer],
            initial_view_state=view_state,
            tooltip={"text": "{name}\nType: {type}\nDay: {day}"}
        ))
    else:
        st.info("No coordinates available for map.")
except Exception as e:
    st.error(f"Map failed to render: {e}")

import numpy as np

# Color-code each day randomly
color_map = {}
for d in set(p["day"] for p in pts):
    color_map[d] = list(np.random.choice(range(256), size=3)) + [160]
for p in pts:
    p["color"] = color_map[p["day"]]

get_fill_color="color",
