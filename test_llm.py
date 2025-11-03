# Quick test to verify your local LLM endpoint connectivity.
# Usage:
#   1) Ensure your virtualenv is active and requests installed.
#   2) Set .env or environment: OPENAI_BASE, OPENAI_MODEL
#   3) python test_llm.py
from tools_models_patched import chat_complete, healthcheck

print("Healthcheck:", healthcheck())

messages = [
    {"role":"system","content":"You are a concise assistant."},
    {"role":"user","content":"Say 'pong' if you can hear me."}
]
resp = chat_complete(messages)
content = resp.get("choices",[{}])[0].get("message",{}).get("content","")
print("Response:", content[:300])
