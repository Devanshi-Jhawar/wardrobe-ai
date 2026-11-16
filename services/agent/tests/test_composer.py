"""Composer: weather reading, weather advice (gap #5), trips (gap #4),
ethnic outfits (gap #1), memory and search ranking."""
from app import prefs as P
from app.nodes.composer import _search_boosts, _weather_signal, composer
from conftest import item, weather_day, weather_reply

HOT, MILD, COLD, VERY_COLD = 35, 26, 15, 5


def compose(wardrobe, weather=None, **state):
    out = composer({"wardrobe_items": wardrobe, "weather": weather, "attempts": 0,
                    "prefs": state.pop("prefs", P.empty_prefs(True)), **state})
    return out["draft_outfit"]


def cats(draft):
    return [i["category"] for i in draft["items"]]


# --- reading the weather (the original bug: everything looked cold + rainy) ---

def test_signal_follows_weather_labels():
    hot = _weather_signal(weather_reply(weather_day(HOT)))
    assert hot["hot"] and not hot["cold"] and not hot["rain"] and hot["temp"] == HOT
    cold = _weather_signal(weather_reply(weather_day(COLD)))
    assert cold["cold"] and not cold["hot"]
    wet = _weather_signal(weather_reply(weather_day(MILD, rain=80)))
    assert wet["rain"] and not wet["cold"] and not wet["hot"]
    assert _weather_signal(None)["temp"] is None


def test_hot_day_no_layer_cold_day_layer(wardrobe):
    hot = compose(wardrobe, weather_reply(weather_day(HOT)), occasion="office")
    assert "Blazer" not in cats(hot) and "Hoodie" not in cats(hot)
    cold = compose(wardrobe, weather_reply(weather_day(COLD)), occasion="office")
    assert "Blazer" in cats(cold)


# --- gap #5: the weather service's advice is used ---

def test_hot_day_prefers_sandals_over_shoes(wardrobe):
    # Shoes are "office" but the weather says sandals; with no occasion, weather decides.
    draft = compose(wardrobe, weather_reply(weather_day(HOT)))
    assert "Slippers" in cats(draft)


def test_cold_day_prefers_shoes(wardrobe):
    draft = compose(wardrobe, weather_reply(weather_day(COLD)))
    assert "Shoes" in cats(draft)


def test_material_advice():
    linen = item("l", "Shirt", material="linen")
    wool = item("w", "Shirt", material="wool")
    base = [item("j", "Jeans"), item("s", "Shoes")]
    assert "l" in [i["id"] for i in compose([wool, linen] + base, weather_reply(weather_day(HOT)))["items"]]
    assert "w" in [i["id"] for i in compose([linen, wool] + base, weather_reply(weather_day(COLD)))["items"]]


def test_rain_avoids_white():
    white = item("white", "T-Shirt", color=["white"])
    navy = item("navy", "T-Shirt", color=["navy"])
    base = [item("j", "Jeans"), item("s", "Shoes")]
    ids = [i["id"] for i in compose([white, navy] + base, weather_reply(weather_day(MILD, rain=90)))["items"]]
    assert "navy" in ids and "white" not in ids


def test_weather_accessories_owned_and_carried(wardrobe):
    hot = compose(wardrobe, weather_reply(weather_day(HOT)))
    assert "Sunglasses" in cats(hot)                       # owned -> worn
    assert "sunscreen" in hot["carry"]                     # not owned -> carry
    assert "cap or hat" in hot["carry"]
    wet = compose(wardrobe, weather_reply(weather_day(MILD, rain=90)))
    assert "umbrella or raincoat" in wet["carry"]
    assert "Sunglasses" not in cats(wet)


def test_occasion_accessories(wardrobe):
    party = compose(wardrobe, None, occasion="wedding")
    assert "Jewellery" in cats(party) and "Bag" in cats(party)
    gym = compose(wardrobe, None, occasion="gym")
    assert "Jewellery" not in cats(gym)


# --- gap #1: ethnic wear is used ---

def test_festival_ethnic_outfit_with_dupatta(wardrobe):
    no_saree = [i for i in wardrobe if i["id"] != "saree"]
    draft = compose(no_saree, None, occasion="festival")
    assert cats(draft)[:2] == ["Kurti", "Sharara"]
    assert "Dupatta" in cats(draft)


def test_saree_for_wedding_no_dupatta(wardrobe):
    draft = compose(wardrobe, None, occasion="wedding")
    assert "Saree" in cats(draft) and "Dupatta" not in cats(draft)


def test_only_ethnic_wardrobe_makes_outfits():
    ethnic = [item("k", "Kameez"), item("s", "Shalwar"), item("m", "Slippers")]
    assert cats(compose(ethnic)) == ["Kameez", "Shalwar", "Slippers"]
    assert compose(ethnic)["missing_slots"] == []


