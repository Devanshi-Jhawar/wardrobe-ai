"""The LLM stylist: its pick is used after the guardrails, and any failure keeps
the rules' outfit. No real API calls are made."""
import pytest

from app import config, llm
from app import prefs as P
from app.nodes.composer import composer
from conftest import item, weather_day, weather_reply

CLOSET = [
    item("kurti", "Kurti", color=["green"], occasion=["office", "casual"], style="ethnic"),
    item("palazzo", "Palazzo", color=["white"], occasion=["office", "casual"]),
    item("shirt", "Shirt", color=["white"], occasion=["office"], style="formal"),
    item("trousers", "Trousers", color=["black"], occasion=["office"], style="formal"),
    item("saree", "Saree", color=["red"], occasion=["wedding", "festival"], style="ethnic"),
    item("heels", "Heels", color=["gold"], occasion=["wedding", "party"]),
    item("slippers", "Slippers", color=["grey"], occasion=["casual"]),
    item("loafers", "Loafers", color=["brown"], occasion=["office"]),
    item("bag", "Bag", color=["beige"], occasion=["office"]),
    item("dupatta", "Dupatta", color=["white"]),
]


@pytest.fixture
def fake_llm(monkeypatch):
    """LLM mode on; chat_json returns what the test sets and records the prompt."""
    monkeypatch.setattr(config, "MODE", "llm")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    box = {"data": None, "prompts": []}

    def fake(system, user, **k):
        box["prompts"].append(user)
        return box["data"]
    monkeypatch.setattr(llm, "chat_json", fake)
    return box


def short(item_id):
    """Short id the prompt gives an item (i1 = first in CLOSET)."""
    return f"i{[it['id'] for it in CLOSET].index(item_id) + 1}"


def run(occasion="office", attempts=0, **state):
    return composer({"wardrobe_items": CLOSET, "weather": weather_reply(weather_day(26)),
                     "attempts": attempts, "occasion": occasion, "query": "q",
                     "prefs": state.pop("prefs", P.empty_prefs(True)), **state})


def ids(out):
    return [it["id"] for it in out["draft_outfit"]["items"]]


def test_llm_pick_used_with_note(fake_llm):
    fake_llm["data"] = {"days": [{"day": 1, "items": [short("kurti"), short("palazzo"), short("loafers"),
                                                       short("dupatta")], "note": "Green and white feel fresh."}]}
    out = run()
    assert out["composer_source"] == "llm" and out["llm_used"]
    assert ids(out) == ["kurti", "palazzo", "loafers", "dupatta"]
    assert out["draft_outfit"]["note"] == "Green and white feel fresh."
    assert out["draft_outfit"]["missing_slots"] == []
    prompt = fake_llm["prompts"][0]
    assert "i1: Kurti (top)" in prompt and "occasion: office" in prompt


def test_guardrails(fake_llm):
    # Made-up id, two tops, slippers to a wedding (heels exist), saree + top.
    fake_llm["data"] = {"days": [{"day": 1, "items": ["i99", short("saree"), short("kurti"),
                                                       short("slippers"), short("bag")]}]}
    out = run(occasion="wedding")
    assert out["composer_source"] == "llm"
    got = ids(out)
    assert "kurti" not in got and "slippers" not in got and "saree" in got
    assert any(i in got for i in ("heels", "loafers"))    # footwear filled from the rules


def test_forgotten_slots_filled_from_rules(fake_llm):
    fake_llm["data"] = {"days": [{"day": 1, "items": [short("shirt")]}]}
    got = ids(run())
    assert got[0] == "shirt" and len([i for i in got if i in ("trousers", "palazzo")]) == 1
    assert any(i in got for i in ("loafers", "heels"))


@pytest.mark.parametrize("reply", [None, {}, {"days": "x"}, {"days": [{"day": 1, "items": ["i99"]}]}])
def test_bad_reply_keeps_rules(fake_llm, reply):
    fake_llm["data"] = reply
    out = run()
    assert out["composer_source"] == "rules" and out["llm_used"]
    assert ids(out)


def test_retry_after_llm_is_rules_best_pick(fake_llm, monkeypatch):
    monkeypatch.setattr(config, "MODE", "rules")
    best = ids(run())
    monkeypatch.setattr(config, "MODE", "llm")
    out = run(attempts=1, llm_used=True)       # the critic sent the LLM draft back
    assert out["composer_source"] == "rules" and not fake_llm["prompts"]
    assert ids(out) == best                    # the rules' first choice, not their second


def test_disliked_never_offered(fake_llm):
    prefs = P.empty_prefs(True)
    prefs["dislikes"] = ["saree"]
    fake_llm["data"] = {"days": [{"day": 1, "items": [short("kurti"), short("palazzo")]}]}
    run(prefs=prefs)
    assert "Saree" not in fake_llm["prompts"][0]


def test_trip_days(fake_llm):
    days = [weather_day(26), weather_day(26)]
    fake_llm["data"] = {"days": [
        {"day": 1, "items": ["i1", "i2", "i8"], "note": "Day one."},
        {"day": 2, "items": ["i3", "i4", "i8"], "note": "Day two."}]}
    out = composer({"wardrobe_items": CLOSET, "weather": weather_reply(*days), "attempts": 0,
                    "intent": "trip", "occasion": "office", "query": "q",
                    "dates": {"count": 2}, "prefs": P.empty_prefs(True)})
    draft = out["draft_outfit"]
    assert out["composer_source"] == "llm"
    assert [d["note"] for d in draft["days"]] == ["Day one.", "Day two."]
    assert [it["id"] for it in draft["days"][1]["items"]] == ["shirt", "trousers", "loafers"]
    assert {it["id"] for it in draft["items"]} == {"kurti", "palazzo", "shirt", "trousers", "loafers"}


def test_rules_mode_never_calls(monkeypatch):
    monkeypatch.setattr(config, "MODE", "rules")
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: pytest.fail("called the LLM"))
    assert run()["composer_source"] == "rules"
