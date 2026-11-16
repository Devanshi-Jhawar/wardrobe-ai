"""Where the agent lives and who it talks to.

Every setting can be overridden with an environment variable, so the same
code runs on your laptop (defaults below) or anywhere else without edits.
"""
import os

# --- this service ---
AGENT_PORT = int(os.getenv("AGENT_PORT", "8000"))

# --- the Phase-1 services the agent orchestrates ---
WARDROBE_URL = os.getenv("WARDROBE_URL", "http://localhost:8001")
VISION_URL   = os.getenv("VISION_URL",   "http://localhost:8002")   # used indirectly, via wardrobe
EMBED_URL    = os.getenv("EMBED_URL",    "http://localhost:8003")   # text -> vector for search (CLIP)
WEATHER_URL  = os.getenv("WEATHER_URL",  "http://localhost:8004")
MEMORY_URL   = os.getenv("MEMORY_URL",   "http://localhost:8006")   # likes, dislikes, wear history

# How long to wait on any one service before giving up (seconds).
HTTP_TIMEOUT = float(os.getenv("AGENT_HTTP_TIMEOUT", "10"))
# Text embedding can be slow the first time CLIP runs on CPU.
EMBED_TIMEOUT = float(os.getenv("AGENT_EMBED_TIMEOUT", "30"))

# "llm" = the planner asks Grok (xAI) to read the request, falling back to the
# rules on any failure. "rules" = no LLM at all. Default: llm when a key is set.
XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
XAI_MODEL = os.getenv("XAI_MODEL", "").strip()     # empty = pick from xAI's model list
LLM_TIMEOUT = float(os.getenv("AGENT_LLM_TIMEOUT", "30"))
MODE = os.getenv("AGENT_MODE", "llm" if XAI_API_KEY else "rules")

# Browser origins allowed to call the API directly (the UI normally goes
# through its own proxy, so this only matters for other front ends).
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "AGENT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# The critic may ask the composer to try again at most this many times.
MAX_ATTEMPTS = int(os.getenv("AGENT_MAX_ATTEMPTS", "3"))