# --- gap #4: trips are planned day by day ---

def test_trip_plans_each_day_without_repeats(wardrobe, days_from):
    weather = weather_reply(weather_day(HOT, on=days_from(0)), weather_day(COLD, on=days_from(1)),
                            weather_day(MILD, rain=90, on=days_from(2)))
    draft = compose(wardrobe, weather, intent="trip")
    assert len(draft["days"]) == 3
    day1, day2, day3 = (d["items"] for d in draft["days"])
    clothes = lambda items: {i["id"] for i in items if i["category"] not in
                             {"Sunglasses", "Jewellery", "Dupatta", "Bag"}}
    tops = [i["id"] for d in (day1, day2, day3) for i in d if i["category"] in {"Shirt", "T-Shirt", "Kurti"}]
    assert len(tops) == len(set(tops)) == 3, "a top repeats although three exist"
    # Only items with no suitable unused alternative may repeat: jeans are the
    # only western bottom, shoes the only footwear that suits cold/rain.
    repeated = (clothes(day1) & clothes(day2)) | (clothes(day2) & clothes(day3)) | (clothes(day1) & clothes(day3))
    assert repeated <= {"jeans", "shoes"}, repeated
    assert any(i["category"] in {"Blazer", "Hoodie"} for i in day2)        # cold day layered
    assert not any(i["category"] in {"Blazer", "Hoodie"} for i in day1)    # hot day not
    packed = [i["id"] for i in draft["items"]]
    assert len(packed) == len(set(packed))                                  # each item packed once
    assert set(packed) == {i["id"] for d in draft["days"] for i in d["items"]}
    assert "umbrella or raincoat" in draft["carry"]


def test_trip_repeats_only_when_needed(days_from):
    tiny = [item("t1", "Shirt"), item("t2", "Shirt"), item("j", "Jeans"), item("s", "Shoes")]
    weather = weather_reply(*(weather_day(MILD, on=days_from(n)) for n in range(3)))
    days = [d["items"] for d in compose(tiny, weather, intent="trip")["days"]]
    tops = [next(i["id"] for i in d if i["category"] == "Shirt") for d in days]
    assert tops[0] != tops[1]                                # two shirts -> alternate
    assert all(any(i["id"] == "j" for i in d) for d in days) # one pair of jeans -> repeats


def test_trip_without_weather_still_plans_days():
    tiny = [item("t", "Shirt"), item("j", "Jeans"), item("s", "Shoes")]
    draft = compose(tiny, None, intent="trip", dates={"count": 3})
    assert len(draft["days"]) == 3


def test_one_day_trip_is_a_single_outfit(wardrobe):
    draft = compose(wardrobe, weather_reply(weather_day(MILD)), intent="trip")
    assert "days" not in draft


# --- memory and search ---

def test_memory_dislikes_recent_wears_likes():
    items = [item("t1", "Shirt"), item("t2", "Shirt"), item("b1", "Jeans"), item("f1", "Sneakers")]
    prefs = {**P.empty_prefs(True), "recently_worn_item_ids": ["t1", "b1"]}
    ids = [i["id"] for i in compose(items, prefs=prefs)["items"]]
    assert "t2" in ids and "t1" not in ids and "b1" in ids   # repeat only when it's the only option
    prefs = {**P.empty_prefs(True), "dislikes": ["sneaker"], "liked_item_ids": ["t1"]}
    ids = [i["id"] for i in compose(items, prefs=prefs)["items"]]
    assert "f1" not in ids and "t1" in ids


def test_search_boosts():
    assert _search_boosts({"a": 0.20, "b": 0.30, "c": 0.25}) == {"a": 0, "b": 5, "c": 2}
    assert _search_boosts({"a": 0.2, "b": 0.2}) == {}
    items = [item("saree", "Saree", color=["red"]), item("tee", "T-Shirt", color=["white"])]
    # tags cover "red" -> CLIP's ranking is ignored, the red item wins
    assert _search_boosts({"saree": 0.1, "tee": 0.3}, "red", items) == {"saree": 3}


def test_onepiece_only_when_it_clearly_fits(wardrobe):
    assert "Saree" not in cats(compose(wardrobe))                              # generic -> separates
    assert "Saree" in cats(compose(wardrobe, search_text="red saree"))         # asked for it
    assert "Saree" in cats(compose(wardrobe, occasion="wedding"))              # occasion fits


def test_trip_repeats_suitable_shoes_rather_than_cold_weather_sandals(wardrobe, days_from):
    weather = weather_reply(*(weather_day(COLD, on=days_from(n)) for n in range(3)))
    for day in compose(wardrobe, weather, intent="trip")["days"]:
        feet = [i["category"] for i in day["items"] if i["category"] in {"Shoes", "Slippers"}]
        assert feet == ["Shoes"], f"day {day['day']}: {feet}"


