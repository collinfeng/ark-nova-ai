"""Final scoring (conservation points) for the 11 base-game endgame cards "001" to "011".

Each card registers one function in `effects.ENDGAME`. The function adds its points
through `effects.score`, and never more than MAX_POINTS per card.

Importing this module registers the cards (`arknova/__init__.py` does).
"""
from . import cards, effects as E, mapinfo, tables as T

MAX_POINTS = 4


def threshold_points(card_id, count):
    """Conservation points for `count` on a threshold card.

    The card's `scoring` list is `{"threshold": t, "conservation": c}` entries. The
    result is the `conservation` of the highest threshold that `count` reaches, or 0
    when `count` is below the first threshold.
    """
    points = 0
    for tier in sorted(cards.card(card_id)["scoring"], key=lambda t: t["threshold"]):
        if count >= tier["threshold"]:
            points = tier["conservation"]
    return min(points, MAX_POINTS)


def _award(state, p, points):
    if points > 0:
        E.score(state, p, "conservation", min(points, MAX_POINTS))


def _threshold(state, p, card_id, count):
    _award(state, p, threshold_points(card_id, count))


@E.register(E.ENDGAME, "001")
def large_animal_zoo(state, p):
    player = state.players[p]
    large = sum(1 for c in player.zoo_cards if cards.is_large(c))
    _threshold(state, p, "001", large)


@E.register(E.ENDGAME, "002")
def small_animal_zoo(state, p):
    player = state.players[p]
    small = sum(1 for c in player.zoo_cards if cards.is_small(c))
    _threshold(state, p, "002", small)


@E.register(E.ENDGAME, "003")
def research_zoo(state, p):
    player = state.players[p]
    _threshold(state, p, "003", cards.icons(player).get("science", 0))


@E.register(E.ENDGAME, "004")
def architectural_zoo(state, p):
    zoo = state.players[p].zoo
    conditions = [
        mapinfo.connected_terrain(zoo, "water")[1] == 0,
        mapinfo.connected_terrain(zoo, "rock")[1] == 0,
        mapinfo.all_border_connected(zoo),
        zoo.is_fully_covered(),
    ]
    _award(state, p, sum(conditions))


@E.register(E.ENDGAME, "005")
def conservation_zoo(state, p):
    _threshold(state, p, "005", state.players[p].projects_supported)


@E.register(E.ENDGAME, "006")
def naturalists_zoo(state, p):
    _threshold(state, p, "006", len(mapinfo.empty_spaces(state.players[p].zoo)))


@E.register(E.ENDGAME, "007")
def favorite_zoo(state, p):
    _threshold(state, p, "007", state.players[p].reputation)


@E.register(E.ENDGAME, "008")
def sponsored_zoo(state, p):
    player = state.players[p]
    sponsors = sum(1 for c in player.zoo_cards if cards.card(c)["type"] == "sponsor")
    _threshold(state, p, "008", sponsors)


@E.register(E.ENDGAME, "009")
def diverse_species_zoo(state, p):
    player = state.players[p]
    right = state.players[(p - 1) % state.n]
    mine = cards.icons(player)
    theirs = cards.icons(right)
    more = sum(1 for cat in T.ANIMAL_CATEGORIES if mine.get(cat, 0) > theirs.get(cat, 0))
    _award(state, p, min(more, MAX_POINTS))


@E.register(E.ENDGAME, "010")
def climbing_park(state, p):
    _threshold(state, p, "010", cards.icons(state.players[p]).get("rock", 0))


@E.register(E.ENDGAME, "011")
def aquatic_park(state, p):
    _threshold(state, p, "011", cards.icons(state.players[p]).get("water", 0))
