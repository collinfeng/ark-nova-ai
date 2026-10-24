"""Special rules of maps 1-8 (arknova/map_rules.py)."""
import random

import pytest

import arknova  # noqa: F401
from arknova import abilities, cards, effects as E, engine as G, tables as T
from arknova.actions import animals
from arknova.hexmap import neighbors


@pytest.fixture(autouse=True)
def no_animal_abilities(monkeypatch):
    monkeypatch.setattr(abilities, "resolve", lambda state, p, card_id: None)


def new(name, seed=1):
    state = G.new_game(2, seed=seed, map_name=name)
    while state.stack[-1].kind == "setup_keep":
        G.step(state, G.legal_options(state)[0])
    for pl in state.players:
        pl.hand, pl.money, pl.appeal, pl.reputation = [], 100, 0, 4
    return state


SPONSOR = "201"  # any real card id will do for a hand card


def special(state, name):
    return state.map["special"][name]


def free_neighbor(state, cell):
    return next(n for n in neighbors(cell) if n in state.players[0].zoo.mapdef.cells
                and state.players[0].zoo.mapdef.cells[n].terrain == "plain")


def plain_cells_next_to(state, cell, count=1):
    mapdef = state.players[0].zoo.mapdef
    return [n for n in neighbors(cell) if n in mapdef.cells and mapdef.cells[n].terrain == "plain"][:count]


def put(state, p, kind, size, *cells):
    return E.place_building(state, p, kind, size, frozenset(cells))


def simple_animal(size=1):
    """An animal with no play conditions or terrain needs that fits a standard enclosure of `size`."""
    for cid, c in sorted(cards.all_cards().items()):
        enc = c.get("enclosure") or {}
        if (c["type"] == "animal" and not c.get("requirements") and enc.get("standard_size") == size
                and not enc.get("rock") and not enc.get("water") and not enc.get("special")
                and not any(a["keyword"] == "FLOCK_ANIMAL" for a in c["abilities"])):
            return cid
    raise LookupError


def play_animal(state, p, cid):
    state.players[p].hand = [cid]
    while state.stack[-1].kind != "turn":
        state.stack.pop()
    state.stack.append(type(state.stack[-1])("act_animals", p, dict(remaining=1, played=0, phase="play", all_small=True)))
    key = next(o.key for o in G.legal_options(state) if o.key[0] == "play")
    G.step(state, key)


# ---- Map 1 ------------------------------------------------------------------------------

def test_observation_tower_gives_appeal_each_time_adjacent_enclosure_fills():
    state = new("plan1")
    tower = special(state, "observation_tower")[0]
    cell = plain_cells_next_to(state, tower)[0]
    put(state, 0, "enclosure", 1, cell)
    cid = simple_animal(1)
    before = state.players[0].appeal
    play_animal(state, 0, cid)
    assert state.players[0].appeal == before + cards.card(cid)["appeal"] + 2
    # release it, fill again: another 2
    animals.release_animal(state, 0, cid)
    before = state.players[0].appeal
    play_animal(state, 0, cid)
    assert state.players[0].appeal == before + cards.card(cid)["appeal"] + 2


def test_observation_tower_ignores_far_enclosures_and_other_maps():
    state = new("plan1")
    far = next(c for c in state.players[0].zoo.mapdef.buildable_cells()
               if c not in neighbors(special(state, "observation_tower")[0])
               and state.players[0].zoo.mapdef.is_border(c))
    put(state, 0, "enclosure", 1, far)
    cid = simple_animal(1)
    before = state.players[0].appeal
    play_animal(state, 0, cid)
    assert state.players[0].appeal == before + cards.card(cid)["appeal"]
    state = new("plan2")
    cell = plain_cells_next_to(state, special(state, "outdoor_area")[0])[0]
    put(state, 0, "enclosure", 1, cell)
    assert state.players[0].zoo.buildings[0].extra_size == 2


# ---- Map 2 ------------------------------------------------------------------------------

