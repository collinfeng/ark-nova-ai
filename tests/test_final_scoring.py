import pytest

import arknova  # noqa: F401  (loads the engine and card data)
from arknova import cards, effects as E, engine, mapinfo, tables as T
from arknova import final_scoring as F
from arknova.hexmap import neighbors

ENDGAME_IDS = [f"{i:03d}" for i in range(1, 12)]
ANIMAL_OR_SPONSOR = sorted(
    c["id"] for c in cards.all_cards().values() if c["type"] in ("animal", "sponsor")
)
LARGE = [c for c in ANIMAL_OR_SPONSOR if cards.is_large(c)]
SMALL = [c for c in ANIMAL_OR_SPONSOR if cards.is_small(c)]
SPONSORS = [c for c in ANIMAL_OR_SPONSOR if cards.card(c)["type"] == "sponsor"]


def new_state(n=2):
    return engine.new_game(n, seed=1)


def give_icon(player, icon, n, pool=ANIMAL_OR_SPONSOR):
    """Append cards to player.zoo_cards until `icon` totals exactly n."""
    remaining = n
    for cid in pool:
        if remaining == 0:
            break
        if cid in player.zoo_cards:
            continue
        k = cards.icons_of(cid).get(icon, 0)
        if k and k <= remaining:
            player.zoo_cards.append(cid)
            remaining -= k
    assert remaining == 0, f"could not reach {n} {icon} icons"


def set_count(player, card_id, n):
    """Make the player's count for a threshold card exactly n."""
    player.zoo_cards = []
    player.tokens = [True] * 7
    player.reputation = 1
    if card_id == "001":
        player.zoo_cards = LARGE[:n]
    elif card_id == "002":
        player.zoo_cards = SMALL[:n]
    elif card_id == "003":
        give_icon(player, "science", n)
    elif card_id == "005":
        player.tokens = [False] * n + [True] * (7 - n)
    elif card_id == "006":
        leave_empty(player.zoo, n)
    elif card_id == "007":
        player.reputation = n
    elif card_id == "008":
        player.zoo_cards = SPONSORS[:n]
    elif card_id == "010":
        give_icon(player, "rock", n)
    elif card_id == "011":
        give_icon(player, "water", n)
    else:
        raise KeyError(card_id)


def leave_empty(zoo, n):
    """Cover building spaces until exactly n plain spaces are empty."""
    plain = sorted(zoo.mapdef.buildable_cells())
    assert n <= len(plain)
    for c in plain[: len(plain) - n]:
        zoo.place("enclosure", 1, frozenset([c]))
    assert len(mapinfo.empty_spaces(zoo)) == n


def run(state, card_id, p=0):
    before = state.players[p].conservation
    E.ENDGAME[card_id](state, p)
    return state.players[p].conservation - before


def test_all_eleven_endgame_cards_are_registered():
    assert all(card_id in E.ENDGAME for card_id in ENDGAME_IDS)


# ---- threshold helper -------------------------------------------------------

@pytest.mark.parametrize("card_id, count, expected", [
    ("001", 0, 0), ("001", 1, 1), ("001", 3, 2), ("001", 4, 3), ("001", 9, 4),
    ("006", 5, 0), ("006", 6, 1), ("006", 23, 3), ("006", 24, 4),
])
def test_threshold_points_helper(card_id, count, expected):
    assert F.threshold_points(card_id, count) == expected


# ---- threshold cards -------------------------------------------------------
# Each case: (count, expected points). Covers below the first threshold, exactly
# at each threshold, between thresholds, and above the last threshold.

THRESHOLD_CASES = {
    "001": [(0, 0), (1, 1), (2, 2), (3, 2), (4, 3), (5, 4), (6, 4)],
    "002": [(2, 0), (3, 1), (5, 1), (6, 2), (7, 2), (8, 3), (9, 3), (10, 4), (11, 4)],
    "003": [(2, 0), (3, 1), (4, 2), (5, 3), (6, 4), (7, 4)],
    "005": [(2, 0), (3, 1), (4, 2), (5, 3), (6, 4), (7, 4)],
    "006": [(5, 0), (6, 1), (11, 1), (12, 2), (17, 2), (18, 3), (23, 3), (24, 4), (30, 4)],
    "007": [(5, 0), (6, 1), (8, 1), (9, 2), (12, 3), (15, 4)],
    "008": [(2, 0), (3, 1), (5, 1), (6, 2), (7, 2), (8, 3), (9, 3), (10, 4), (11, 4)],
    "010": [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4), (8, 4)],
    "011": [(1, 0), (2, 1), (3, 1), (4, 2), (6, 3), (8, 4), (9, 4)],
}

THRESHOLD_PARAMS = [(cid, n, pts) for cid, cases in THRESHOLD_CASES.items() for n, pts in cases]


@pytest.mark.parametrize("card_id, count, expected", THRESHOLD_PARAMS)
def test_threshold_card_points(card_id, count, expected):
    state = new_state()
    player = state.players[0]
    set_count(player, card_id, count)
    assert run(state, card_id) == expected
    assert player.conservation == expected


