"""Node 1: planner — understands the request.

Turns a free-form sentence into structured fields (intent, occasion, city,
dates) the rest of the agent can act on. It only *interprets* — it fetches
nothing and recommends nothing.

Two implementations behind one function:
  - rules: fast, no API key, handles the common phrasings;
  - llm (AGENT_MODE=llm + XAI_API_KEY): Grok reads the sentence and returns
    the same fields as JSON. Anything it gets wrong or leaves out is filled
    from the rules, and if the call fails the rules answer is used as is.

Trips can carry a per-day itinerary ("day 1 beach, day 2 wedding"): a list of
{day, occasion, activity} the composer dresses each day for.
"""
import re
from datetime import date, timedelta

from .. import llm
from ..state import OutfitState

# Occasion -> the words that hint at it (checked in this order).
OCCASION_KEYWORDS = {
    "office":   ["office", "work", "meeting", "interview", "client"],
    "wedding":  ["wedding", "shaadi", "reception", "sangeet"],
    "festival": ["festival", "festive", "diwali", "pooja", "puja", "eid", "navratri"],
    "party":    ["party", "club", "night out", "cocktail"],
    "gym":      ["gym", "workout", "exercise", "running"],
    "date":     ["date night", "date"],
    # Trip activities. Wardrobe items aren't tagged with these, so the
    # composer reads them through OCCASION_TAGS (beach -> casual/trip).
    "beach":       ["beach", "pool", "swim", "seaside"],
    "hiking":      ["hike", "hiking", "trek", "trekking"],
    "sightseeing": ["sightseeing", "sight seeing", "exploring", "museum", "city tour"],
    "travel":      ["travel day", "flight", "airport", "train journey", "road trip"],
    "casual":   ["casual", "hangout", "chill", "brunch", "outing", "day out"],
}

# Phrases that flip the whole request into a different intent.
# Dislikes are checked first: "I don't like X" also contains "like".
PREF_TRIGGERS = ["don't like", "dont like", "do not like", "dislike", "hate",
                 "not a fan of", "i avoid", "never wear", "don't wear", "dont wear",
                 "don't want", "dont want", "can't stand", "cant stand"]
LIKE_TRIGGERS = ["i like", "i love", "i prefer", "i really like", "i really love",
                 "i'm a fan of", "im a fan of", "big fan of", "my favourite", "my favorite",
                 "i enjoy wearing", "love wearing", "like wearing"]
TRIP_TRIGGERS = ["trip", "travel", "traveling", "travelling", "vacation",
                 "holiday", "visiting", "packing", "pack for"]
GAP_TRIGGERS = ["should i buy", "what to buy", "need to buy", "shopping",
                "what am i missing", "missing", "buy for", "add to my wardrobe"]

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Words that carry no description of the clothes themselves. Whatever is left
# after removing these (and the occasion, city and date words) is what the user
# said about the garments — "red saree", "white t-shirt", "ethnic" — and that is
# what gets searched. "What should I wear to office tomorrow?" leaves nothing.
FILLER_WORDS = set("""
a an the and or but of to in on at for from with without by into my me i i'm im you your we our
it its this that these those is am are was were be been being do does did can could should would will
shall may might must what which who whom how when where why wear wearing wore put go going get got
want wanna like need suggest suggestion recommend recommendation give show tell help please pick choose
outfit outfits look looks clothes clothing something anything some any thing things one ones today
tonight tomorrow weekend week next day days morning evening night trip travel traveling travelling
vacation holiday visiting visit packing pack plan planning ideas idea good nice best new also just
really maybe so very too
""".split())


def _detect_intent(q: str) -> str:
    if any(t in q for t in PREF_TRIGGERS) or any(t in q for t in LIKE_TRIGGERS):
        return "save_preference"
    if any(t in q for t in GAP_TRIGGERS):
        return "gap"
    if any(t in q for t in TRIP_TRIGGERS) or re.search(r"\b\d+\s*-?\s*day", q):
        return "trip"
    return "recommend"


