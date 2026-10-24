import pytest

import arknova.actions.animals as A
from arknova import cards, effects as E, engine, tables as T
from arknova.state import Option

PLAIN_STD = lambda c: (c["type"] == "animal" and not c["requirements"]
                       and not c["enclosure"]["special"] and c["enclosure"]["standard_size"] is not None
                       and c["enclosure"]["rock"] == 0 and c["enclosure"]["water"] == 0)


def find(pred, n=1):
    found = sorted((c for c in cards.all_cards().values() if pred(c)), key=lambda c: c["id"])
    assert len(found) >= n
    return [c["id"] for c in found[:n]] if n > 1 else found[0]["id"]


def new(seed=1):
    s = engine.new_game(2, seed=seed)
    while s.stack[-1].kind == "setup_keep":
        engine.step(s, engine.legal_options(s)[0])
    p = s.players[0]
    p.hand, p.money, p.reputation, p.appeal = [], 100, 1, 0
    p.slots = ["animals", "cards", "build", "association", "sponsors"]
    s.display = list(s.display)
    return s, p


def build(p, size, rock=0, water=0):
    options = p.zoo.legal_placements("enclosure", size)
    if rock or water:
        options = [c for c in options if p.zoo.adjacent_terrain(c, "rock") >= rock
                   and p.zoo.adjacent_terrain(c, "water") >= water]
    return p.zoo.place("enclosure", size, options[0])[0]


def build_exact(p, size, rock, water):
    for c in p.zoo.legal_placements("enclosure", size):
        if p.zoo.adjacent_terrain(c, "rock") == rock and p.zoo.adjacent_terrain(c, "water") == water:
            return p.zoo.place("enclosure", size, c)[0]
    raise AssertionError("no placement")


def keys(s):
    return [o.key for o in engine.legal_options(s)]


def act(s, x=0):
    engine.step(s, ("act", "animals", x))


def with_slot(p, n):
    p.slots.remove("animals")
    p.slots.insert(n - 1, "animals")


@pytest.mark.parametrize("upgraded,table", [(False, [0, 1, 1, 1, 2]), (True, [1, 1, 2, 2, 2])])
def test_strength_table(upgraded, table):
    cid = find(PLAIN_STD)
    size = cards.card(cid)["enclosure"]["standard_size"]
    for strength in range(1, 8):
        s, p = new()
        p.hand = [cid, find(lambda c: PLAIN_STD(c) and c["id"] != cid)]
        build(p, 5)
        build(p, 5)
        if upgraded:
            p.upgraded.add("animals")
        feas = A.feasible(s, 0, strength)
        assert feas == (table[min(strength, 5) - 1] > 0)


def test_strength_one_side_one_not_offered_in_turn():
    s, p = new()
    cid = find(PLAIN_STD)
    p.hand = [cid]
    build(p, 5)
    assert ("act", "animals", 0) not in keys(s)  # animals sits in slot 1, strength 1, side I
    p.xtokens = 1
    assert ("act", "animals", 1) in keys(s)


def test_cost_and_partner_discount():
    cid = find(lambda c: c["type"] == "animal" and len(c["continents"]) == 1 and not c["requirements"]
               and not c["enclosure"]["special"] and c["enclosure"]["rock"] == 0 and c["enclosure"]["water"] == 0
               and c["cost"] >= 6)
    c = cards.card(cid)
    cont = c["continents"][0]
    s, p = new()
    p.hand = [cid]
    build(p, 5)
    with_slot(p, 2)
    p.money = c["cost"] - 1
    assert not A.feasible(s, 0, 2)
    p.partner_zoos = [cont]
    p.money = c["cost"] - 3
    assert A.feasible(s, 0, 2)
    engine.step(s, ("act", "animals", 0))
    assert keys(s) == [("play", cid, 0)] or keys(s)[0][:2] == ("play", cid)
    engine.step(s, keys(s)[0])
    assert p.money == 0
    assert cid not in p.hand and cid in p.zoo_cards  # its ability may have drawn cards


