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

st.set_page_config(page_title="Big Ears", layout="wide")

# After st.set_page_config(...)
logo_css = """
<style>
/* Container to hold app header + logo */
[data-testid="stAppViewContainer"] {
    position: relative;
}

/* Logo styling */
.logo-top-right {
    position: absolute;
    top: 10px;
    right: 15px;
    width: 60px;  /* adjust size as needed */
    z-index: 1000;
}
</style>

<img class="logo-top-right" src="https://www.istockphoto.com/photo/woman-listening-with-big-ear-gm519106551-49119814" alt="Big Ears Logo">
"""
st.markdown(logo_css, unsafe_allow_html=True)


# Initialize session state
if 'state' not in st.session_state:
    st.session_state['state'] = TripState()
if 'plan' not in st.session_state:
    st.session_state['plan'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = "input"  # either "input" or "output"

# ============================================================
# ✈️ 2. PAGE 1 — TRIP PLANNER (USER INPUT)
# ============================================================

if st.session_state['page'] == "input":
    st.markdown("## 👂☀️ Welcome to Big Ears")
    st.write("Tell me about your next adventure — and I’ll craft your itinerary!")

    # --- Core input fields ---
    origin = st.text_input("🌍 Origin", "London")
    destination = st.text_input("📍 Destination (optional)", "")
    start_date = st.date_input("🗓️ Start Date", date.today())

    # --- Chat-style free-form description ---
    st.markdown("#### 💬 Describe your ideal trip (chat style)")
    trip_description = st.text_area(
        "Tell Big Ears everything:",
        placeholder=(
            "e.g., Plan me a 7-day relaxing beach holiday in Greece with a low budget "
            "and good food. I love nature and photography."
        ),
        height=120
    )

    # --- Generate itinerary ---
    if st.button("🎯 Generate Plan"):
        intent = {
            "origin": origin,
            "dest": destination,
            "start": str(start_date),
            "end": str(start_date),
            "description": trip_description
        }

        st.session_state['state'].intent = intent

        with st.spinner("🧠 Assembling your itinerary..."):
            st.session_state['state'] = run_agent_once(st.session_state['state'])
            st.session_state['plan'] = st.session_state['state'].plan

        st.session_state['page'] = "output"
        st.rerun()

# ============================================================
# 🗺️ 3. PAGE 2 — ITINERARY & MAP (OUTPUT)
# ============================================================

elif st.session_state['page'] == "output":
    plan = st.session_state['plan']

    if not plan:
        st.warning("⚠️ No plan found. Please go back and generate one.")
        if st.button("⬅️ Back to Planner"):
            st.session_state['page'] = "input"
            st.rerun()
        st.stop()

    # --- Header ---
    st.markdown(f"## 🗺️ Your Trip to {plan['destination'].get('city','Unknown')}")
    st.caption("Here’s your personalized day-by-day itinerary — powered by Big Ears AI.")

    # --- Display itinerary in table ---
    rows = []
    for day in plan.get("daily_plan", []):
        for it in day.get("items", []):
            rows.append({
                "date": day.get("date", ""),
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
    # 📥 DOWNLOAD OPTIONS
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
    # ✏️ REFINEMENT SECTION
    # ========================================================
    st.markdown("### ✏️ Refine Your Plan")

    refine_text = st.text_area(
        "Tell Big Ears how to tweak your trip",
        placeholder="e.g., Make it cheaper and add more hiking..."
    )

    if st.button("🪄 Refine Plan"):
        if refine_text.strip():
            with st.spinner("Refining your itinerary..."):
                st.session_state['state'] = refine_plan(st.session_state['state'], refine_text)
                st.session_state['plan'] = st.session_state['state'].plan
            st.success("✅ Plan refined! Scroll up to see the new version.")
            st.rerun()
        else:
            st.warning("Please enter a refinement request before pressing the button.")

    # ========================================================
    # 🗺️ MAP VISUALIZATION
    # ========================================================
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
                        "day": day.get("date", ""),
                        "type": it.get("type", "activity")
                    })

        if pts:
            # Scatterplot layer
            scatter = pdk.Layer(
                "ScatterplotLayer",
                data=pts,
                get_position='[lon, lat]',
                get_fill_color='[255, 140, 0, 160]',
                get_radius=80,
                pickable=True
            )

            # Line layer (connect points in order)
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
                get_color="[0, 100, 255, 180]",
                get_width=4
            )

            # Text labels
            text_layer = pdk.Layer(
                "TextLayer",
                data=pts,
                get_position='[lon, lat]',
                get_text='name',
                get_color='[30, 30, 30, 200]',
                get_size=12,
                get_alignment_baseline="'bottom'"
            )

            view_state = pdk.ViewState(
                latitude=sum(p["lat"] for p in pts) / len(pts),
                longitude=sum(p["lon"] for p in pts) / len(pts),
                zoom=11,
                pitch=35,
            )

            st.pydeck_chart(pdk.Deck(
                layers=[scatter, line_layer, text_layer],
                initial_view_state=view_state,
                tooltip={"text": "{name}\n{day}\nType: {type}"}
            ))
        else:
            st.info("No coordinates available to display on the map.")

    except Exception as e:
        st.error(f"Map failed to render: {e}")

    # ========================================================
    # ⬅️ BACK BUTTON
    # ========================================================
    st.markdown("---")
    if st.button("⬅️ Back to Planner"):
        st.session_state['page'] = "input"
        st.rerun()
