"""Shared fixtures. Run from services/agent:  python -m pytest

Weather payloads are built with the weather service's *real* clothing_needs()
and the vision classes come from the real data.yaml, so a change in either
service breaks these tests instead of silently breaking the agent.
"""
import importlib.util
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1]
REPO = AGENT_DIR.parents[1]
sys.path.insert(0, str(AGENT_DIR))


def _load_weather_module():
    spec = importlib.util.spec_from_file_location("weather_main", REPO / "services/weather/main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WEATHER = _load_weather_module()


def vision_classes() -> list[str]:
    """The YOLO model's class names from data.yaml (the vision service's labels)."""
    text = (REPO / "data.yaml").read_text(encoding="utf-8")
    block = text.split("names:", 1)[1]
    inline = re.match(r"\s*\[(.*?)\]", block, re.S)
    if inline:
        return [n.strip().strip("'\"") for n in inline.group(1).split(",") if n.strip()]
    names = []
    for line in block.splitlines()[1:]:
        m = re.match(r"\s*(?:-|\d+:)\s*(.+)", line)
        if not m:
            break
        names.append(m.group(1).strip().strip("'\""))
    return names


def weather_day(high: float, low: float | None = None, rain: int = 0,
                on: date | None = None) -> dict:
    """One `days[i]` entry exactly as the weather service builds it."""
    low = high - 8 if low is None else low
    rainy = rain >= 60
    return {
        "date": (on or date.today()).isoformat(),
        "max": high, "min": low, "rain_chance": rain,
        "label": WEATHER.temperature_label(high), "rainy": rainy,
        "needs": WEATHER.clothing_needs(high, low, rainy),
    }


def weather_reply(*days: dict) -> dict:
    """A full GET /weather reply around the given days."""
    days = list(days)
    return {"place": "Test", "timezone": "UTC", "days": days, "trip": WEATHER.trip_summary(days)}


def item(id, category, **kw):
    return {"id": id, "category": category, "color": kw.pop("color", None),
            "occasion": kw.pop("occasion", None), "season": kw.pop("season", None), **kw}


@pytest.fixture
def wardrobe():
    """A small but complete wardrobe: separates, ethnic wear, layers, accessories."""
    return [
        item("shirt", "Shirt", color=["blue"], occasion=["office"], material="cotton"),
        item("tee", "T-Shirt", color=["white"], occasion=["casual"], season=["summer"]),
        item("kurti", "Kurti", color=["yellow"], occasion=["festival", "casual"]),
        item("jeans", "Jeans", color=["black"], occasion=["casual", "office"], material="denim"),
        item("sharara", "Sharara", color=["yellow"], occasion=["festival"]),
        item("saree", "Saree", color=["red"], occasion=["festive", "wedding"]),
        item("shoes", "Shoes", color=["brown"], occasion=["office"]),
        item("slippers", "Slippers", color=["tan"], occasion=["casual"]),
        item("blazer", "Blazer", color=["navy"], occasion=["office"], season=["winter"]),
        item("hoodie", "Hoodie", color=["grey"], occasion=["casual"], season=["winter"]),
        item("shades", "Sunglasses", color=["black"]),
        item("jewels", "Jewellery", color=["gold"]),
        item("dupatta", "Dupatta", color=["yellow"]),
        item("bag", "Bag", color=["black"]),
    ]


@pytest.fixture
def today():
    return date.today()


@pytest.fixture
def days_from(today):
    return lambda n: today + timedelta(days=n)
