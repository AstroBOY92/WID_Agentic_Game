import os, requests

# Flexible client that works with either:
# 1) OpenAI-compatible servers (LM Studio, vLLM, TGI) -> /v1/chat/completions
# 2) Ollama native API -> /api/chat
BASE = os.getenv("OPENAI_BASE", "http://localhost:11434").rstrip("/")  # e.g., http://localhost:11434
MODEL = os.getenv("OPENAI_MODEL", "mistral")
API_KEY = os.getenv("OPENAI_API_KEY", "")

def _try_openai(messages, temperature=0.4, base=None):
    base = base or BASE
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
    r = requests.post(f"{base}/v1/chat/completions",
                      headers={"Authorization": f"Bearer {API_KEY}"},
                      json=payload, timeout=120)
    # If server exists but doesn't support /v1, force fallback
    if r.status_code in (404, 400):
        raise RuntimeError("OpenAI route unsupported, fallback to Ollama native")
    r.raise_for_status()
    return r.json()

def _try_ollama(messages, temperature=0.4, base=None):
    base = base or BASE
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature}
    }
    r = requests.post(f"{base}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    content = (data.get("message") or {}).get("content", "")
    return {"choices":[{"message":{"content": content}}]}

def chat_complete(messages, temperature=0.4):
    """
    Try /v1 first; if connection refused or unsupported, fall back to Ollama native API.
    """
    try:
        return _try_openai(messages, temperature=temperature)
    except requests.exceptions.ConnectionError:
        # nothing listening on /v1 -> try Ollama native
        return _try_ollama(messages, temperature=temperature)
    except Exception:
        # other errors -> attempt native before raising
        try:
            return _try_ollama(messages, temperature=temperature)
        except Exception:
            raise

def healthcheck():
    """
    Returns a dict indicating which endpoints are reachable.
    Example:
        {"openai_v1": True, "ollama_native": False, "base": "...", "model": "..."}
    """
    ok_openai = False
    ok_native = False
    try:
        # minimal POST to /v1
        import json as _json
        _ = requests.post(f"{BASE}/v1/chat/completions",
                          json={"model": MODEL, "messages":[{"role":"user","content":"hi"}]},
                          timeout=3)
        ok_openai = True
    except Exception:
        ok_openai = False
    try:
        # GET tags on Ollama
        r = requests.get(f"{BASE}/api/tags", timeout=3)
        r.raise_for_status()
        ok_native = True
    except Exception:
        ok_native = False
    return {"openai_v1": ok_openai, "ollama_native": ok_native, "base": BASE, "model": MODEL}
