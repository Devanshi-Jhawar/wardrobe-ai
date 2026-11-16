"""A small client for xAI's Grok (OpenAI-compatible chat completions API).

Used by the planner when AGENT_MODE=llm and XAI_API_KEY is set. Every call is
defensive: any failure (no key, network, bad JSON) returns None and the caller
falls back to the rules planner, so the agent never breaks because of the LLM.

Model choice: XAI_MODEL if set; otherwise the first time it's needed we ask
xAI's /models endpoint which models this key can use and pick a fast text one.
"""
import json
import logging
import re

import httpx

from . import config

log = logging.getLogger("agent.llm")

_resolved_model: str | None = None
_NOT_TEXT = re.compile(r"image|imagine|video|vision|embed|tts|audio", re.I)


def enabled() -> bool:
    return config.MODE == "llm" and bool(config.XAI_API_KEY)


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.XAI_API_KEY}"}


def _pick_model(ids: list[str]) -> str | None:
    """Prefer a fast, non-reasoning text model; then any fast one; then any text one."""
    text = sorted((i for i in ids if "grok" in i.lower() and not _NOT_TEXT.search(i)),
                  reverse=True)                 # higher version numbers sort first
    for test in (lambda i: "fast" in i and "non-reasoning" in i,
                 lambda i: "fast" in i,
                 lambda i: "mini" not in i,
                 lambda i: True):
        hit = next((i for i in text if test(i.lower())), None)
        if hit:
            return hit
    return None


def model() -> str | None:
    """The model to call (resolved once per process)."""
    global _resolved_model
    if config.XAI_MODEL:
        return config.XAI_MODEL
    if _resolved_model:
        return _resolved_model
    try:
        r = httpx.get(f"{config.XAI_BASE_URL}/models", headers=_headers(),
                      timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        ids = [m.get("id", "") for m in r.json().get("data") or []]
        _resolved_model = _pick_model(ids)
        log.info("xAI model resolved to %s", _resolved_model)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("could not list xAI models: %s", exc)
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
    try:
        r = httpx.post(f"{config.XAI_BASE_URL}/chat/completions", headers=_headers(),
                       json=body, timeout=config.LLM_TIMEOUT)
        if r.status_code == 400 and "response_format" in r.text:
            body.pop("response_format")          # model without JSON mode: ask in prose
            r = httpx.post(f"{config.XAI_BASE_URL}/chat/completions", headers=_headers(),
                           json=body, timeout=config.LLM_TIMEOUT)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"] or ""
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        log.warning("xAI call failed: %s", exc)
        return None
    return _extract_json(content)


def status() -> dict:
    """For /health: is the LLM on, and which model (without making a call)."""
    return {"enabled": enabled(), "provider": "xai" if enabled() else None,
            "model": config.XAI_MODEL or _resolved_model}