def test_outdoor_area_makes_adjacent_enclosure_two_larger():
    state = new("plan2")
    outdoor = special(state, "outdoor_area")[0]
    near = plain_cells_next_to(state, outdoor)[0]
    b = put(state, 0, "enclosure", 1, near)
    assert b.capacity == 3
    cid = simple_animal(3)
    assert any(h[0] == b.id for h in animals.housings(state.players[0], cid))
    far = next(c for c in state.players[0].zoo.mapdef.buildable_cells()
               if c not in neighbors(outdoor) and c not in state.players[0].zoo.cell_owner
               and any(n in state.players[0].zoo.cell_owner for n in neighbors(c)))
    b2 = put(state, 0, "enclosure", 1, far)
    assert b2.capacity == 1


# ---- Map 4 ------------------------------------------------------------------------------

def harbor_keys(state):
    return [o.key for o in G.legal_options(state) if o.key[0] == "harbor"]


def connect_harbor(state, p):
    put(state, p, "pavilion", 1, special(state, "harbor_connecting_building_space")[0])


def test_harbor_needs_connection():
    state = new("plan4")
    state.players[0].hand = [SPONSOR, "202"]
    assert not harbor_keys(state)


def test_harbor_at_turn_decision_once_per_turn():
    state = new("plan4")
    p = state.stack[-1].player
    connect_harbor(state, p)
    hand = [cid for cid in sorted(cards.all_cards())][:3]
    state.players[p].hand = list(hand)
    state.players[p].money = 10
    assert sorted(harbor_keys(state)) == sorted(("harbor", c) for c in hand)
    frame = state.stack[-1]
    G.step(state, ("harbor", hand[0]))
    assert state.stack[-1] is frame and state.players[p].money == 13
    assert hand[0] not in state.players[p].hand and state.discard[-1] == hand[0]
    assert not harbor_keys(state)
    # next turn of the same player offers it again
    act = next(o for o in G.legal_options(state) if o.key[0] in ("act", "xtoken"))
    G.step(state, act)
    guard = 0
    while state.stack[-1].player != p or state.stack[-1].kind != "turn":
        G.step(state, random.Random(guard).choice(G.legal_options(state, extras=False)))
        guard += 1
        assert guard < 500
    assert state.turn_flags == {} and state.players[p].hand
    assert harbor_keys(state)


def test_harbor_mid_action_and_free_build():
    state = new("plan4")
    p = 0
    connect_harbor(state, p)
    put(state, p, "enclosure", 1, plain_cells_next_to(state, special(state, "harbor_connecting_building_space")[0])[0])
    state.players[p].hand = [simple_animal(1), simple_animal(1)] + [SPONSOR]
    state.stack.append(type(state.stack[-1])("act_animals", p, dict(remaining=2, played=0, phase="play", all_small=True)))
    top = state.stack[-1]
    assert harbor_keys(state)
    G.step(state, ("harbor", SPONSOR))
    assert state.stack[-1] is top and state.players[p].money == 103
    state.turn_flags = {}
    state.stack.append(type(top)("free_build", p, dict(kinds=[("kiosk", 1)])))
    assert harbor_keys(state)


def test_harbor_discard_that_empties_the_hand_ends_a_pending_hand_discard():
    """Cards action: draw, then discard 1. Discarding the only card at the harbour instead must not leave a
    hand-discard decision with nothing to discard (it used to raise "choice frame discard_hand has no options")."""
    state = new("plan4")
    p = 0
    connect_harbor(state, p)
    state.players[p].hand = [SPONSOR]
    state.stack.append(type(state.stack[-1])("discard_hand", p, dict(count=1)))
    below = state.stack[-2]
    assert ("harbor", SPONSOR) in harbor_keys(state)
    G.step(state, ("harbor", SPONSOR))
    assert state.stack[-1] is below and not state.players[p].hand and state.players[p].money == 103


def test_harbor_not_offered_to_opponent_or_in_break():
    state = new("plan4")
    for q in (0, 1):
        connect_harbor(state, q)
        state.players[q].hand = [SPONSOR]
    state.stack.append(type(state.stack[-1])("discard_hand", 1, dict(limit=0)))
    assert not harbor_keys(state)  # opponent's decision during player 0's turn
    state.stack.pop()
    assert harbor_keys(state)
    state.stack.append(type(state.stack[-1])("break", 0, dict(phase=0)))
    state.stack.append(type(state.stack[-1])("discard_hand", 0, dict(limit=0)))
    assert not harbor_keys(state)


