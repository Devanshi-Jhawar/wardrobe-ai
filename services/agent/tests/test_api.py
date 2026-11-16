"""The HTTP API end to end, with the other services replaced by fakes.

Covers /wear (gap #2), /rate and likes via /feedback and chat (gap #3), the
trip answer (gap #4), and that the agent keeps answering when services fail.
"""
import pytest
from fastapi.testclient import TestClient

from app import clients
from app.main import app
from conftest import weather_day, weather_reply


class FakeMemory:
    """Just enough of the memory service for the agent."""

    def __init__(self):
        self.prefs = {"likes": [], "dislikes": [], "avoid_repeat_days": 3, "home_city": "Pune"}
        self.worn, self.ratings, self.up = [], [], True

    def memory(self, user_id):
        if not self.up:
            return None
        recent = [i for w in self.worn for i in w["item_ids"]]
        liked = [i for r in self.ratings if r["liked"] for i in r["item_ids"]]
        disliked = [i for r in self.ratings if not r["liked"] for i in r["item_ids"]]
        return {"preferences": self.prefs, "recently_worn_item_ids": recent,
                "liked_item_ids": liked, "disliked_item_ids": disliked, "recent_outfits": []}

    def save(self, user_id, things, kind="dislike"):
        if not self.up:
            return None
        add, rem = ("likes", "dislikes") if kind == "like" else ("dislikes", "likes")
        for t in things:
            if t.lower() not in self.prefs[add]:
                self.prefs[add].append(t.lower())
        self.prefs[rem] = [x for x in self.prefs[rem] if x not in things]
        return dict(self.prefs)

    def wear(self, user_id, item_ids, worn_on=None, occasion=None, city=None, note=None):
        if not self.up:
            return None
        entry = {"id": f"w{len(self.worn)}", "item_ids": item_ids, "occasion": occasion}
        self.worn.append(entry)
        return entry

    def rate(self, user_id, item_ids, liked, reason=None):
        if not self.up:
            return None
        self.ratings.append({"item_ids": item_ids, "liked": liked, "reason": reason})
        return self.ratings[-1]


@pytest.fixture
def mem(monkeypatch, wardrobe, today):
    m = FakeMemory()
    monkeypatch.setattr(clients, "fetch_wardrobe", lambda user_id, limit=200: wardrobe)
    monkeypatch.setattr(clients, "fetch_weather",
                        lambda city, days=1, start_date=None: weather_reply(
                            *(weather_day(26, on=start_date or today) for _ in range(days))))
    monkeypatch.setattr(clients, "embed_text", lambda text: None)
    monkeypatch.setattr(clients, "fetch_memory", m.memory)
    monkeypatch.setattr(clients, "save_preferences", m.save)
    monkeypatch.setattr(clients, "record_worn", m.wear)
    monkeypatch.setattr(clients, "rate_items", m.rate)
    return m


@pytest.fixture
def api():
    return TestClient(app)


def ask(api, q, user="u1"):
    return api.post("/agent", json={"query": q, "user_id": user}).json()["answer"]


def test_wear_then_not_repeated(api, mem):
    first = ask(api, "what should I wear to office?")
    assert first["item_ids"]
    r = api.post("/wear", json={"user_id": "u1", "item_ids": first["item_ids"], "occasion": "office"})
    assert r.status_code == 201 and mem.worn[0]["item_ids"] == first["item_ids"]
    second = ask(api, "what should I wear to office?")
    clothes = lambda a: {i["id"] for i in a["outfit"] if i["category"] not in {"Bag", "Jewellery"}}
    # Only repeats what has no office-worthy alternative (the one pair of jeans,
    # the one blazer, and shoes - the other footwear is slippers).
    assert not clothes(first) & clothes(second) - {"jeans", "blazer", "shoes"}


def test_wear_validation_and_memory_down(api, mem):
    assert api.post("/wear", json={"user_id": "u1", "item_ids": []}).status_code == 422
    mem.up = False
    assert api.post("/wear", json={"user_id": "u1", "item_ids": ["shirt"]}).status_code == 503


def test_rate_thumbs_down_removes_item(api, mem):
    assert "Shirt" in [i["category"] for i in ask(api, "what should I wear to office?")["outfit"]]
    r = api.post("/rate", json={"user_id": "u1", "item_ids": ["shirt"], "liked": False, "reason": "itchy"})
    assert r.status_code == 201
    assert "Shirt" not in [i["category"] for i in ask(api, "what should I wear to office?")["outfit"]]


def test_likes_from_chat_and_feedback(api, mem):
    a = ask(api, "I love yellow and ethnic wear")
    assert a["type"] == "preference_saved" and a["kind"] == "like"
    assert mem.prefs["likes"] == ["yellow", "ethnic"]
    assert "Kurti" in [i["category"] for i in ask(api, "what should I wear today?")["outfit"]]
    # changing your mind: a dislike replaces the like
    ask(api, "I don't like yellow")
    assert "yellow" in mem.prefs["dislikes"] and "yellow" not in mem.prefs["likes"]
    r = api.post("/feedback", json={"user_id": "u1", "like": "blue"})
    assert r.status_code == 200 and "blue" in mem.prefs["likes"]
    assert api.post("/feedback", json={"user_id": "u1"}).status_code == 422


def test_preference_memory_down(api, mem):
    mem.up = False
    a = ask(api, "I love blue")
    assert a["type"] == "preference_not_saved"
    assert api.post("/feedback", json={"user_id": "u1", "dislike": "x"}).status_code == 503


def test_trip_answer(api, mem):
    a = ask(api, "packing for a 3-day trip to Shimla")
    assert a["type"] == "trip_plan" and len(a["days"]) == 3
    assert "Day 1" in a["message"] and "Pack (" in a["message"]
    assert all(d["item_ids"] for d in a["days"])
    assert len(a["packing_list"]) == len({i["id"] for i in a["packing_list"]})


def test_services_down_still_answers(api, mem, monkeypatch):
    mem.up = False
    monkeypatch.setattr(clients, "fetch_weather", lambda *a, **k: None)
    a = ask(api, "what should I wear to office?")
    assert a["type"] == "recommendation" and a["outfit"]


def test_weather_uses_home_city_when_none_asked(api, mem, monkeypatch, today):
    asked = []
    monkeypatch.setattr(clients, "fetch_weather", lambda city, days=1, start_date=None: (
        asked.append(city) or {**weather_reply(weather_day(26, on=today)), "place": f"{city}, Maharashtra, India"}))
    a = ask(api, "what should I wear to office?")
    assert asked == ["Pune"]
    assert a["weather_source"] == "home" and a["weather_place"] == "Pune, Maharashtra"
    assert "in Pune, Maharashtra" in a["rationale"]
    a = ask(api, "what should I wear to office in Goa?")
    assert asked[-1] == "Goa" and a["weather_source"] == "asked"


def test_no_city_no_weather(api, mem, monkeypatch):
    mem.prefs["home_city"] = None
    monkeypatch.setattr(clients, "fetch_weather", lambda *a, **k: pytest.fail("guessed a place"))
    a = ask(api, "what should I wear to office?")
    assert a["outfit"] and a["weather_missing"] == "no_city" and a["weather_place"] is None
    assert "°C" not in (a["rationale"] or "")
