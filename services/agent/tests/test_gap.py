"""Gap suggestions beyond empty slots: occasion, weather, complements, coverage."""
from app import prefs as P
from app.nodes.gap import gap
from conftest import item


def kinds(out):
    return [s["kind"] for s in out["missing_items"]]


def run(items, draft=None, **state):
    return gap({"wardrobe_items": items, "draft_outfit": draft,
                "prefs": state.pop("prefs", P.empty_prefs(True)), **state})


def test_missing_slot_still_reported():
    items = [item("t", "T-Shirt", occasion=["casual"]), item("j", "Jeans", occasion=["casual"])]
    out = run(items, {"items": items, "missing_slots": ["footwear"]}, occasion="casual")
    s = out["missing_items"][0]
    assert s["kind"] == "missing" and s["slot"] == "footwear"
    assert s["search_link"].startswith("https://www.google.com/search?q=")


def test_occasion_gap_when_owned_clothes_dont_suit():
    items = [item("t", "T-Shirt", occasion=["casual"]), item("j", "Jeans", occasion=["casual"]),
             item("s", "Shoes", occasion=["office"])]
    out = run(items, {"items": items, "missing_slots": []}, occasion="office")
    occ = [s for s in out["missing_items"] if s["kind"] == "occasion"]
    assert occ and occ[0]["slot"] == "top" and "formal shirt" in occ[0]["title"]


def test_weather_gear_not_owned():
    items = [item("t", "T-Shirt"), item("j", "Jeans"), item("s", "Shoes")]
    out = run(items, {"items": items, "missing_slots": [], "carry": ["umbrella or raincoat", "sunscreen"]})
    weather = [s for s in out["missing_items"] if s["kind"] == "weather"]
    assert len(weather) == 1 and "umbrella" in weather[0]["title"]


def test_complement_with_colour_and_skip_owned(wardrobe):
    kurti = next(i for i in wardrobe if i["id"] == "kurti")
    sharara = next(i for i in wardrobe if i["id"] == "sharara")
    out = run(wardrobe, {"items": [kurti, sharara], "missing_slots": []}, occasion="festival")
    comp = [s for s in out["missing_items"] if s["kind"] == "complement"]
    assert comp
    assert all("dupatta" not in s["title"] for s in comp)        # already owns one
    assert comp[0]["title"].startswith("white ")                 # pairs with yellow


def test_dislikes_never_suggested():
    items = [item("d", "Dress", color=["black"], occasion=["party"]), item("h", "Heels", occasion=["party"])]
    prefs = P.empty_prefs(True) | {"dislikes": ["sandals"]}
    out = run(items, {"items": items, "missing_slots": []}, occasion="party", prefs=prefs)
    assert all("sandal" not in s["title"] for s in out["missing_items"])


def test_shopping_question_reports_coverage():
    items = [item("t", "T-Shirt", occasion=["casual"]), item("j", "Jeans", occasion=["casual"]),
             item("s", "Slippers", occasion=["casual"])]
    out = run(items, None, intent="gap")
    assert "coverage" in kinds(out)
    assert any("office" in s["reason"] for s in out["missing_items"])
    assert len(out["missing_items"]) <= 6


def test_trip_day_occasion_gap_names_day():
    tee = item("t", "T-Shirt", occasion=["casual"])
    jeans = item("j", "Jeans", occasion=["casual"])
    draft = {"items": [tee, jeans], "missing_slots": [],
             "days": [{"day": 2, "occasion": "wedding", "items": [tee, jeans]}]}
    out = run([tee, jeans], draft, itinerary=[{"day": 2, "occasion": "wedding"}])
    occ = [s for s in out["missing_items"] if s["kind"] == "occasion"]
    assert occ and occ[0]["day"] == 2 and "(day 2)" in occ[0]["reason"]
