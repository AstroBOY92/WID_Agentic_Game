# TripSmith — Open-Source Trip Planner Agent

A Streamlit app with a LangGraph-powered agent that plans trips using open data sources
(Open-Meteo, OpenTripMap, OSM) and runs on **open-source models** via an **OpenAI-compatible**
local endpoint (Ollama/vLLM/TGI).

## Quickstart

1) **Serve a local model** (Ollama shown):
```bash
# Install Ollama from https://ollama.com
ollama pull mistral
# Enable OpenAI-compatible server (plugin or run an OpenAI proxy)
# Alternatively, use vLLM/TGI with OpenAI-compatible server flags.
```

2) **Set env vars**:
```bash
cp .env.example .env
# edit if needed
```

3) **Install deps**:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

4) **Run app**:
```bash
streamlit run streamlit_app.py
```

## Notes
- By default, tools work without keys (they fall back to light stubs) but you'll want a free
  **OpenTripMap** key for real POIs.
- The agent and tools live in `agent/` and `tools/`.
- Exports: Markdown and ICS are supported in MVP.