def test_unaffordable_and_unmet_not_offered():
    cheap = find(lambda c: PLAIN_STD(c) and c["cost"] <= 10)
    pricey = find(lambda c: PLAIN_STD(c) and c["cost"] >= 20)
    unmet = find(lambda c: c["type"] == "animal" and c["requirements"] == ["predator", "predator", "predator"])
    s, p = new()
    with_slot(p, 2)
    p.hand = [cheap, pricey, unmet]
    build(p, 5)
    p.money = 12
    act(s)
    ks = keys(s)
    assert [k[1] for k in ks] == [cheap]
    assert cards.unmet_requirements(p, unmet) > 0


def test_non_animal_in_hand_ignored():
    sponsor = find(lambda c: c["type"] == "sponsor")
    s, p = new()
    p.hand = [sponsor]
    build(p, 5)
    assert not A.feasible(s, 0, 2)


def test_enclosure_size_and_terrain():
    need_rock = find(lambda c: c["type"] == "animal" and not c["requirements"] and not c["enclosure"]["special"] and c["enclosure"]["standard_size"] == 2
                     and c["enclosure"]["rock"] == 1 and c["enclosure"]["water"] == 0)
    s, p = new()
    p.hand = [need_rock]
    small = build_exact(p, 1, 0, 0)
    assert not A.housings(p, need_rock)  # too small
    p.zoo.buildings.clear(); p.zoo.cell_owner.clear()
    nr = build_exact(p, 2, 0, 0) if p.zoo.legal_placements("enclosure", 2) and any(
        p.zoo.adjacent_terrain(c, "rock") == 0 for c in p.zoo.legal_placements("enclosure", 2)) else None
    assert nr is not None and not A.housings(p, need_rock)  # no rock adjacent
    p.zoo.buildings.clear(); p.zoo.cell_owner.clear()
    good = build(p, 3, rock=1)
    assert A.housings(p, need_rock) == [(good.id, 0)]
    good.occupied = True
    assert not A.housings(p, need_rock)


def test_water_requirement():
    cid = find(lambda c: c["type"] == "animal" and not c["enclosure"]["special"]
               and c["enclosure"]["standard_size"] == 2 and c["enclosure"]["water"] == 1
               and c["enclosure"]["rock"] == 0)
    s, p = new()
    b = build(p, 2, water=1)
    assert A.housings(p, cid) == [(b.id, 0)]
    p.zoo.buildings.clear(); p.zoo.cell_owner.clear()
    build_exact(p, 2, 0, 0)
    assert A.housings(p, cid) == []


def test_special_enclosures_capacity():
    reptile = find(lambda c: c["type"] == "animal" and c["enclosure"]["special"]
                   and c["enclosure"]["special"][0]["type"] == "Reptile House"
                   and c["enclosure"]["special"][0]["size"] == 2 and c["enclosure"]["standard_size"] == 3
                   and c["enclosure"]["rock"] == 0 and c["enclosure"]["water"] == 0 and not c["requirements"])
    s, p = new()
    p.hand = [reptile]
    with_slot(p, 3)
    assert not A.housings(p, reptile)
    rh, _ = p.zoo.place("reptile_house", 5, p.zoo.legal_placements("reptile_house", 5)[0])
    assert A.housings(p, reptile) == [(rh.id, 2)]
    rh.used = 4
    assert not A.housings(p, reptile)
    rh.used = 3
    assert A.housings(p, reptile) == [(rh.id, 2)]
    act(s)
    engine.step(s, ("play", reptile, rh.id))
    assert rh.used == 5 and p.housing[reptile] == (rh.id, 2)


def test_aviary():
    bird = find(lambda c: c["type"] == "animal" and c["enclosure"]["special"]
                and c["enclosure"]["special"][0]["type"] == "Large Bird Aviary" and not c["requirements"]
                and c["enclosure"]["rock"] == 0 and c["enclosure"]["water"] == 0)
    s, p = new()
    av, _ = p.zoo.place("aviary", 5, p.zoo.legal_placements("aviary", 5)[0])
    size = cards.card(bird)["enclosure"]["special"][0]["size"]
    assert A.housings(p, bird) == [(av.id, size)]


