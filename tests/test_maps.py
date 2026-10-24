import random

import pytest

import arknova  # noqa: F401
from arknova import engine as G, maps, tables as T
from arknova.hexmap import MAP0

NAMES = maps.available()


def test_all_base_maps_are_registered():
    assert {f"plan{i}" for i in range(1, 9)} | {"plana"} <= set(NAMES)
    for name in NAMES:
        assert name in G.MAP_DEFS and name in T.MAPS


@pytest.mark.parametrize("name", NAMES)
def test_map_shares_map0_grid_and_has_full_side_panels(name):
    mapdef, board = G.MAP_DEFS[name], T.MAPS[name]
    assert set(mapdef.cells) == set(MAP0.cells)
    assert len(board["partner_zoo_slots"]) == 4 and len(board["university_slots"]) == 3
    assert len(board["tokens"]) == 7
    for cell in mapdef.cells.values():
        assert cell.bonus is None or cell.bonus in T.PLACEMENT_BONUS


@pytest.mark.parametrize("name", NAMES)
def test_random_games_on_every_map_finish(name):
    for seed in (1, 2):
        state, rng, steps = G.new_game(2, seed=seed, map_name=name), random.Random(seed), 0
        while not state.over and steps < 6000:
            G.step(state, rng.choice(G.legal_options(state)))
            steps += 1
        assert state.over, f"{name} seed {seed} did not finish in {steps} decisions"


def test_map_a_starts_with_its_kiosk_and_enclosure():
    state = G.new_game(2, seed=0, map_name="plana")
    for player in state.players:
        kinds = sorted((b.kind, b.size) for b in player.zoo.buildings)
        assert kinds == [("enclosure", 3), ("kiosk", 1)]


def test_map3_build2_spaces_also_pay_money():
    cells = [c for c in G.MAP_DEFS["plan3"].cells.values() if c.build2_only and c.bonus == "money2"]
    assert len(cells) == 3


def test_effect_formats_are_normalised():
    assert maps.parse_effects("none") == []
    assert maps.parse_effects("upgrade1") == [("upgrade", 1)]
    assert maps.parse_effects(["enclosure_size2"]) == [("enclosure", 2)]
    assert maps.parse_effects(["card", 1]) == [("card", 1)]
    assert maps.parse_effects([["conservation", 2]]) == [("conservation", 2)]
    assert maps.parse_effects([{"worker": 1}]) == [("worker", 1)]
    assert maps.parse_effects(["animal_silhouette_2_UNKNOWN"]) == []
    with pytest.raises(ValueError):
        maps.parse_effects("mystery7")


def test_new_bonus_kinds_open_the_right_decisions():
    from arknova import effects as E
    state = G.new_game(2, seed=3, map_name="plan5")
    while state.stack[-1].kind == "setup_keep":
        G.step(state, G.legal_options(state)[0])
    p = state.stack[-1].player
    E.gain(state, p, "special_enclosure", 1)
    kinds = {o.key[1] for o in G.legal_options(state) if o.key[0] == "place"}
    assert kinds == {"reptile_house", "aviary"}
    state.stack.pop()
    E.gain(state, p, "kiosk", 1)
    assert {o.key[1] for o in G.legal_options(state) if o.key[0] == "place"} == {"kiosk"}