def _detect_occasion(q: str) -> str | None:
    for occasion, words in OCCASION_KEYWORDS.items():
        if any(w in q for w in words):
            return occasion
    return None


RELATIVE_DAYS = ["today", "tonight", "tomorrow", "this weekend", "next weekend",
                 "this week", "next week"]


def _detect_dates(q: str) -> dict:
    """{"count": 4}, {"relative": "tomorrow"}, or both ("4-day trip from saturday")."""
    out: dict = {}
    m = re.search(r"\b(\d+)\s*-?\s*days?\b", q)      # "4-day", "4 day", "4 days"
    if m:
        out["count"] = int(m.group(1))
    for rel in RELATIVE_DAYS:
        if rel in q:
            out["relative"] = rel
            break
    else:
        for day in WEEKDAYS:
            if day in q:
                out["relative"] = day
                break
    if "count" in out and out.get("relative") in ("this weekend", "next weekend",
                                                  "this week", "next week"):
        out.pop("relative")                     # "4 days next week": keep the count
    return out


_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
             "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}
_DAY_MARK = re.compile(
    r"\bday\s*(\d+)\b"                                    # day 1
    r"|\b(\d+)(?:st|nd|rd|th)\s+day\b"                    # 2nd day
    r"|\b(" + "|".join(_ORDINALS) + r"|last|final)\s+day\b")   # third day, last day
_ACTIVITY_FILLER = {"is", "will", "be", "we", "i", "for", "a", "an", "the", "at", "on",
                    "of", "and", "then", "to", "go", "going", "have", "has", "there",
                    "it", "its", "my", "our", "some", "with"}


def _detect_itinerary(q: str, count: int | None) -> list[dict]:
    """Per-day plans from "day 1 beach, day 2 wedding, last day travel".

    Each marker starts a segment that runs to the next marker; the segment's
    occasion and a short activity text come from its words.
    """
    marks = list(_DAY_MARK.finditer(q))
    if not marks:
        return []
    numbered = [int(m.group(1) or m.group(2) or _ORDINALS.get(m.group(3), 0))
                for m in marks]
    last = max([count or 0] + numbered)
    plan: dict[int, dict] = {}
    for i, m in enumerate(marks):
        day = numbered[i] or last or len(marks)          # "last day" -> the final day
        end = marks[i + 1].start() if i + 1 < len(marks) else len(q)
        seg = re.split(r"[.;\n]", q[m.end():end])[0]
        words = [w for w in re.findall(r"[a-z][a-z'-]*", seg) if w not in _ACTIVITY_FILLER]
        plan[day] = {"day": day, "occasion": _detect_occasion(seg),
                     "activity": " ".join(words)[:60] or None}
    return [plan[d] for d in sorted(plan) if d >= 1]


