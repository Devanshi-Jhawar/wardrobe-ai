"""Gap #1: every garment the other services can name must mean something here."""
import pytest

from app.slots import CATEGORIES, SLOT_KEYWORDS, WEATHER_KEYWORDS, slot_of, weather_types_of
from conftest import WEATHER, vision_classes

CLOTHES = {"top", "bottom", "onepiece", "footwear", "outerwear"}


def test_data_yaml_has_classes():
    assert len(vision_classes()) >= 20


@pytest.mark.parametrize("name", vision_classes())
def test_every_vision_class_has_a_slot(name):
    assert slot_of(name) is not None, f"vision class {name!r} is ignored by the agent"


@pytest.mark.parametrize("name", vision_classes())
def test_every_vision_garment_has_weather_words(name):
    """Clothes (not accessories) must map to the weather service's words,
    so its prefer/avoid advice applies to them."""
    if slot_of(name) in CLOTHES:
        types = weather_types_of(name)
        assert types, f"{name!r} has no weather words"
        assert types <= set(WEATHER.TYPES), f"{name!r} maps to unknown weather words {types - set(WEATHER.TYPES)}"


@pytest.mark.parametrize("word", WEATHER.TYPES)
def test_every_weather_word_is_understood(word):
    """Each word the weather service may prefer/avoid is recognised as a garment."""
    assert word in WEATHER_KEYWORDS
    assert slot_of(word) in CLOTHES


def test_table_only_uses_known_slots():
    assert {slot for slot, _ in CATEGORIES.values()} <= CLOTHES | {"accessory"}
    assert set(SLOT_KEYWORDS) <= CLOTHES | {"accessory"}


@pytest.mark.parametrize("category, slot", [
    ("Kurti", "top"), ("Kameez", "top"), ("Sherwani", "top"),
    ("Shalwar", "bottom"), ("Sharara", "bottom"),
    ("Anarkali", "onepiece"), ("Maxi", "onepiece"), ("Saree", "onepiece"), ("Lehenga", "onepiece"),
    ("Dupatta", "accessory"),
    # hand-typed categories still work through keywords
    ("Kurtis", "top"), ("Tshirts", "top"), ("Heels", "footwear"), ("Palazzo pants", "bottom"),
    ("Kurta set", "onepiece"), ("Mojari", "footwear"), ("unknown thing", None),
])
def test_slots(category, slot):
    assert slot_of(category) == slot


def test_weather_words_for_ethnic_wear():
    assert weather_types_of("Kurti") == {"kurta", "top"}
    assert weather_types_of("Slippers") == {"sandals"}
    assert weather_types_of("Palazzo") == {"trousers"}
