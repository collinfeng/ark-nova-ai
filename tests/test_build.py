import arknova.actions.build as B
from arknova import engine, tables as T


def new(strength, upgraded=False, money=25, seed=1, p=0):
    s = engine.new_game(2, seed=seed)
    while s.stack[-1].kind == "setup_keep":
        engine.step(s, engine.legal_options(s)[0])
    pl = s.players[p]
    pl.slots.remove("build")
    pl.slots.insert(strength - 1, "build")
    pl.money = money
    if upgraded:
        pl.upgraded.add("build")
    return s


def act(s):
    opt = next(o for o in engine.legal_options(s) if o.key[:2] == ("act", "build"))
    engine.step(s, opt)


def builds(s, kind=None, size=None):
    return [o for o in engine.legal_options(s) if o.key[0] == "build"
            and (kind is None or o.key[1] == kind) and (size is None or o.key[2] == size)]


def test_side1_single_building_ends_frame():
    s = new(3)
    act(s)
    assert s.stack[-1].kind == "act_build"
    opt = builds(s, "enclosure", 3)[0]
    engine.step(s, opt)
    assert s.stack[-1].kind != "act_build"
    assert len(s.players[0].zoo.buildings) == 1


def test_side1_no_done_option():
    s = new(2)
    act(s)
    assert all(o.key[0] == "build" for o in engine.legal_options(s))


def test_size_limit_by_strength():
    s = new(2)
    act(s)
    assert all(o.key[2] <= 2 for o in builds(s))
    assert not builds(s, "petting_zoo")
    assert builds(s, "enclosure", 2)


def test_strength_above_five():
    s = new(5, upgraded=True)
    s.players[0].xtokens = 2
    opt = next(o for o in engine.legal_options(s) if o.key == ("act", "build", 2))
    engine.step(s, opt)
    assert s.stack[-1].data["budget"] == 7


def test_cannot_afford():
    s = new(5, money=7)
    act(s)
    assert all(o.key[2] <= 3 for o in builds(s))
    assert builds(s, "enclosure", 3) and not builds(s, "enclosure", 4)


def test_cost_paid():
    s = new(4)
    act(s)
    opt = next(o for o in builds(s, "enclosure", 4))
    engine.step(s, opt)
    assert s.players[0].money == 25 - 8


def test_feasible_false_when_broke():
    s = new(5, money=1)
    assert not B.feasible(s, 0, 5)
    assert not any(o.key[:2] == ("act", "build") for o in engine.legal_options(s))
    s.players[0].money = 2
    assert B.feasible(s, 0, 5)
    assert not B.feasible(s, 0, 0)


def test_first_building_on_border_and_bonus_pays():
    s = new(1)
    act(s)
    mapdef = s.players[0].zoo.mapdef
    for o in builds(s):
        assert any(mapdef.is_border(c) for c in o.key[3])
    bonus_cell = next(c for c, v in mapdef.cells.items() if v.bonus == "money5" and mapdef.is_border(c))
    opt = next(o for o in builds(s, "kiosk") if o.key[3] == (bonus_cell,))
    engine.step(s, opt)
    assert s.players[0].money == 25 - 2 + 5
    assert s.stack[-1].kind != "act_build"


def test_pavilion_appeal():
    s = new(1)
    before = s.players[0].appeal
    act(s)
    engine.step(s, builds(s, "pavilion")[0])
    assert s.players[0].appeal == before + 1


def test_side2_multiple_different_and_identical_ban():
    s = new(5, upgraded=True)
    act(s)
    engine.step(s, builds(s, "enclosure", 2)[0])
    top = s.stack[-1]
    assert top.kind == "act_build" and top.data["budget"] == 3
    assert ("done",) in [o.key for o in engine.legal_options(s)]
    assert not builds(s, "enclosure", 2)           # identical
    assert builds(s, "enclosure", 3) and builds(s, "enclosure", 1)
    engine.step(s, builds(s, "enclosure", 3)[0])
    assert s.stack[-1].kind != "act_build"
    assert len(s.players[0].zoo.buildings) == 2


def test_side2_budget_exhaust_ends_frame():
    s = new(3, upgraded=True)
    act(s)
    engine.step(s, builds(s, "enclosure", 3)[0])
    assert s.stack[-1].kind != "act_build"


def test_side2_done_option():
    s = new(5, upgraded=True)
    act(s)
    assert ("done",) not in [o.key for o in engine.legal_options(s)]
    engine.step(s, builds(s, "kiosk")[0])
    engine.step(s, ("done",))
    assert s.stack[-1].kind != "act_build"
    assert len(s.players[0].zoo.buildings) == 1


def test_side2_same_size_different_kind_allowed():
    s = new(5, upgraded=True)
    act(s)
    engine.step(s, builds(s, "pavilion")[0])
    assert builds(s, "kiosk") or builds(s, "enclosure", 1)
    assert not builds(s, "pavilion")


def test_side2_auto_end_when_broke():
    s = new(5, upgraded=True, money=6)
    act(s)
    engine.step(s, builds(s, "enclosure", 3)[0])
    assert s.players[0].money == 0
    assert s.stack[-1].kind != "act_build"


def test_money_from_bonus_funds_next_building():
    s = new(5, upgraded=True, money=2)
    mapdef = s.players[0].zoo.mapdef
    bonus_cell = next(c for c, v in mapdef.cells.items() if v.bonus == "money5" and mapdef.is_border(c))
    act(s)
    opt = next(o for o in builds(s, "kiosk") if o.key[3] == (bonus_cell,))
    engine.step(s, opt)
    assert s.stack[-1].kind == "act_build"
    assert s.players[0].money == 5
    assert builds(s)


def test_side2_only_kinds():
    s1 = new(5)
    act(s1)
    assert not builds(s1, "reptile_house") and not builds(s1, "aviary")
    s2 = new(5, upgraded=True)
    act(s2)
    assert builds(s2, "reptile_house") and builds(s2, "aviary")


def test_build2_cells_reachable_when_adjacent():
    s = new(1, upgraded=True)
    zoo = s.players[0].zoo
    b2 = next(c for c, v in zoo.mapdef.cells.items() if v.build2_only)
    from arknova.hexmap import neighbors
    nb = next(n for n in neighbors(b2) if n in zoo.mapdef.cells and zoo.mapdef.cells[n].terrain == "plain"
              and not zoo.mapdef.cells[n].build2_only)
    zoo.place("enclosure", 1, frozenset([nb]))
    act(s)
    assert any(o.key[3] == (b2,) for o in builds(s, "kiosk") + builds(s, "enclosure", 1))
    s.players[0].upgraded.discard("build")
    assert not any(o.key[3] == (b2,) for o in builds(s))


def test_card_moves_to_slot_one():
    s = new(4)
    act(s)
    engine.step(s, builds(s, "enclosure", 1)[0])
    assert s.players[0].slots[0] == "build"
    assert s.current == 1 and s.stack[-1].kind == "turn"