def _detect_city(q_raw: str) -> str | None:
    # Heuristic: a capitalised word after a travel preposition, or "<City> trip".
    patterns = [
        r"\b(?:in|to|at|for|visiting|visit)\s+([A-Z][a-zA-Z]+)",
        r"\b([A-Z][a-zA-Z]+)\s+trip\b",
        r"\btrip\s+to\s+([A-Z][a-zA-Z]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, q_raw)
        if m:
            cand = m.group(1).strip()
            if cand.lower() not in WEEKDAYS + ["i", "what", "office", "work"]:
                return cand
    return None


def _search_text(q: str, city: str | None) -> str | None:
    """The descriptive part of the request, for wardrobe search (or None)."""
    skip = set(FILLER_WORDS) | set(WEEKDAYS)
    for words in OCCASION_KEYWORDS.values():
        for w in words:
            skip.update(w.split())
    skip.update(OCCASION_KEYWORDS)
    if city:
        skip.add(city.lower())
    tokens = re.findall(r"[a-z][a-z'-]*", q)
    kept = [t for t in tokens if t not in skip and len(t) > 1]
    return " ".join(kept) or None


# Extra words that say nothing about *which* clothes ("I love wearing blue colours").
_PREF_FILLER = FILLER_WORDS | {"colour", "colours", "color", "colors", "stuff", "much",
                               "lot", "lots", "kind", "kinds", "type", "types", "style",
                               "styles", "all", "any", "ever", "anymore", "them", "those"}


def _extract_preferences(q: str) -> tuple[str | None, list[str]]:
    """("dislike" | "like", ["yellow", "orange"]) from a preference statement.

    "I don't like yellow and orange" -> ("dislike", ["yellow", "orange"])
    "I love wearing ethnic clothes"  -> ("like", ["ethnic"])
    Dislike phrases are checked first, since "don't like" contains "like".
    """
    for kind, triggers in (("dislike", PREF_TRIGGERS), ("like", LIKE_TRIGGERS)):
        hits = [(q.find(t), t) for t in triggers if t in q]
        if not hits:
            continue
        idx, t = min(hits)
        tail = q[idx + len(t):]
        things = []
        for part in re.split(r",|\band\b|\bor\b|/|&", tail):
            words = [w for w in re.findall(r"[a-z][a-z'-]*", part) if w not in _PREF_FILLER]
            if words:
                things.append(" ".join(words))
        return kind, things
    return None, []


def rules_planner(state: OutfitState) -> dict:
    """The keyword-based reading of state['query']."""
    q_raw = (state.get("query") or "").strip()
    q = q_raw.lower()

    intent = _detect_intent(q)
    updates: dict = {"intent": intent}

    # A preference statement ("I don't like frocks", "I love blue") isn't an
    # outfit request; capture what to remember and let the graph route it to memory.
    if intent == "save_preference":
        kind, things = _extract_preferences(q)
        updates["preference_kind"] = kind
        updates["preferences"] = things
        updates["preference"] = ", ".join(things) or None
        return updates

    updates["occasion"] = _detect_occasion(q)
    updates["city"] = _detect_city(q_raw)
    updates["dates"] = _detect_dates(q)
    itinerary = _detect_itinerary(q, updates["dates"].get("count"))
    if itinerary:
        updates["intent"] = "trip"
        updates["itinerary"] = itinerary
        # The trip lasts at least as long as its last planned day.
        updates["dates"]["count"] = max(updates["dates"].get("count") or 0,
                                        itinerary[-1]["day"])
        if all(d["occasion"] for d in itinerary):
            updates["occasion"] = None          # each day has its own
    updates["search_text"] = _search_text(_strip_itinerary(q), updates["city"])
    return updates


def _strip_itinerary(q: str) -> str:
    """The request without its "day N ..." parts (they describe plans, not clothes)."""
    first = _DAY_MARK.search(q)
    return q[:first.start()] if first else q


# ------------------------------------------------------------------ LLM ---

INTENTS = {"recommend", "trip", "gap", "save_preference"}

LLM_SYSTEM = """You read requests sent to a personal wardrobe stylist app and return JSON only.

Fields:
- intent: "recommend" (what to wear), "trip" (several days or packing), "gap" (what to buy, what is missing), or "save_preference" (the user states a like or dislike, e.g. "I don't like frocks").
- occasion: one of {occasions}, or null. For a trip whose days differ, null here and set per day.
- city: the place the outfit is for, as a city name a weather service can find (e.g. "Goa", "Shimla"), or null.
- dates: {{"relative": one of {relative} or a weekday name, or null; "start_date": "YYYY-MM-DD" or null; "count": number of days or null}}. Today is {today} ({weekday}). Resolve explicit dates ("Dec 20", "the 24th") to start_date. A trip with no length given but a day-by-day plan has count = its last day.
- search_text: only the words describing particular clothes the user wants to wear (colours, garment names, styles), e.g. "red saree". null when no clothes are named.
- preference_kind: "like" or "dislike" (only for save_preference), else null.
- preferences: the liked or disliked things as short lowercase words, e.g. ["frocks"], ["yellow", "orange"]. Empty list otherwise.
- itinerary: for trips with plans per day, [{{"day": 1, "occasion": one of the occasions or null, "activity": "a few words"}}]. Empty list otherwise.

Return exactly these keys."""


def _valid_date(text) -> str | None:
    """An ISO date from yesterday up to 60 days ahead, else None."""
    try:
        d = date.fromisoformat(str(text))
    except ValueError:
        return None
    today = date.today()
    return d.isoformat() if today - timedelta(days=1) <= d <= today + timedelta(days=60) else None


def _clean_occasion(value) -> str | None:
    if not value:
        return None
    v = str(value).lower().strip()
    return v if v in OCCASION_KEYWORDS else _detect_occasion(v)


def _clean_itinerary(raw) -> list[dict]:
    plan: dict[int, dict] = {}
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict):
            continue
        try:
            day = int(d.get("day"))
        except (TypeError, ValueError):
            continue
        if 1 <= day <= 16:
            act = d.get("activity")
            plan[day] = {"day": day, "occasion": _clean_occasion(d.get("occasion")),
                         "activity": str(act).strip()[:60] if act else None}
    return [plan[k] for k in sorted(plan)]