def test_threshold_cards_are_capped_at_four_points():
    state = new_state()
    player = state.players[0]
    set_count(player, "006", 39)  # far above the top threshold of 24
    assert run(state, "006") == 4


def test_zero_points_does_not_call_score(monkeypatch):
    state = new_state()
    calls = []
    monkeypatch.setattr(E, "score", lambda *a: calls.append(a))
    set_count(state.players[0], "001", 0)
    assert run(state, "001") == 0
    assert calls == []


# ---- 004 Architectural Zoo --------------------------------------------------

def _plain_neighbors(zoo, cells):
    return {n for c in cells for n in neighbors(c) if n in zoo.mapdef.buildable_cells()}


def _cover(zoo, cells):
    for c in sorted(cells):
        if c not in zoo.cell_owner:
            zoo.place("enclosure", 1, frozenset([c]))


def _terrain(zoo, kind):
    return [c for c, cell in zoo.mapdef.cells.items() if cell.terrain == kind]


def _border(zoo):
    return [c for c in zoo.mapdef.buildable_cells() if zoo.mapdef.is_border(c)]


@pytest.mark.parametrize("cover, expected", [
    ("none", 0),
    ("water", 1),
    ("rock", 1),
    # Water and rock neighbours also leave every empty border space next to a building.
    ("water+rock", 3),
    ("border", 1),
    ("full", 4),
])
def test_architectural_zoo_conditions(cover, expected):
    state = new_state()
    zoo = state.players[0].zoo
    water = _terrain(zoo, "water")
    rock = _terrain(zoo, "rock")
    cells = {
        "none": [],
        "water": _plain_neighbors(zoo, water),
        "rock": _plain_neighbors(zoo, rock),
        "water+rock": _plain_neighbors(zoo, water) | _plain_neighbors(zoo, rock),
        "border": _border(zoo),
        "full": zoo.mapdef.buildable_cells(),
    }[cover]
    _cover(zoo, cells)
    assert run(state, "004") == expected


def test_architectural_zoo_empty_map_scores_nothing():
    state = new_state()
    assert run(state, "004") == 0


def test_architectural_zoo_partial_water_connection_is_not_enough():
    state = new_state()
    zoo = state.players[0].zoo
    water = _terrain(zoo, "water")
    # Connect only the first water space: the other water spaces stay unconnected.
    first_neighbors = _plain_neighbors(zoo, [water[0]])
    _cover(zoo, first_neighbors)
    assert mapinfo.connected_terrain(zoo, "water")[1] > 0
    assert run(state, "004") == 0


# ---- 009 Diverse Species Zoo ------------------------------------------------

CATEGORIES = T.ANIMAL_CATEGORIES


def single_category_pool(cat):
    """Cards whose only animal-category icon is `cat`, so one category never adds to another."""
    return [
        cid for cid in ANIMAL_OR_SPONSOR
        if {k for k in cards.icons_of(cid) if k in CATEGORIES} == {cat}
    ]


def set_categories(player, counts):
    """Give the player exactly `counts` icons per animal category and nothing else in those categories."""
    player.zoo_cards = []
    for cat, n in counts.items():
        give_icon(player, cat, n, pool=single_category_pool(cat))
    have = {k: v for k, v in cards.icons(player).items() if k in CATEGORIES}
    assert have == {k: v for k, v in counts.items() if v}, have


def test_diverse_species_more_than_right_neighbour_scores_per_category():
    state = new_state()
    set_categories(state.players[0], {"bird": 2, "predator": 1})
    set_categories(state.players[1], {"bird": 1})
    assert run(state, "009") == 2


def test_diverse_species_equal_or_fewer_scores_nothing():
    state = new_state()
    set_categories(state.players[0], {"bird": 1, "predator": 1})
    set_categories(state.players[1], {"bird": 1, "predator": 2})
    assert run(state, "009") == 0


def test_diverse_species_equal_counts_do_not_score():
    state = new_state()
    set_categories(state.players[0], {"bird": 2})
    set_categories(state.players[1], {"bird": 2})
    assert run(state, "009") == 0


def test_diverse_species_caps_at_four():
    state = new_state()
    # Five categories ahead of an empty right neighbour: 5 would score, the cap gives 4.
    chosen = ["bird", "herbivore", "predator", "primate", "reptile"]
    set_categories(state.players[0], {cat: 1 for cat in chosen})
    assert run(state, "009") == 4


def test_diverse_species_exactly_four_scores_four():
    state = new_state()
    chosen = ["bird", "herbivore", "predator", "reptile"]
    set_categories(state.players[0], {cat: 1 for cat in chosen})
    assert run(state, "009") == 4


def test_diverse_species_compares_with_player_to_the_right():
    # With 3 players, player 0's right-hand neighbour is player 2, not player 1.
    state = new_state(3)
    set_categories(state.players[0], {"bird": 1})
    set_categories(state.players[1], {"bird": 0})
    set_categories(state.players[2], {"bird": 1})
    assert run(state, "009") == 0
    state.players[2].zoo_cards = []
    assert run(state, "009") == 1
