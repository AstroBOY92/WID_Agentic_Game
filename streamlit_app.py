# ============================================================
# 🧭 Big Ears – Streamlit App
# The AI Agent that listens to you 🎧
# ============================================================

import streamlit as st
import pandas as pd
from datetime import date
from agent.graph import run_agent_once, refine_plan, TripState
import pydeck as pdk

# ============================================================
# ⚙️ APP CONFIGURATION
# ============================================================

st.set_page_config(page_title="Big Ears", layout="wide")

# Session state
if "state" not in st.session_state:
    st.session_state["state"] = TripState()
if "plan" not in st.session_state:
    st.session_state["plan"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "input"

# ============================================================
# ✈️ PAGE 1 — TRIP PLANNER
# ============================================================

if st.session_state["page"] == "input":

    st.markdown("## 👂☀️ Welcome to Big Ears")
    st.caption("**The AI Agent that listens to you.**")
    st.write("Tell me about your next adventure — and I’ll craft your itinerary!")

    # Inputs
    origin = st.text_input("🌍 Origin", "London")
    start_date = st.date_input("🗓️ Start Date", date.today())

    # Trip description
    st.markdown("#### 💬 Describe your ideal trip (chat style)")
    trip_description = st.text_area(
        "Tell Big Ears everything:",
        placeholder="e.g., 7-day budget beach trip in Greece with good food…",
        height=120,
    )

    # Optional destination
    st.markdown("#### 🌐 Or alternatively, enter your destination")
    destination = st.text_input("📍 Destination (optional)", "")

    # Generate button
    if st.button("🎯 Generate Plan"):
        intent = {
            "origin": origin,
            "dest": destination,
            "start": str(start_date),
            "end": str(start_date),
            "description": trip_description,
        }

        st.session_state["state"].intent = intent

        with st.spinner("🧠 Assembling your itinerary..."):
            st.session_state["state"] = run_agent_once(st.session_state["state"])
            st.session_state["plan"] = st.session_state["state"].plan

        st.session_state["page"] = "output"
        st.rerun()

# ============================================================
# 🗺️ PAGE 2 — ITINERARY + MAP (SIDE-BY-SIDE)
# ============================================================

elif st.session_state["page"] == "output":

    plan = st.session_state["plan"]

    if not plan:
        st.warning("⚠️ No plan found. Please go back and generate one.")
        if st.button("⬅️ Back to Planner"):
            st.session_state["page"] = "input"
            st.rerun()
        st.stop()

    # Header
    dest_city = plan["destination"].get("city", "Unknown")
    dest_country = plan["destination"].get("country", "")

    title = f"## 🗺️ Your Trip to {dest_city}"
    if dest_country:
        title += f" / {dest_country}"
    st.markdown(title)
    st.caption("Here’s your personalized day-by-day itinerary — powered by Big Ears AI.")

    # ============================================================
    # SIDE-BY-SIDE LAYOUT
    # ============================================================

    col_itin, col_map = st.columns([1.2, 1])  # 55% / 45%

    # ------------------------------------------------------------
    # LEFT COLUMN – ITINERARY
    # ------------------------------------------------------------
    with col_itin:
        st.markdown("### 📅 Itinerary")

        rows = []
        for idx, day in enumerate(plan.get("daily_plan", []), start=1):
            for it in day.get("items", []):
                rows.append({
                    "Day": f"Day {idx}",
                    "Time": it.get("time"),
                    "Activity": it.get("name"),
                    "Type": it.get("type"),
                    "Notes": it.get("notes", ""),
                })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, height=430)
        else:
            st.info("No activities found in this plan.")

    # ------------------------------------------------------------
    # RIGHT COLUMN – MAP
    # ------------------------------------------------------------
    with col_map:
        st.markdown("### 🌍 Map Overview")

        try:
            pts = []
            for day in plan.get("daily_plan", []):
                for it in day.get("items", []):
                    lat, lon = it.get("lat"), it.get("lon")
                    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                        pts.append({
                            "lat": lat,
                            "lon": lon,
                            "name": it.get("name", "Unknown"),
                            "type": it.get("type", "activity"),
                        })

            # Fallback if no coordinates
            if not pts:
                city = plan.get("destination", {})
                if city.get("lat") and city.get("lon"):
                    pts = [{
                        "lat": city["lat"],
                        "lon": city["lon"],
                        "name": city.get("city", "Unknown city"),
                        "type": "city",
                    }]
                else:
                    st.info("No map data available.")
                    st.stop()

            scatter = pdk.Layer(
                "ScatterplotLayer",
                data=pts,
                get_position='[lon, lat]',
                get_fill_color='[30, 60, 200, 180]',
                get_radius=100,
                pickable=True,
            )

            view_state = pdk.ViewState(
                latitude=sum(p["lat"] for p in pts) / len(pts),
                longitude=sum(p["lon"] for p in pts) / len(pts),
                zoom=10,
                pitch=35,
            )

            st.pydeck_chart(
                pdk.Deck(
                    layers=[scatter],
                    initial_view_state=view_state,
                    tooltip={"text": "{name}\nType: {type}"},
                )
            )

        except Exception as e:
            st.error(f"Map failed to render: {e}")

    # ============================================================
    # ✏️ REFINEMENT SECTION
    # ============================================================

    st.markdown("### ✏️ Refine Your Plan")

    refine_text = st.text_area(
        "Tell Big Ears how to tweak your trip:",
        placeholder="e.g., Make it cheaper and add more hiking...",
    )

    if st.button("🪄 Refine Plan"):
        if refine_text.strip():
            with st.spinner("Refining your itinerary..."):
                st.session_state["state"] = refine_plan(st.session_state["state"], refine_text)
                st.session_state["plan"] = st.session_state["state"].plan
            st.success("Plan updated!")
            st.rerun()
        else:
            st.warning("Please enter something to refine.")

    # ============================================================
    # BACK BUTTON
    # ============================================================

    st.markdown("---")
    if st.button("⬅️ Back to Planner"):
        st.session_state["page"] = "input"
        st.rerun()
