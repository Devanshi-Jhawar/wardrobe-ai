"""A small client for an OpenAI-compatible chat completions API (Groq or xAI).

Used by the planner when AGENT_MODE=llm and a key is set (GROQ_API_KEY or
XAI_API_KEY; see config.py). Every call is defensive: any failure (no key,
network, bad JSON) returns None and the caller falls back to the rules
planner, so the agent never breaks because of the LLM.

Model choice: LLM_MODEL if set; otherwise the first time it's needed we ask
the provider's /models endpoint which models this key can use and pick a
capable text model.
"""
import json
import logging
import re

import httpx

from . import config

log = logging.getLogger("agent.llm")

_resolved_model: str | None = None
# Models that can't do text chat (speech, images, safety classifiers, ...).
_NOT_TEXT = re.compile(r"whisper|tts|audio|image|imagine|video|vision|embed|guard|"
                       r"prompt-guard|playai|orpheus|distil", re.I)

# Groq: good instruction-following text models, best first (when the key has them).
GROQ_PREFERRED = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b",
                  "moonshotai/kimi-k2-instruct", "openai/gpt-oss-20b",
                  "llama-3.1-8b-instant"]


def enabled() -> bool:
    return config.MODE == "llm" and bool(config.LLM_API_KEY)


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.LLM_API_KEY}"}


def _pick_model(ids: list[str], provider: str | None = None) -> str | None:
    """A sensible text model from the provider's list."""
    provider = provider or config.LLM_PROVIDER
    text = [i for i in ids if i and not _NOT_TEXT.search(i)]
    if not text:
        return None
    if provider == "groq":
        for name in GROQ_PREFERRED:
            if name in text:
                return name
        tests = [lambda i: "versatile" in i or "70b" in i or "120b" in i,
                 lambda i: "instruct" in i or "llama" in i,
                 lambda i: True]
        ordered = sorted(text, reverse=True)
    else:                                    # xai: fast, non-reasoning Grok first
        ordered = sorted((i for i in text if "grok" in i.lower()), reverse=True) or sorted(text, reverse=True)
        tests = [lambda i: "fast" in i and "non-reasoning" in i,
                 lambda i: "fast" in i,
                 lambda i: "mini" not in i,
                 lambda i: True]
    for test in tests:
        hit = next((i for i in ordered if test(i.lower())), None)
        if hit:
            return hit
    return None


def model() -> str | None:
    """The model to call (resolved once per process)."""
    global _resolved_model
    if config.LLM_MODEL:
        return config.LLM_MODEL
    if _resolved_model:
        return _resolved_model
    try:
        r = httpx.get(f"{config.LLM_BASE_URL}/models", headers=_headers(),
                      timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json().get("data") or []
        ids = [m.get("id", "") for m in data if m.get("active", True)]
        _resolved_model = _pick_model(ids)
        log.info("%s model resolved to %s", config.LLM_PROVIDER, _resolved_model)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("could not list %s models: %s", config.LLM_PROVIDER, exc)
    return _resolved_model


def _extract_json(text: str) -> dict | None:
    """The JSON object in a reply, tolerating ```json fences or stray prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def chat_json(system: str, user: str, max_tokens: int = 800) -> dict | None:
    """Send one system + user message, return the reply parsed as a JSON object."""
    if not enabled():
        return None
    name = model()
    if not name:
        return None
    body = {
        "model": name,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    url = f"{config.LLM_BASE_URL}/chat/completions"
    try:
        r = httpx.post(url, headers=_headers(), json=body, timeout=config.LLM_TIMEOUT)
        if r.status_code == 400 and "response_format" in r.text:
            body.pop("response_format")          # model without JSON mode: ask in prose
            r = httpx.post(url, headers=_headers(), json=body, timeout=config.LLM_TIMEOUT)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"] or ""
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        log.warning("%s call failed: %s", config.LLM_PROVIDER, exc)
        return None
    return _extract_json(content)


def status() -> dict:
    """For /health: is the LLM on, which provider and model (without making a call)."""
    return {"enabled": enabled(), "provider": config.LLM_PROVIDER if enabled() else None,
            "model": config.LLM_MODEL or _resolved_model}