def test_petting_zoo_animals():
    pet = find(lambda c: c["type"] == "animal" and c["enclosure"]["standard_size"] is None)
    s, p = new()
    p.hand = [pet]
    build(p, 5)
    assert not A.housings(p, pet)  # standard enclosures never house pets
    pz, _ = p.zoo.place("petting_zoo", 3, p.zoo.legal_placements("petting_zoo", 3)[0])
    with_slot(p, 2)
    act(s)
    k = keys(s)
    assert k == [("play", pet, pz.id)]
    engine.step(s, k[0])
    assert pz.used == cards.card(pet)["enclosure"]["special"][0]["size"]
    assert not any(b.occupied for b in p.zoo.buildings if b.kind == "enclosure")


def test_zero_size_special_does_not_occupy():
    cid = find(lambda c: c["type"] == "animal" and c["enclosure"]["special"]
               and c["enclosure"]["special"][0]["size"] == 0 and c["enclosure"]["rock"] == 0
               and c["enclosure"]["water"] == 0 and not c["requirements"])
    s, p = new()
    rh, _ = p.zoo.place("reptile_house", 5, p.zoo.legal_placements("reptile_house", 5)[0])
    assert A.housings(p, cid) == [(rh.id, 0)]
    p.hand = [cid]
    with_slot(p, 2)
    act(s)
    engine.step(s, keys(s)[0])
    assert rh.used == 0 and p.housing[cid] == (rh.id, 0)
    A.release_animal(s, 0, cid)
    assert rh.used == 0


def test_display_play_side_two_folder_cost_and_range():
    cid = find(PLAIN_STD)
    c = cards.card(cid)
    s, p = new()
    p.upgraded.add("animals")
    with_slot(p, 2)
    build(p, 5)
    s.display = [None, None, None, cid, None, None]
    p.reputation = 3  # folders 1-2
    assert not A.feasible(s, 0, 2)
    p.reputation = 5  # folders 1-3? check via table
    folders = T.reputation_folders(5)
    assert folders == 3
    assert not A.feasible(s, 0, 2)
    p.reputation = 7  # four folders
    assert T.reputation_folders(7) == 4
    p.money = c["cost"] + 3
    assert not A.feasible(s, 0, 2)
    p.money = c["cost"] + 4
    act(s)
    assert keys(s) == [("play_display", 3, 0)]
    engine.step(s, keys(s)[0])
    assert p.money == 0
    assert cid not in s.display and cid in p.zoo_cards


def test_display_not_available_on_side_one():
    cid = find(PLAIN_STD)
    s, p = new()
    build(p, 5)
    s.display = [cid] + [None] * 5
    assert not A.feasible(s, 0, 2)


def test_reputation_at_strength_five_side_two():
    cid = find(PLAIN_STD)
    s, p = new()
    p.upgraded.add("animals")
    p.hand = [cid]
    build(p, 5)
    with_slot(p, 5)
    p.reputation = 1
    act(s)
    assert p.reputation == 2  # before any card is chosen
    assert s.stack[-1].kind == "act_animals"
    # strength 4: no bonus
    s2, p2 = new()
    p2.upgraded.add("animals")
    p2.hand = [cid]
    build(p2, 5)
    with_slot(p2, 4)
    act(s2)
    assert p2.reputation == 1


def test_reputation_bonus_choice_resolves_before_frame():
    cid = find(PLAIN_STD)
    s, p = new()
    p.upgraded.add("animals")
    p.hand = [cid]
    build(p, 5)
    with_slot(p, 5)
    p.reputation = 1
    # reputation 2 gives a bonus per T.REPUTATION_BONUS, if any; frame must still be reachable
    act(s)
    for _ in range(5):
        if s.stack[-1].kind == "act_animals":
            break
        engine.step(s, engine.legal_options(s)[0])
    assert s.stack[-1].kind == "act_animals"


def test_two_animals_and_done():
    a, b = find(PLAIN_STD, 2)
    s, p = new()
    p.upgraded.add("animals")
    p.hand = [a, b]
    build(p, 5)
    build(p, 5)
    with_slot(p, 3)  # side II strength 3 -> 2 animals
    act(s)
    assert ("done",) not in keys(s)
    first = keys(s)[0]
    engine.step(s, first)
    assert s.stack[-1].kind == "act_animals"
    ks = keys(s)
    assert ("done",) in ks and len(ks) >= 2
    engine.step(s, ("done",))
    assert len(p.zoo_cards) == 1 and s.current == 1 and p.slots[0] == "animals"


