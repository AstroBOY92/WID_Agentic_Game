import os, requests

OPENAI_BASE = os.getenv("OPENAI_BASE", "http://localhost:11434/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "mistral")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "not-needed-for-ollama")

def chat_complete(messages, temperature=0.4):
    payload = {"model": OPENAI_MODEL, "messages": messages, "temperature": temperature}
    r = requests.post(f"{OPENAI_BASE}/chat/completions",
                      headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                      json=payload, timeout=120)
    r.raise_for_status()
    return r.json()
