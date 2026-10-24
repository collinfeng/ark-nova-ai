"""Card data access. Game state stores card ids only; card facts are looked up here."""
import json
from functools import lru_cache
from pathlib import Path

from .tables import CONTINENTS

DATA = Path(__file__).resolve().parent.parent / "data" / "cards.json"


@lru_cache(maxsize=None)
def all_cards():
    """Base-game cards by id."""
    cards = json.loads(DATA.read_text())["cards"]
    return {c["id"]: c for c in cards if c["base_game"]}


def card(card_id):
    return all_cards()[card_id]


def ids_of(card_type, **where):
    return sorted(c["id"] for c in all_cards().values()
                  if c["type"] == card_type and all(c.get(k) == v for k, v in where.items()))


def zoo_deck_ids():
    """Animals, sponsors and non-base conservation projects: the zoo card deck."""
    return sorted(c["id"] for c in all_cards().values()
                  if c["type"] in ("animal", "sponsor")
                  or (c["type"] == "project" and c["category"] != "base"))


def icons_of(card_id):
    """Icons one card adds to a zoo: its tags plus its rock/water requirement icons."""
    c = card(card_id)
    counts = {}
    for tag in c.get("tags", []):
        counts[tag] = counts.get(tag, 0) + 1
    enclosure = c.get("enclosure") or {}
    for terrain in ("rock", "water"):
        n = enclosure.get(terrain)
        if isinstance(n, int) and n and terrain not in c.get("tags", []):
            counts[terrain] = counts.get(terrain, 0) + n
    return counts


def is_small(card_id):
    return card(card_id)["type"] == "animal" and card(card_id)["size"] <= 2


def is_large(card_id):
    return card(card_id)["type"] == "animal" and card(card_id)["size"] >= 4


def icons(player):
    """Icon counts in a zoo: card tags (incl. rock/water requirements), partner zoos, universities."""
    key = (tuple(player.zoo_cards), tuple(player.partner_zoos), tuple(player.universities))
    cached = getattr(player, "_icons", None)
    if cached is not None and cached[0] == key:
        return dict(cached[1])
    counts = {}

    def add(icon, n=1):
        counts[icon] = counts.get(icon, 0) + n

    for cid in player.zoo_cards:
        c = card(cid)
        for tag in c.get("tags", []):
            add(tag)
        enclosure = c.get("enclosure") or {}
        for terrain in ("rock", "water"):
            n = enclosure.get(terrain)
            if isinstance(n, int) and n and terrain not in c.get("tags", []):
                add(terrain, n)
    for continent in player.partner_zoos:
        add(continent)
    for university in player.universities:
        add("science", {"science2": 2, "science_rep": 1}.get(university, 0))
    counts = {k: v for k, v in counts.items() if v}
    player._icons = (key, counts)
    return dict(counts)


def animal_continents(card_id):
    return [t for t in card(card_id).get("continents", []) if t in CONTINENTS]


def unmet_requirements(player, card_id):
    """Number of play conditions on the card's left side that the player does not meet."""
    c = card(card_id)
    have = icons(player)
    needs = {}
    for r in c.get("requirements", []):
        needs[r] = needs.get(r, 0) + 1
    unmet = 0
    for need, n in needs.items():
        if need in ("animalsII", "sponsorsII"):
            ok = need[:-2] in player.upgraded
        elif need == "Partner Zoo":
            continents = animal_continents(card_id)
            owned = [z for z in player.partner_zoos if z in continents] if continents else player.partner_zoos
            ok = len(owned) >= (1 if continents else n)
        elif need == "reputation":
            ok = player.reputation >= c["min_reputation"]
        elif need == "appeal":
            ok = player.appeal <= c["max_appeal"]
        else:
            ok = have.get(need, 0) >= n
        unmet += 0 if ok else 1
    return unmet