def test_second_animal_auto_ends_and_slot_moves():
    a, b = find(PLAIN_STD, 2)
    s, p = new()
    p.upgraded.add("animals")
    p.hand = [a, b]
    build(p, 5)
    build(p, 5)
    with_slot(p, 3)
    act(s)
    engine.step(s, keys(s)[0])
    engine.step(s, [k for k in keys(s) if k != ("done",)][0])
    assert len(p.zoo_cards) == 2 and p.slots[0] == "animals"
    assert s.current == 1 and s.stack[-1].kind == "turn" and s.stack[-1].player == 1


def test_frame_ends_when_nothing_possible():
    a, b = find(PLAIN_STD, 2)
    s, p = new()
    p.upgraded.add("animals")
    p.hand = [a, b]
    build(p, 5)  # only one enclosure
    with_slot(p, 3)
    act(s)
    engine.step(s, keys(s)[0])
    assert s.current == 1  # frame closed automatically, turn passed


def test_side_one_single_animal_ends_turn_and_moves_slot():
    a = find(PLAIN_STD)
    s, p = new()
    p.hand = [a]
    build(p, 5)
    with_slot(p, 3)
    assert p.slots.index("animals") == 2
    act(s)
    engine.step(s, keys(s)[0])
    assert p.slots[0] == "animals"
    assert s.current == 1


def _play_and_settle(s, cid, **kw):
    played = []
    A.ON_ANIMAL_PLAYED.append(lambda st, who, card: played.append((who, card)))
    try:
        act(s)
        engine.step(s, keys(s)[0])
        while s.stack[-1].kind != "turn" and not s.over:
            engine.step(s, engine.legal_options(s)[0])
    finally:
        A.ON_ANIMAL_PLAYED.pop()
    return played


def test_gains_conservation_and_hook():
    cid = "440"  # appeal 4, conservation 1, needs rock 1
    s, p = new()
    p.hand = [cid]
    build(p, 3, rock=1)
    with_slot(p, 2)
    played = _play_and_settle(s, cid)
    assert played == [(0, cid)]
    assert p.appeal == 4 and p.conservation == 1


def test_gains_reputation():
    cid = "435"  # appeal 5, reputation 1
    s, p = new()
    p.hand = [cid]
    build(p, 2)
    with_slot(p, 2)
    p.reputation = 1
    _play_and_settle(s, cid)
    assert p.appeal == 5 and p.reputation == 2


def test_simple_gain_values():
    cid = find(lambda c: PLAIN_STD(c) and c["appeal"] >= 3)
    s, p = new()
    p.hand = [cid]
    build(p, 5)
    with_slot(p, 2)
    act(s)
    engine.step(s, keys(s)[0])
    assert p.appeal == cards.card(cid)["appeal"]


def test_release_animal_standard():
    cid = find(lambda c: PLAIN_STD(c) and c["appeal"] >= 3)
    s, p = new()
    b = build(p, 5)
    p.hand = [cid]
    with_slot(p, 2)
    act(s)
    engine.step(s, keys(s)[0])
    assert b.occupied
    appeal = p.appeal
    A.release_animal(s, 0, cid)
    assert not b.occupied and cid not in p.zoo_cards and cid not in p.housing
    assert p.appeal == max(0, appeal - cards.card(cid)["appeal"])
    assert s.discard[-1] == cid


def test_release_animal_special_and_floor():
    cid = find(lambda c: c["type"] == "animal" and c["enclosure"]["special"]
               and c["enclosure"]["special"][0]["type"] == "Reptile House"
               and c["enclosure"]["special"][0]["size"] >= 1 and c["appeal"] >= 2)
    s, p = new()
    rh, _ = p.zoo.place("reptile_house", 5, p.zoo.legal_placements("reptile_house", 5)[0])
    size = cards.card(cid)["enclosure"]["special"][0]["size"]
    rh.used = size
    p.zoo_cards.append(cid)
    p.housing[cid] = (rh.id, size)
    p.appeal = 0
    A.release_animal(s, 0, cid)
    assert rh.used == 0 and p.appeal == 0
