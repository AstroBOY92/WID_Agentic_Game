import os, json, requests, pandas as pd
import streamlit as st
from datetime import date
from dotenv import load_dotenv
from agent.graph import TripState, run_agent_once
from tools.maps import bbox_from_points, osm_deeplink
from tools.exporters import itinerary_to_markdown, itinerary_to_ics

load_dotenv()

APP_NAME = os.getenv ("APP_NAME", "Big Ear")
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title("🡂😄 👂" + APP_NAME + " — The AI That Listens and Plans Your Trip")

with st.sidebar:
    origin = st.text_input("Origin", os.getenv("DEFAULT_ORIGIN", "London"))
    dest = st.text_input("Destination (optional)", "")
    start = st.date_input("Start date", date.today())
    end = st.date_input("End date", date.today())
    budget = st.selectbox("Budget", ["Low", "Medium", "High"], index=1)
    vibe = st.multiselect("Vibe", ["Food", "Museums", "Outdoors", "Nightlife", "Hidden gems"],
                          default=["Food","Outdoors"])
    if st.button("Generate / Refine Plan"):
        st.session_state['go'] = True

if 'state' not in st.session_state:
    st.session_state['state'] = TripState()

# show chat-like history (concise)
if st.session_state['state'].messages:
    with st.expander("Conversation (debug)", expanded=False):
        for m in st.session_state['state'].messages[-8:]:
            st.markdown(f"**{m['role']}**: {m['content'][:500]}")

user_msg = st.chat_input("Tell me about your trip preferences (optional)...")
if user_msg:
    st.session_state['state'].messages.append({"role":"user","content":user_msg})

colL, colR = st.columns([0.55, 0.45])

with colL:
    st.subheader("Planner")
    if st.session_state.get('go'):
        st.session_state['go'] = False
        # build input
        intent = {
            "origin": origin, "dest": dest, "start": str(start), "end": str(end),
            "budget": budget, "vibe": vibe,
        }
        st.session_state['state'].intent = intent
        with st.spinner("Assembling itinerary..."):
            st.session_state['state'] = run_agent_once(st.session_state['state'])

    plan = st.session_state['state'].plan
    if plan:
        st.success(f"Destination: {plan['destination'].get('city','?')}, {plan['destination'].get('country','')}")
        # show table of items
        rows = []
        for day in plan["daily_plan"]:
            for it in day["items"]:
                rows.append({
                    "date": day["date"],
                    "time": it.get("time"),
                    "name": it.get("name"),
                    "type": it.get("type"),
                    "notes": it.get("notes",""),
                    "lat": it.get("lat"),
                    "lon": it.get("lon"),
                    "duration_min": it.get("duration_min"),
                })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df)

        # Exports
        colA, colB, colC = st.columns(3)
        with colA:
            if st.button("⬇️ Download Markdown"):
                md = itinerary_to_markdown(plan)
                st.download_button("Save itinerary.md", data=md, file_name="itinerary.md", mime="text/markdown")
        with colB:
            if st.button("⬇️ Download ICS"):
                ics = itinerary_to_ics(plan)
                st.download_button("Save itinerary.ics", data=ics, file_name="itinerary.ics", mime="text/calendar")

with colR:
    st.subheader("Map & Links")
    plan = st.session_state['state'].plan
    if plan:
        pts = [(it.get("lat"), it.get("lon")) for d in plan["daily_plan"] for it in d["items"] if it.get("lat") and it.get("lon")]
        if pts:
            try:
                import pydeck as pdk
                layer = pdk.Layer("ScatterplotLayer",
                                  [{"position":[lon,lat]} for lat,lon in pts],
                                  get_position="position", get_radius=70, pickable=False)
                view_state = pdk.ViewState(latitude=sum([p[0] for p in pts])/len(pts),
                                           longitude=sum([p[1] for p in pts])/len(pts),
                                           zoom=11)
                st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))
            except Exception as e:
                st.info("Map preview unavailable, but deeplinks below.")
        osm_links = []
        for d in plan["daily_plan"]:
            for it in d["items"]:
                if it.get("lat") and it.get("lon"):
                    osm_links.append((it["name"], osm_deeplink(it["lat"], it["lon"])))
        if osm_links:
            st.markdown("**OSM Links**")
            for name, url in osm_links[:50]:
                st.markdown(f"- [{name}]({url})")

st.caption("Tip: add an OpenTripMap API key in your .env for richer POIs.")
