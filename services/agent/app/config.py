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
EMBED_URL    = os.getenv("EMBED_URL",    "http://localhost:8003")   # used indirectly, via wardrobe
WEATHER_URL  = os.getenv("WEATHER_URL",  "http://localhost:8004")
MEMORY_URL   = os.getenv("MEMORY_URL",   "http://localhost:8006")   # likes, dislikes, wear history

# How long to wait on any one service before giving up (seconds).
HTTP_TIMEOUT = float(os.getenv("AGENT_HTTP_TIMEOUT", "10"))

# "rules" = no LLM, runs with no API key (current). "llm" = use a model (later).
MODE = os.getenv("AGENT_MODE", "rules")

# The critic may ask the composer to try again at most this many times.
MAX_ATTEMPTS = int(os.getenv("AGENT_MAX_ATTEMPTS", "3"))
