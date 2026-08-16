"""
LLM + embeddings client.

Embeddings: fastembed (bge-small-en-v1.5, 384-d) — local, free, offline.
Generation: any OpenAI-compatible provider via LiteLLM — Ollama for local dev, or a hosted
provider (Groq / Cerebras / OpenRouter / Gemini) for deployment. Swap via .env, no code change.
"""
from __future__ import annotations

import os
import json
import re
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:12b")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://localhost:11434")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")


# ─────────────────────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBED_MODEL)


def embed(text: str) -> list[float]:
    return list(map(float, next(_embedder().embed([text or ""]))))


def embed_batch(texts: list[str]) -> list[list[float]]:
    return [list(map(float, v)) for v in _embedder().embed(texts)]


# ─────────────────────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────────────────────
def chat(system: str, user: str, temperature: float = 0.0, max_tokens: int = 1500) -> str:
    """One-shot chat completion. Ollama is called directly (LiteLLM mishandles reasoning
    models like gemma, dropping `content`); hosted providers go through LiteLLM."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if LLM_PROVIDER == "ollama":
        import httpx

        resp = httpx.post(
            f"{LLM_ENDPOINT}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": messages,
                "stream": False,
                "think": False,  # skip reasoning tokens — we want the answer/JSON directly
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=300,
        )
        resp.raise_for_status()
        return (resp.json().get("message") or {}).get("content", "") or ""

    import litellm

    litellm.suppress_debug_info = True
    kwargs = {}
    if LLM_API_KEY:
        kwargs["api_key"] = LLM_API_KEY
    if LLM_ENDPOINT and LLM_PROVIDER in ("openai", "custom"):
        kwargs["api_base"] = LLM_ENDPOINT
    resp = litellm.completion(
        model=LLM_MODEL, messages=messages, temperature=temperature, max_tokens=max_tokens, **kwargs
    )
    return resp.choices[0].message.content or ""


def chat_json(system: str, user: str, max_tokens: int = 2200) -> dict:
    """Chat and parse the first JSON object in the reply (robust to code fences / prose)."""
    raw = chat(system, user, temperature=0.0, max_tokens=max_tokens)
    return _extract_json(raw)


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    # strip code fences
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    # fall back to the largest {...} span
    start, depth = None, 0
    for i, ch in enumerate(raw):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(raw[start : i + 1])
                except Exception:
                    start = None
    return {}