def _clean_dates(raw, fallback: dict) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out: dict = {}
    rel = str(raw.get("relative") or "").lower()
    if rel in RELATIVE_DAYS or rel in WEEKDAYS:
        out["relative"] = rel
    start = _valid_date(raw["start_date"]) if raw.get("start_date") else None
    if start:
        out["start"] = start
        out.pop("relative", None)
    try:
        count = int(raw["count"]) if raw.get("count") is not None else None
    except (TypeError, ValueError):
        count = None
    if count and 1 <= count <= 16:
        out["count"] = count
    return out or dict(fallback or {})


def merge_llm(data: dict, rules: dict) -> dict:
    """Grok's fields, validated; anything missing or invalid comes from the rules."""
    intent = str(data.get("intent") or "").lower()
    intent = intent if intent in INTENTS else rules["intent"]

    if intent == "save_preference":
        kind = str(data.get("preference_kind") or "").lower()
        things = [str(t).strip().lower() for t in data.get("preferences") or []
                  if str(t).strip()]
        if kind not in ("like", "dislike") or not things:
            kind, things = _extract_preferences(rules.get("_q", ""))
        return {"intent": intent, "preference_kind": kind, "preferences": things,
                "preference": ", ".join(things) or None}

    out = {"intent": intent}
    out["occasion"] = (_clean_occasion(data["occasion"]) if "occasion" in data
                       else rules.get("occasion"))
    city = data.get("city")
    out["city"] = city.strip() if isinstance(city, str) and city.strip() else rules.get("city")
    out["dates"] = _clean_dates(data.get("dates"), rules.get("dates") or {})
    st = data.get("search_text")
    out["search_text"] = (st.strip().lower() or None) if isinstance(st, str) else \
        (None if "search_text" in data else rules.get("search_text"))

    itinerary = _clean_itinerary(data.get("itinerary")) or rules.get("itinerary") or []
    if itinerary:
        out["itinerary"] = itinerary
        out["intent"] = "trip"
        out["dates"]["count"] = max(out["dates"].get("count") or 0, itinerary[-1]["day"])
    return out


def llm_planner(state: OutfitState, rules: dict) -> dict | None:
    """Ask Grok; None if the LLM is off or its reply is unusable."""
    today = date.today()
    system = LLM_SYSTEM.format(
        occasions=", ".join(f'"{o}"' for o in OCCASION_KEYWORDS),
        relative=", ".join(f'"{r}"' for r in RELATIVE_DAYS),
        today=today.isoformat(), weekday=today.strftime("%A"),
    )
    data = llm.chat_json(system, state.get("query") or "")
    if not data:
        return None
    return merge_llm(data, {**rules, "_q": (state.get("query") or "").lower()})


def planner(state: OutfitState) -> dict:
    """Read state['query'], return the fields this node fills in."""
    rules = rules_planner(state)
    if llm.enabled():
        merged = llm_planner(state, rules)
        if merged is not None:
            merged["planner_source"] = "llm"
            return merged
    rules["planner_source"] = "rules"
    return rules