def test_harbor_not_on_other_maps():
    for name in ("map0", "plan1", "plan6"):
        state = new(name)
        state.players[0].hand = [SPONSOR]
        assert not harbor_keys(state)


# ---- Map 5 ------------------------------------------------------------------------------

def income(state, p):
    before = state.players[p].money
    for hook in E.BREAK_INCOME_HOOKS:
        hook(state, p)
    return state.players[p].money - before


def test_restaurant_adjacent_cells_match_transcription():
    state = new("plan5")
    adj = sorted(c for c in neighbors(special(state, "park_restaurant")[0]) if c in state.players[0].zoo.mapdef.cells)
    assert adj == sorted(special(state, "restaurant_adjacent_spaces"))


def test_park_restaurant_income_counts_covered_adjacent_spaces():
    state = new("plan5")
    restaurant = special(state, "park_restaurant")[0]
    cells = [c for c in neighbors(restaurant) if state.players[0].zoo.mapdef.cells[c].terrain == "plain"][:3]
    assert income(state, 0) == 0
    put(state, 0, "enclosure", 1, cells[0])
    put(state, 0, "pavilion", 1, cells[1])
    assert income(state, 0) == 2
    state0 = new("map0")
    assert [h for h in E.BREAK_INCOME_HOOKS if h(state0, 0)] == []


def test_restaurant_income_runs_in_break():
    state = new("plan5")
    cells = [c for c in neighbors(special(state, "park_restaurant")[0])
             if state.players[0].zoo.mapdef.cells[c].terrain == "plain"]
    put(state, 0, "pavilion", 1, cells[0])
    while state.stack[-1].kind != "turn":
        state.stack.pop()
    money = state.players[0].money
    base = T.appeal_income(state.players[0].appeal)
    state.stack.append(type(state.stack[-1])("break", 0, dict(phase=2, order=[0])))
    G._settle(state)
    assert state.players[0].money - money == base + 1 + state.players[0].zoo.kiosk_income()


# ---- Map 6 ------------------------------------------------------------------------------

def unmet_one_animal(player):
    """An animal with exactly one condition the player lacks."""
    for cid, c in sorted(cards.all_cards().items()):
        enc = c.get("enclosure") or {}
        if (c["type"] == "animal" and cards.unmet_requirements(player, cid) == 1 and enc.get("standard_size") == 1
                and not enc.get("rock") and not enc.get("water")):
            return cid


def test_research_institute_allows_one_unmet_condition_once_connected():
    state = new("plan6")
    player = state.players[0]
    cid = unmet_one_animal(player)
    assert cid
    put(state, 0, "enclosure", 1, free_neighbor_border(state))
    player.hand = [cid]
    assert not any(m[1] == cid for m in animals._plays(state, 0))
    connect = special(state, "institute_connecting_building_space")[0]
    put(state, 0, "pavilion", 1, connect)
    assert any(m[1] == cid for m in animals._plays(state, 0))
    # two unmet conditions are still too many
    two = next((c for c in sorted(cards.all_cards()) if cards.card(c)["type"] == "animal"
                and cards.unmet_requirements(player, c) == 2), None)
    if two:
        assert not any(m[1] == two for m in animals._plays(state, 0))


def free_neighbor_border(state):
    zoo = state.players[0].zoo
    return next(c for c in sorted(zoo.mapdef.buildable_cells()) if zoo.mapdef.is_border(c) and c not in zoo.cell_owner
                and c != (0, 5))


def test_research_institute_inactive_on_other_maps():
    state = new("plan5")
    player = state.players[0]
    cid = unmet_one_animal(player)
    put(state, 0, "enclosure", 1, free_neighbor_border(state))
    player.hand = [cid]
    assert not any(m[1] == cid for m in animals._plays(state, 0))


# ---- Map 7 ------------------------------------------------------------------------------