def test_bottom_matches_top_style(wardrobe, days_from):
    weather = weather_reply(*(weather_day(MILD, on=days_from(n)) for n in range(4)))
    ethnic_tops, ethnic_bottoms = {"Kurti", "Kameez", "Sherwani"}, {"Sharara", "Shalwar"}
    for day in compose(wardrobe, weather, intent="trip")["days"]:
        c = {i["category"] for i in day["items"]}
        if c & ethnic_tops:
            assert c & ethnic_bottoms, f"day {day['day']} pairs an ethnic top with {c}"
        if c & {"Shirt", "T-Shirt"}:
            assert not c & ethnic_bottoms, f"day {day['day']} pairs a western top with {c}"


# --- office dress code: festive or beachy pieces lose to smart ones ---

OFFICE_CLOSET = [
    item("kurti", "Kurti", color=["green"], occasion=["casual", "office"], style="ethnic"),
    item("sharara", "Sharara", color=["purple"], occasion=["festival", "wedding"], style="ethnic"),
    item("shirt", "Shirt", color=["white"], occasion=["office", "casual"], style="smart casual"),
    item("jeans", "Jeans", color=["navy"], occasion=["casual", "trip"], style="casual"),
    item("shoes", "Shoes", color=["brown"], occasion=["office"]),
]


def test_office_avoids_festive_bottom():
    draft = compose(OFFICE_CLOSET, weather_reply(weather_day(HOT)), occasion="office")
    assert "Sharara" not in cats(draft)
    assert {"Shirt", "Jeans"} <= set(cats(draft))


def test_office_takes_tailored_trousers_when_owned():
    closet = OFFICE_CLOSET + [item("trousers", "Trousers", color=["black"], occasion=["office"], style="formal")]
    draft = compose(closet, weather_reply(weather_day(MILD)), occasion="office")
    assert "Trousers" in cats(draft)


def test_office_blazer_worn_when_mild_carried_when_hot():
    closet = OFFICE_CLOSET + [item("blazer", "Blazer", color=["navy"], occasion=["office"], style="formal")]
    mild = compose(closet, weather_reply(weather_day(MILD)), occasion="office")
    assert "Blazer" in cats(mild)
    hot = compose(closet, weather_reply(weather_day(HOT)), occasion="office")
    assert "Blazer" not in cats(hot)
    assert any("blazer" in c for c in hot["carry"])


def test_dress_code_only_for_office():
    party = compose(OFFICE_CLOSET, weather_reply(weather_day(MILD)), occasion="festival")
    assert "Sharara" in cats(party)


def test_office_repeats_shoes_rather_than_wearing_slippers():
    closet = OFFICE_CLOSET + [item("slippers", "Slippers", color=["grey"], occasion=["casual"])]
    prefs = P.empty_prefs(True)
    prefs["recently_worn_item_ids"] = ["shoes"]
    draft = compose(closet, weather_reply(weather_day(MILD)), occasion="office", prefs=prefs)
    assert "Shoes" in cats(draft) and "Slippers" not in cats(draft)
    casual = compose(closet, weather_reply(weather_day(MILD)), occasion="casual", prefs=prefs)
    assert "Slippers" in cats(casual)


WEDDING_CLOSET = [
    item("lehenga", "Lehenga", color=["red"], occasion=["wedding"], style="ethnic"),
    item("slippers", "Slippers", color=["grey"], occasion=["casual"]),
    item("heels", "Heels", color=["gold"], occasion=["party", "wedding"]),
    item("tee", "T-Shirt", color=["white"], occasion=["casual"]),
    item("joggers", "Track Pants", color=["black"], occasion=["gym"]),
]


def test_dressy_occasions_skip_slippers_even_if_heels_were_just_worn():
    prefs = P.empty_prefs(True)
    prefs["recently_worn_item_ids"] = ["heels"]
    for occ in ("wedding", "festival", "party", "date"):
        draft = compose(WEDDING_CLOSET, weather_reply(weather_day(MILD)), occasion=occ, prefs=prefs)
        assert "Slippers" not in cats(draft), occ
        assert "Track Pants" not in cats(draft), occ


def test_slippers_used_when_nothing_else_and_fine_for_casual():
    only = [it for it in WEDDING_CLOSET if it["id"] != "heels"]
    assert "Slippers" in cats(compose(only, weather_reply(weather_day(MILD)), occasion="wedding"))
    assert "Slippers" in cats(compose(only, weather_reply(weather_day(MILD)), occasion="casual"))


def test_blazer_rule_stays_office_only():
    closet = OFFICE_CLOSET + [item("blazer", "Blazer", color=["navy"], occasion=["office"], style="formal")]
    assert "Blazer" not in cats(compose(closet, weather_reply(weather_day(MILD)), occasion="party"))
