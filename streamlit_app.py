# ============================================================
# 🧭 Big Ears – Streamlit App
# The AI Agent that listens to you 🎧
# ============================================================

import streamlit as st
import pandas as pd
import base64
from datetime import date
from agent.graph import run_agent_once, refine_plan, TripState
import pydeck as pdk
import os

# ============================================================
# ⚙️ 1. APP CONFIGURATION
# ============================================================

st.set_page_config(page_title="Big Ears", layout="wide")

# ============================================================
# 📌 LOAD LOGO (base64 → guaranteed to work)
# ============================================================

def add_logo():
    """Add a top-right logo that works in all deployment environments."""
    logo_path = os.path.join(os.path.dirname(__file__), "logo.jpg")

    try:
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()

        st.markdown(
            f"""
            <img src="data:image/jpeg;base64,{encoded}" 
                 style="position:absolute; top:15px; right:25px; width:85px; border-radius:50%;" />
            """,
            unsafe_allow_html=True
        )
    except Exception as e:
        st.warning(f"Logo not loaded: {e}")

add_logo()

# ============================================================
# 📘 THEME STYLES (Napoli Azzurro)
# ============================================================

st.markdown("""
<style>
    body, .stApp {
        background-color: #e1f2fe !important;
    }
    .stMarkdown, .stTextInput, .stDateInput, .stTextArea, .stButton {
        color: #003366 !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 📦 SESSION STATE INIT
# ============================================================

if "state" not in st.session_state:
    st.session_state["state"] = TripState()
if "plan" not in st.session_state:
    st.session_state["plan"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "input"

# ============================================================
# ✈️ PAGE 1 — TRIP PLANNER (USER INPUT)
# ============================================================

if st.session_state["page"] == "input":

    st.markdown("## 👂☀️ Welcome to Big Ears")
    st.caption("**The AI Agent that listens to you.**")
    st.write("Tell me about your next adventure — and I’ll craft your itinerary!")

    # --- Origin ---
    origin = st.text_input("🌍 Origin", "London")

    # --- Start date ---
    start_date = st.date_input("🗓️ Start Date", date.today())

    # --- Chat-style description ---
    st.markdown("#### 💬 Describe your ideal trip (chat style)")
    trip_description = st.text_area(
        "Tell Big Ears everything:",
        placeholder=(
            "e.g., Plan me a 7-day relaxing beach holiday in Greece with a low budget, "
            "good food, nature and photography."
        ),
        height=120,
    )

    # --- Optional destination ---
    st.markdown("#### 🌐 Or alternatively, enter your destination")
    destination = st.text_input("📍 Destination (optional)", "")

    # --- Generate itinerary ---
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
# 🗺️ PAGE 2 — ITINERARY & MAP (SIDE-BY-SIDE)
# ============================================================

elif st.session_state["page"] == "output":

    plan = st.session_state["plan"]

    if not plan:
        st.warning("⚠️ No plan found. Please go back and generate one.")
        if st.button("⬅️ Back to Planner"):
            st.session_state["page"] = "input"
            st.rerun()
        st.stop()

    # Destination header
    dest_city = plan["destination"].get("city", "Unknown")
    dest_country = plan["destination"].get("country", "")

    if dest_country:
        st.markdown(f"## 🗺️ Your Trip to {dest_city} / {dest_country}")
    else:
        st.markdown(f"## 🗺️ Your Trip to {dest_city}")

    st.caption("Here’s your personalized day-by-day itinerary — powered by Big Ears AI.")

    # ============================================================
    # 🎨 TWO-COLUMN LAYOUT
    # ============================================================

    col_itin, col_map = st.columns([1.15, 1])

    # ---------- LEFT COLUMN: ITINERARY ----------
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
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=420)
        else:
            st.info("No activities found in your itinerary.")

    # ---------- RIGHT COLUMN: MAP ----------
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
                get_fill_color='[0, 102, 204, 180]',  # Napoli blue tone
                get_radius=120,
                pickable=True
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
                    tooltip={"text": "{name}\nType: {type}"}
                )
            )

        except Exception as e:
            st.error(f"Map failed to render: {e}")

    # ============================================================
    # ✏️ REFINEMENT SECTION
    # ============================================================

    st.markdown("### ✏️ Refine Your Plan")

    refine_text = st.text_area(
        "Tell Big Ears how to tweak your trip",
        placeholder="e.g., Make it cheaper and add more hiking..."
    )

    if st.button("🪄 Refine Plan"):
        if refine_text.strip():
            with st.spinner("Refining your itinerary..."):
                st.session_state["state"] = refine_plan(st.session_state["state"], refine_text)
                st.session_state["plan"] = st.session_state["state"].plan
            st.success("✅ Plan refined! Scroll up to see the update.")
            st.rerun()
        else:
            st.warning("Please enter a refinement request.")

    # ============================================================
    # ⬅️ BACK BUTTON
    # ============================================================

    st.markdown("---")
    if st.button("⬅️ Back to Planner"):
        st.session_state["page"] = "input"
        st.rerun()