def test_ice_cream_income_needs_all_kiosk_spaces_covered():
    state = new("plan7")
    spots = special(state, "kiosk_bonus")
    put(state, 0, "kiosk", 1, spots[0])
    put(state, 0, "kiosk", 1, spots[1])
    assert income(state, 0) == 0
    put(state, 0, "kiosk", 1, spots[2])
    assert income(state, 0) == 3
    put(state, 0, "kiosk", 1, next(c for c in sorted(state.players[0].zoo.mapdef.buildable_cells())
                                    if all(__import__("arknova.hexmap", fromlist=[SPONSOR]).distance(c, k) >= 3 for k in spots)
                                    and c not in state.players[0].zoo.cell_owner))
    assert income(state, 0) == 4
    assert income(state, 1) == 0  # the other zoo has nothing covered


# ---- Map 8 ------------------------------------------------------------------------------

def sponsors_and_animals():
    s = [c for c in sorted(cards.all_cards()) if cards.card(c)["type"] == "sponsor"]
    a = [c for c in sorted(cards.all_cards()) if cards.card(c)["type"] == "animal"]
    return s, a


def test_hollywood_cover_h_takes_first_sponsor_revealed():
    state = new("plan8")
    s, a = sponsors_and_animals()
    state.deck = [s[1], a[0], a[1], s[0], a[2], a[3]]  # top of the deck is the end
    state.discard = []
    hand = len(state.players[0].hand)
    put(state, 0, "pavilion", 1, special(state, "H")[0])
    assert len(state.players[0].hand) == hand + 1
    assert cards.card(state.players[0].hand[-1])["type"] == "sponsor"
    assert state.discard == [a[3], a[2]]
    assert state.deck == [s[1], a[0], a[1]]


def test_hollywood_without_sponsor_in_deck_does_nothing_but_discard():
    state = new("plan8")
    _, a = sponsors_and_animals()
    state.deck, state.discard = [a[0], a[1]], []
    put(state, 0, "pavilion", 1, special(state, "H")[0])
    assert state.players[0].hand == [] and state.deck == []


def test_hollywood_all_three_make_sponsors_one_level_cheaper():
    state = new("plan8")
    s, _ = sponsors_and_animals()
    state.deck = []
    state.discard = []
    sponsor = next(c for c in s if cards.card(c)["level"] >= 2)
    level = cards.card(sponsor)["level"]
    from arknova import sponsor_rules as SR
    hs = special(state, "H")
    for h in hs[:2]:
        put(state, 0, "pavilion", 1, h)
    assert SR.sponsor_level(state, 0, sponsor) == level
    put(state, 0, "pavilion", 1, hs[2])
    assert SR.sponsor_level(state, 0, sponsor) == level - 1
    assert SR.sponsor_level(state, 1, sponsor) == level
    other = new("plan7")
    assert SR.sponsor_level(other, 0, sponsor) == level


def test_hollywood_discount_applies_to_money_cost_and_budget():
    state = new("plan8")
    s, _ = sponsors_and_animals()
    state.deck = []
    sponsor = "223"  # level 3, no conditions, no building
    for h in special(state, "H"):
        put(state, 0, "pavilion", 1, h)
    state.players[0].hand = [sponsor]
    state.players[0].money = 2
    from arknova.actions import sponsors
    assert sponsors._playable(state, 0, 2)  # level 3 -> 2: strength 2 and 2 money suffice
    other = new("plan7")
    other.players[0].hand, other.players[0].money = [sponsor], 2
    assert not sponsors._playable(other, 0, 2)


def test_h_bonus_is_not_a_placement_bonus_for_archaeologist():
    state = new("plan8")
    h = special(state, "H")[0]
    assert state.players[0].zoo.mapdef.cells[h].bonus is None


# ---- Map 0 and others ---------------------------------------------------------------------

def test_map0_is_unaffected():
    state = new("map0")
    b = put(state, 0, "enclosure", 1, (0, 0))
    assert b.extra_size == 0 and b.capacity == 1
    state.players[0].hand = [SPONSOR]
    assert not harbor_keys(state)
    assert income(state, 0) == 0


@pytest.mark.parametrize("name", ["plan1", "plan2", "plan4", "plan5", "plan6", "plan7", "plan8"])
def test_random_playouts_with_rules_finish(name):
    for seed in (3, 4):
        state, rng, steps = G.new_game(2, seed=seed, map_name=name), random.Random(seed), 0
        while not state.over and steps < 8000:
            options = G.legal_options(state)
            G.step(state, rng.choice(options))
            steps += 1
        assert state.over
