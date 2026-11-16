"""The Grok planner: its reply is validated and merged with the rules, and any
failure falls back to the rules. No real API calls are made."""
from datetime import date, timedelta

import httpx
import pytest

from app import config, llm
from app.nodes import planner as P


@pytest.fixture
def grok(monkeypatch):
    """Turn LLM mode on and make chat_json return whatever the test sets."""
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "XAI_API_KEY", "test-key")
    reply = {"data": None}
    monkeypatch.setattr(llm, "chat_json", lambda system, user, **k: reply["data"])
    return reply


def test_llm_reply_used(grok):
    start = (date.today() + timedelta(days=3)).isoformat()
    grok["data"] = {
        "intent": "trip", "occasion": None, "city": "Udaipur",
        "dates": {"relative": None, "start_date": start, "count": None},
        "search_text": None, "preference_kind": None, "preferences": [],
        "itinerary": [{"day": 1, "occasion": "wedding", "activity": "haldi"},
                      {"day": 2, "occasion": "Sangeet", "activity": "sangeet night"}],
    }
    out = P.planner({"query": "my cousin's shaadi in udaipur from the 19th, haldi then sangeet"})
    assert out["planner_source"] == "llm"
    assert out["city"] == "Udaipur" and out["intent"] == "trip"
    assert out["dates"] == {"start": start, "count": 2}
    assert [d["occasion"] for d in out["itinerary"]] == ["wedding", "wedding"]  # sangeet -> wedding


def test_invalid_fields_fall_back_to_rules(grok):
    grok["data"] = {"intent": "dance", "occasion": "galactic", "city": "",
                    "dates": {"count": 99, "start_date": "not a date"}, "itinerary": "x"}
    out = P.planner({"query": "what should I wear to office tomorrow in Goa?"})
    assert out["planner_source"] == "llm"
    assert out["intent"] == "recommend"            # from the rules
    assert out["occasion"] is None                 # the LLM said an unknown one
    assert out["city"] == "Goa"                    # rules kept
    assert out["dates"] == {"relative": "tomorrow"}


def test_preference_from_llm(grok):
    grok["data"] = {"intent": "save_preference", "preference_kind": "dislike",
                    "preferences": ["Frocks", "neon colours"]}
    out = P.planner({"query": "ugh, frocks and anything neon are not me"})
    assert out == {"intent": "save_preference", "preference_kind": "dislike",
                   "preferences": ["frocks", "neon colours"],
                   "preference": "frocks, neon colours", "planner_source": "llm"}


def test_llm_failure_uses_rules(grok):
    grok["data"] = None
    out = P.planner({"query": "packing for a 4-day trip to Shimla"})
    assert out["planner_source"] == "rules" and out["dates"] == {"count": 4}


def test_rules_mode_never_calls(monkeypatch):
    monkeypatch.setattr(config, "MODE", "rules")
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: pytest.fail("called the LLM"))
    assert P.planner({"query": "office tomorrow"})["planner_source"] == "rules"


# --- the HTTP client itself ---

def test_extract_json_tolerates_fences():
    assert llm._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm._extract_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    assert llm._extract_json("no json here") is None


def test_pick_model_prefers_fast_text():
    ids = ["grok-imagine-image", "grok-4", "grok-4-fast-reasoning",
           "grok-4-fast-non-reasoning", "grok-3-mini"]
    assert llm._pick_model(ids) == "grok-4-fast-non-reasoning"
    assert llm._pick_model(["grok-2-vision", "grok-3"]) == "grok-3"
    assert llm._pick_model([]) is None


def test_chat_json_network_error_returns_none(monkeypatch):
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "XAI_API_KEY", "k")
    monkeypatch.setattr(config, "XAI_MODEL", "grok-test")

    def boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(llm.httpx, "post", boom)
    assert llm.chat_json("s", "u") is None


def test_chat_json_parses_reply(monkeypatch):
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "XAI_API_KEY", "k")
    monkeypatch.setattr(config, "XAI_MODEL", "grok-test")
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, auth=headers["Authorization"], model=json["model"])
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"intent": "gap"}'}}]},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.chat_json("s", "u") == {"intent": "gap"}
    assert sent["url"].endswith("/chat/completions") and sent["auth"] == "Bearer k"
    assert sent["model"] == "grok-test"
