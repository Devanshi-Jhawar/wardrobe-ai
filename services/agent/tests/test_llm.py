"""The LLM planner (Groq or xAI): its reply is validated and merged with the rules, and any
failure falls back to the rules. No real API calls are made."""
from datetime import date, timedelta

import httpx
import pytest

from app import config, llm
from app.nodes import planner as P


@pytest.fixture
def fake_llm(monkeypatch):
    """Turn LLM mode on and make chat_json return whatever the test sets."""
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    reply = {"data": None}
    monkeypatch.setattr(llm, "chat_json", lambda system, user, **k: reply["data"])
    return reply


def test_llm_reply_used(fake_llm):
    start = (date.today() + timedelta(days=3)).isoformat()
    fake_llm["data"] = {
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


def test_made_up_start_date_loses_to_relative_day(fake_llm):
    fake_llm["data"] = {"intent": "trip", "city": "Manali",
                        "dates": {"start_date": (date.today() + timedelta(days=7)).isoformat()},
                        "itinerary": [{"day": 1, "occasion": "festival"}, {"day": 2, "occasion": "wedding"}]}
    out = P.planner({"query": "Manali next weekend, haldi saturday and wedding sunday"})
    assert out["dates"] == {"relative": "next weekend", "count": 2}


def test_invalid_fields_fall_back_to_rules(fake_llm):
    fake_llm["data"] = {"intent": "dance", "occasion": "galactic", "city": "",
                    "dates": {"count": 99, "start_date": "not a date"}, "itinerary": "x"}
    out = P.planner({"query": "what should I wear to office tomorrow in Goa?"})
    assert out["planner_source"] == "llm"
    assert out["intent"] == "recommend"            # from the rules
    assert out["occasion"] is None                 # the LLM said an unknown one
    assert out["city"] == "Goa"                    # rules kept
    assert out["dates"] == {"relative": "tomorrow"}


def test_preference_from_llm(fake_llm):
    fake_llm["data"] = {"intent": "save_preference", "preference_kind": "dislike",
                    "preferences": ["Frocks", "neon colours"]}
    out = P.planner({"query": "ugh, frocks and anything neon are not me"})
    assert out == {"intent": "save_preference", "preference_kind": "dislike",
                   "preferences": ["frocks", "neon colours"],
                   "preference": "frocks, neon colours", "planner_source": "llm"}


def test_llm_failure_uses_rules(fake_llm):
    fake_llm["data"] = None
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


def test_pick_model_groq():
    ids = ["whisper-large-v3", "llama-guard-4-12b", "llama-3.1-8b-instant",
           "llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
    assert llm._pick_model(ids, "groq") == "llama-3.3-70b-versatile"
    assert llm._pick_model(["whisper-large-v3", "llama-3.1-8b-instant"], "groq") == "llama-3.1-8b-instant"
    assert llm._pick_model(["whisper-large-v3", "some-new-120b-model"], "groq") == "some-new-120b-model"
    assert llm._pick_model([], "groq") is None


def test_pick_model_xai():
    ids = ["grok-imagine-image", "grok-4", "grok-4-fast-reasoning",
           "grok-4-fast-non-reasoning", "grok-3-mini"]
    assert llm._pick_model(ids, "xai") == "grok-4-fast-non-reasoning"
    assert llm._pick_model(["grok-2-vision", "grok-3"], "xai") == "grok-3"


def test_chat_json_network_error_returns_none(monkeypatch):
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_MODEL", "llama-test")

    def boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(llm.httpx, "post", boom)
    assert llm.chat_json("s", "u") is None


def test_chat_json_parses_reply(monkeypatch):
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_MODEL", "llama-test")
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, auth=headers["Authorization"], model=json["model"])
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"intent": "gap"}'}}]},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.chat_json("s", "u") == {"intent": "gap"}
    assert sent["url"].endswith("/chat/completions") and sent["auth"] == "Bearer k"
    assert sent["model"] == "llama-test"


def test_named_festival_beats_generic_party(fake_llm):
    fake_llm["data"] = {"intent": "recommend", "occasion": "party"}
    assert P.planner({"query": "outfit for a diwali party"})["occasion"] == "festival"
    fake_llm["data"] = {"intent": "recommend", "occasion": "party"}
    assert P.planner({"query": "outfit for a birthday party"})["occasion"] == "party"


def test_reasoning_model_gets_low_effort_and_room(monkeypatch):
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "LLM_MODEL", "openai/gpt-oss-120b")
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(json)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    llm.chat_json("s", "u", max_tokens=300)
    assert sent["reasoning_effort"] == "low" and sent["max_tokens"] == 300 + llm.REASONING_ROOM


def test_rate_limit_retried_once(monkeypatch):
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "LLM_API_KEY", "k")
    monkeypatch.setattr(config, "LLM_MODEL", "m")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    replies = [httpx.Response(429, headers={"retry-after": "1"}),
               httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}}]})]
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: replies.pop(0))
    assert llm.chat_json("s", "u") == {"ok": 1}
