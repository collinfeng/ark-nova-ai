"""Animal abilities. Each keyword is one function, resolved when the animal is played.

Register with `@ability("KEYWORD", ...)`; the function gets (state, player_idx, card_id, value)
where value is the number or name printed with the keyword (None if there is none).
Effects worded "after finishing" must queue their choice with `after_finishing(...)` /
`offer_extra_action(...)` instead of pushing a frame directly.
"""
from . import cards
from .state import under

ABILITIES = {}  # keyword -> fn(state, player_idx, card_id, value)
PASSIVE = {"FLOCK_ANIMAL"}  # handled where the rule applies (enclosure choice), nothing to resolve


def ability(*keywords):
    def register(fn):
        for keyword in keywords:
            ABILITIES[keyword] = fn
        return fn
    return register


def after_finishing(state, kind, player, **data):
    """Queue a frame for after the current action (resolved once its action card has moved)."""
    state.turn["after"].append((kind, player, data))


def resolve(state, p, card_id):
    """Resolve the abilities of an animal that was just played, in printed order."""
    for a in reversed(cards.card(card_id)["abilities"]):  # frames stack, so push the last one first
        if a["keyword"] in PASSIVE:
            continue
        fn = ABILITIES.get(a["keyword"])
        if fn is not None:
            under(state, ("ability", card_id, a["keyword"]), fn, state, p, card_id, a["value"])


def missing_keywords():
    used = {a["keyword"] for c in cards.all_cards().values() for a in c.get("abilities", [])}
    return sorted(used - set(ABILITIES) - PASSIVE)
