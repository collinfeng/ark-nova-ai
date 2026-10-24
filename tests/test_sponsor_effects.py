import pytest

import arknova  # noqa: F401
import arknova.sponsor_effects  # noqa: F401  (registers the sponsor effects)
from arknova import cards, effects as E, engine, mapinfo, tables as T
from arknova.actions.sponsors import play_sponsor
from arknova.hexmap import neighbors
from arknova.state import push


def new(n=2, seed=1):
    s = engine.new_game(n, seed=seed)
    while s.stack[-1].kind == "setup_keep":
        engine.step(s, engine.legal_options(s)[0])
    for p in s.players:
        p.hand, p.money, p.appeal, p.xtokens, p.conservation = [], 20, 0, 0, 0
    return s


def kinds(s):
    return [f.kind for f in s.stack]


def keys(s):
    return [o.key for o in engine.legal_options(s)]


def animal_with(icon, count=1):
    """An animal card with exactly `count` of the icon in its tags."""
    return next(c for c in cards.ids_of("animal") if cards.card(c)["tags"].count(icon) == count)


def trigger(s, p, icons, before=None):
    E.icons_played(s, p, icons, before or {})


def own(s, p, *card_ids):
    s.players[p].zoo_cards.extend(card_ids)


UNIT = {"water": "241", "rock": "242"}  # sponsors with exactly one water / rock icon


def set_icons(s, p, icon, n):
    """Add cards to p's zoo until it has exactly n of the icon."""
    while icon_count(s, p, icon) < n:
        own(s, p, UNIT.get(icon) or animal_with(icon))
    assert icon_count(s, p, icon) == n


def icon_count(s, p, icon):
    return cards.icons(s.players[p]).get(icon, 0)


# ---- helpers for map tests ------------------------------------------------------

def plain_cells(zoo):
    return [c for c, v in zoo.mapdef.cells.items() if v.terrain == "plain"]


def near(zoo, c, terrain):
    return any(n in zoo.mapdef.cells and zoo.mapdef.cells[n].terrain == terrain for n in neighbors(c))


def cover(zoo, cells):
    for c in cells:
        zoo.place("enclosure", 1, {c})


def connected(zoo, terrain):
    cells = [c for c, v in zoo.mapdef.cells.items() if v.terrain == terrain]
    return sum(any(n in zoo.cell_owner for n in neighbors(c)) for c in cells), len(cells)


# ---- own-zoo icon triggers ---------------------------------------------------------

def test_202_reputation_per_science_icon_own_zoo_only():
    s = new()
    own(s, 0, "202")
    trigger(s, 0, {"science": 3})
    assert s.players[0].reputation == 4
    trigger(s, 1, {"science": 3})
    assert s.players[0].reputation == 4 and s.players[1].reputation == 1
    trigger(s, 0, {"bird": 2})
    assert s.players[0].reputation == 4


def test_204_conservation_per_science_icon():
    s = new()
    own(s, 0, "204")
    trigger(s, 0, {"science": 2})
    assert s.players[0].conservation == 2
    trigger(s, 1, {"science": 2})
    assert s.players[0].conservation == 2 and s.players[1].conservation == 0


def test_210_free_kiosk_per_americas_icon():
    s = new()
    own(s, 0, "210")
    trigger(s, 0, {"americas": 2})
    assert kinds(s)[-2:] == ["free_build", "free_build"]
    assert s.stack[-1].data["kinds"] == [("kiosk", 1)] and s.stack[-1].player == 0
    place = next(k for k in keys(s) if k[0] == "place")
    engine.step(s, place)
    assert s.players[0].zoo.count("kiosk") == 1
    assert s.stack[-1].kind == "free_build"
    engine.step(s, ("skip",))
    assert s.stack[-1].kind == "turn"


def test_210_not_for_other_zoo_or_other_icon():
    s = new()
    own(s, 0, "210")
    trigger(s, 1, {"americas": 1})
    trigger(s, 0, {"asia": 1})
    assert kinds(s) == ["turn"]


def test_210_free_kiosk_on_water_with_diversity_researcher():
    """With every plain space covered, the free kiosk still comes when Diversity Researcher (219)
    allows building on water and rock; without it there is no room and no free build."""
    for with_219, expected in ((False, ["turn"]), (True, ["turn", "free_build"])):
        s = new()
        own(s, 0, "210", *(["219"] if with_219 else []))
        zoo = s.players[0].zoo
        for c, cell in zoo.mapdef.cells.items():
            if cell.terrain == "plain":
                zoo.cell_owner[c] = -1
        zoo._placements.clear()  # cached before the cells were covered
        trigger(s, 0, {"americas": 1})
        assert kinds(s) == expected
        if with_219:
            place = next(k for k in keys(s) if k[0] == "place")
            assert all(zoo.mapdef.cells[tuple(c)].terrain != "plain" for c in place[-1])


def test_211_free_size_one_enclosure():
    s = new()
    own(s, 0, "211")
    trigger(s, 0, {"europe": 1})
    assert s.stack[-1].kind == "free_build" and s.stack[-1].data["kinds"] == [("enclosure", 1)]
    engine.step(s, next(k for k in keys(s) if k[0] == "place"))
    assert s.players[0].zoo.buildings[0].kind == "enclosure" and s.players[0].zoo.buildings[0].size == 1


def test_213_free_pavilion_gives_pavilion_appeal():
    s = new()
    own(s, 0, "213")
    trigger(s, 0, {"asia": 1})
    assert s.stack[-1].data["kinds"] == [("pavilion", 1)]
    engine.step(s, next(k for k in keys(s) if k[0] == "place"))
    assert s.players[0].zoo.count("pavilion") == 1 and s.players[0].appeal == 1


def test_free_build_not_offered_without_legal_placement():
    s = new()
    own(s, 0, "211")
    s.players[0].zoo.legal_placements = lambda *a, **k: []
    trigger(s, 0, {"europe": 2})
    assert kinds(s) == ["turn"]


def test_212_pouch_per_australia_icon_only_with_hand():
    s = new()
    own(s, 0, "212")
    trigger(s, 0, {"australia": 1})
    assert kinds(s) == ["turn"]
    s.players[0].hand = ["401", "402", "403"]
    trigger(s, 0, {"australia": 2})
    assert kinds(s)[-2:] == ["ab_pouch", "ab_pouch"] and s.stack[-1].data["left"] == 1
    engine.step(s, ("tuck", "401"))
    assert s.players[0].appeal == 2 and s.players[0].tucked == ["401"]
    engine.step(s, ("tuck", "402"))
    assert s.players[0].appeal == 4 and s.stack[-1].kind == "turn"


def test_212_not_for_other_zoo():
    s = new()
    own(s, 0, "212")
    s.players[0].hand = ["401"]
    trigger(s, 1, {"australia": 1})
    assert kinds(s) == ["turn"]


def test_214_action_card_to_slot_one_per_africa_icon():
    s = new()
    own(s, 0, "214")
    trigger(s, 0, {"africa": 2})
    assert kinds(s)[-2:] == ["clever", "clever"]
    target = s.players[0].slots[3]
    engine.step(s, ("clever", target))
    assert s.players[0].slots[0] == target
    engine.step(s, ("skip",))
    trigger(s, 1, {"africa": 1})
    assert kinds(s) == ["turn"]


@pytest.mark.parametrize("card_id,icon", [("243", "herbivore"), ("244", "bird"), ("245", "water"),
                                          ("246", "rock"), ("247", "primate")])
def test_243_to_247_two_appeal_per_icon_own_zoo_only(card_id, icon):
    s = new(3)
    own(s, 0, card_id)
    trigger(s, 0, {icon: 3})
    assert s.players[0].appeal == 6
    trigger(s, 1, {icon: 3})
    assert s.players[0].appeal == 6 and s.players[1].appeal == 0
    trigger(s, 0, {"reptile": 3})
    assert s.players[0].appeal == 6


def test_own_icon_triggers_when_the_card_itself_is_played():
    """Meerkat Den has a herbivore icon, so playing it triggers its own passive."""
    s = new()
    play_sponsor(s, 0, "243")
    assert s.players[0].appeal == 2
    assert s.stack[-1].kind == "sponsor_building"


@pytest.mark.parametrize("card_id,icon", [("243", "herbivore"), ("244", "bird"), ("245", "water"),
                                          ("246", "rock"), ("247", "primate")])
def test_243_to_247_endgame_needs_six_icons(card_id, icon):
    s = new()
    own(s, 0, card_id)
    for n in (icon_count(s, 0, icon), 4, 5):
        set_icons(s, 0, icon, n)
        before = s.players[0].conservation
        E.ENDGAME[card_id](s, 0)
        assert s.players[0].conservation == before
    for n in (6, 9):
        set_icons(s, 0, icon, n)
        before = s.players[0].conservation
        E.ENDGAME[card_id](s, 0)
        assert s.players[0].conservation == before + 1


def test_248_xtoken_per_primate_icon():
    s = new()
    own(s, 0, "248")
    trigger(s, 0, {"primate": 2})
    assert s.players[0].xtokens == 2
    trigger(s, 1, {"primate": 2})
    assert s.players[0].xtokens == 2 and s.players[1].xtokens == 0


def test_249_perception_two_keep_one_per_bird_icon():
    s = new()
    own(s, 0, "249")
    s.deck = ["401", "402", "403", "404", "405"]
    s.discard = []
    trigger(s, 0, {"bird": 2})
    assert kinds(s)[-2:] == ["ab_pick", "ab_pick"]
    assert s.stack[-1].data["count"] == 1
    assert s.stack[-1].data["cards"] == ["403", "402"] and s.stack[-2].data["cards"] == ["405", "404"]
    engine.step(s, ("pick", "403"))
    # keeping 1 of the 2 revealed discards the other
    assert s.players[0].hand == ["403"] and s.discard == ["402"]
    assert s.stack[-1].kind == "ab_pick"
    engine.step(s, ("pick", "404"))
    assert s.stack[-1].kind == "turn"
    assert sorted(s.players[0].hand) == ["403", "404"] and sorted(s.discard) == ["402", "405"]


def test_249_other_zoo_and_empty_deck():
    s = new()
    own(s, 0, "249")
    s.deck = ["401", "402"]
    trigger(s, 1, {"bird": 1})
    assert kinds(s) == ["turn"] and s.deck == ["401", "402"]
    s.deck, s.discard = [], []
    trigger(s, 0, {"bird": 1})
    assert kinds(s) == ["turn"] and s.players[0].hand == []


def test_250_sunbathing_per_reptile_icon():
    s = new()
    own(s, 0, "250")
    trigger(s, 0, {"reptile": 1})
    assert kinds(s) == ["turn"]  # empty hand: no frame
    s.players[0].hand = ["401", "402", "403"]
    trigger(s, 0, {"reptile": 2})
    assert kinds(s)[-2:] == ["ab_sun", "ab_sun"] and s.stack[-1].data["left"] == 2
    engine.step(s, ("sell", "401"))
    engine.step(s, ("sell", "402"))
    assert s.players[0].money == 28
    assert s.stack[-1].kind == "ab_sun"
    engine.step(s, ("done",))
    assert s.stack[-1].kind == "turn" and s.players[0].hand == ["403"]


def test_250_other_zoo_ignored():
    s = new()
    own(s, 0, "250")
    s.players[0].hand = ["401"]
    trigger(s, 1, {"reptile": 1})
    assert kinds(s) == ["turn"]


def test_252_hunter_x_is_owner_predator_icons():
    s = new()
    own(s, 0, "252", "401")  # 1 + 2 predator icons
    assert icon_count(s, 0, "predator") == 3
    s.deck = ["403", "223", "205", "402"]
    s.discard = []
    trigger(s, 0, {"predator": 1})
    frame = s.stack[-1]
    assert frame.kind == "ab_hunter" and frame.data["cards"] == ["402", "205", "223"]
    assert ("take", "402") in keys(s) and ("take", "205") not in keys(s)
    engine.step(s, ("take", "402"))
    assert s.players[0].hand == ["402"] and sorted(s.discard) == ["205", "223"]
    assert s.deck == ["403"] and s.stack[-1].kind == "turn"


def test_252_per_icon_and_no_animal_revealed():
    s = new()
    own(s, 0, "252")
    s.deck = ["205", "223", "220"]
    s.discard = []
    trigger(s, 0, {"predator": 2})  # X = 1: reveals one sponsor per icon, no animal
    assert kinds(s) == ["turn"] and sorted(s.discard) == ["220", "223"] and s.deck == ["205"]
    s.deck = ["402", "403"]
    trigger(s, 0, {"predator": 2})
    assert kinds(s)[-2:] == ["ab_hunter", "ab_hunter"]
    trigger(s, 1, {"predator": 5})
    assert kinds(s)[-2:] == ["ab_hunter", "ab_hunter"] and len(s.stack) == 3


def test_262_explorer_new_continent_or_category_icons():
    s = new()
    own(s, 0, "262")
    trigger(s, 0, {"africa": 1, "bird": 2, "science": 1}, before={"africa": 1})
    # africa already present, science is neither continent nor category: only bird counts (once)
    assert s.players[0].appeal == 1 and s.players[0].money == 22
    trigger(s, 0, {"asia": 1, "pet": 1, "rock": 1}, before={})
    assert s.players[0].appeal == 3 and s.players[0].money == 26
    trigger(s, 1, {"asia": 1}, before={})
    assert s.players[0].appeal == 3 and s.players[1].appeal == 0


def test_262_explorer_through_a_real_animal_play_flow():
    s = new()
    p = s.players[0]
    own(s, 0, "262")
    before = cards.icons(p)
    animal = animal_with("predator")
    p.zoo_cards.append(animal)
    E.icons_played(s, 0, cards.icons_of(animal), before)
    new_n = len([i for i in cards.icons_of(animal) if i in set(T.CONTINENTS) | set(T.ANIMAL_CATEGORIES)])
    assert new_n == 2 and p.appeal == 2 and p.money == 24
    before = cards.icons(p)
    p.zoo_cards.append(animal)  # same icons again: nothing new
    E.icons_played(s, 0, cards.icons_of(animal), before)
    assert p.appeal == 2 and p.money == 24


def test_262_immediate_two_money_per_distinct_icon():
    s = new()
    p = s.players[0]
    p.partner_zoos = ["africa", "asia"]
    own(s, 0, animal_with("predator", 2), "262")  # cheetah-like: predator x2 + a continent
    distinct = len(set(cards.icons(p)) & (set(T.CONTINENTS) | set(T.ANIMAL_CATEGORIES)))
    E.IMMEDIATE["262"](s, 0)
    assert p.money == 20 + 2 * distinct and distinct >= 2


# ---- any-zoo triggers -----------------------------------------------------------------

def test_208_science_library_money_for_any_zoo():
    s = new(3)
    own(s, 0, "208")
    trigger(s, 0, {"science": 2})
    assert s.players[0].money == 24
    trigger(s, 1, {"science": 3})
    assert s.players[0].money == 30 and s.players[1].money == 20
    trigger(s, 2, {"bird": 3})
    assert s.players[0].money == 30


@pytest.mark.parametrize("card_id,icon", [("236", "primate"), ("237", "reptile"), ("238", "bird"),
                                          ("239", "predator"), ("240", "herbivore")])
def test_236_to_240_three_money_per_icon_any_zoo(card_id, icon):
    s = new(3)
    own(s, 1, card_id)
    trigger(s, 0, {icon: 2})
    assert s.players[1].money == 26 and s.players[0].money == 20
    trigger(s, 1, {icon: 1})
    assert s.players[1].money == 29
    trigger(s, 2, {"science": 4})
    assert s.players[1].money == 29


def test_251_polar_bear_appeal_for_any_zoo_bear_icon():
    s = new(3)
    own(s, 0, "251")
    trigger(s, 2, {"bear": 2})
    assert s.players[0].appeal == 4
    trigger(s, 0, {"bear": 1, "predator": 1})
    assert s.players[0].appeal == 6


def test_any_zoo_trigger_fires_for_each_owner():
    s = new(3)
    own(s, 0, "236")
    own(s, 2, "238")
    trigger(s, 1, {"primate": 1, "bird": 1})
    assert s.players[0].money == 23 and s.players[2].money == 23 and s.players[1].money == 20


def test_playing_sponsors_triggers_any_zoo_effects():
    s = new()
    own(s, 0, "208")
    play_sponsor(s, 1, "205")  # Gorilla Field Research: one science icon, +1 conservation +2 reputation
    assert s.players[0].money == 22
    play_sponsor(s, 0, "223")  # Science Institute: its two science icons trigger 208 for its owner
    assert s.players[0].money == 26


def test_208_played_triggers_itself_and_scores_appeal():
    s = new()
    own(s, 0, "223")  # one science icon already in the zoo
    play_sponsor(s, 0, "208")
    assert s.players[0].money == 22  # its own science icon
    assert s.players[0].appeal == 3  # immediate: 1 appeal per science icon (2 + 1)


def test_polar_bear_played_triggers_its_own_icon():
    s = new()
    play_sponsor(s, 0, "251")
    assert s.players[0].appeal == 2


def test_spokesperson_played_triggers_its_own_icon():
    s = new()
    play_sponsor(s, 0, "202")
    assert s.players[0].reputation == 2


# ---- immediate -----------------------------------------------------------------------------

@pytest.mark.parametrize("card_id", ["201", "254"])
def test_201_254_take_a_card(card_id):
    s = new()
    own(s, 0, card_id)
    E.IMMEDIATE[card_id](s, 0)
    assert s.stack[-1].kind == "take_card" and s.stack[-1].player == 0


def test_216_hires_a_worker():
    s = new()
    play_sponsor(s, 0, "216")
    assert s.players[0].workers == 2


def test_207_conservation_and_others_gain_money():
    s = new(3)
    p = s.players[0]
    p.partner_zoos = ["africa", "asia", "europe"]
    own(s, 0, animal_with("bird"), "207")  # 3 continents + 1 category (bird animal carries a continent too)
    distinct = len(set(cards.icons(p)) & (set(T.CONTINENTS) | set(T.ANIMAL_CATEGORIES)))
    n = distinct // 2
    assert n >= 2
    E.IMMEDIATE["207"](s, 0)
    assert p.conservation == n
    assert s.players[1].money == 20 + 2 * n and s.players[2].money == 20 + 2 * n and p.money == 20


def test_207_floor_and_zero():
    s = new()
    own(s, 0, "207")
    E.IMMEDIATE["207"](s, 0)
    assert s.players[0].conservation == 0 and s.players[1].money == 20
    s.players[0].partner_zoos = ["africa", "asia", "europe"]
    E.IMMEDIATE["207"](s, 0)
    assert s.players[0].conservation == 1 and s.players[1].money == 22


def test_222_conservation_per_science_icon_max_three():
    s = new(3)
    p = s.players[0]
    own(s, 0, "222", "223")
    assert icon_count(s, 0, "science") == 2
    E.IMMEDIATE["222"](s, 0)
    assert p.conservation == 2 and s.players[1].money == 24 and s.players[2].money == 24
    s = new()
    own(s, 0, "222", "205", "223", "220", "209", "206")
    assert icon_count(s, 0, "science") == 6
    E.IMMEDIATE["222"](s, 0)
    assert s.players[0].conservation == 3 and s.players[1].money == 26


@pytest.mark.parametrize("card_id,icon", [("231", "primate"), ("232", "reptile"), ("233", "bird"),
                                          ("234", "predator"), ("235", "herbivore")])
def test_231_to_235_immediate_appeal_per_icon(card_id, icon):
    s = new()
    own(s, 0, animal_with(icon, 1), animal_with(icon, 1), card_id)
    n = icon_count(s, 0, icon)
    assert n >= 2
    E.IMMEDIATE[card_id](s, 0)
    assert s.players[0].appeal == n


def test_241_242_immediate_appeal():
    s = new()
    own(s, 0, "241", "245")
    assert icon_count(s, 0, "water") >= 2
    E.IMMEDIATE["241"](s, 0)
    assert s.players[0].appeal == icon_count(s, 0, "water")
    s = new()
    own(s, 0, "242")
    set_icons(s, 0, "rock", 4)
    E.IMMEDIATE["242"](s, 0)
    assert s.players[0].appeal == 6
    s = new()
    own(s, 0, "242")
    set_icons(s, 0, "rock", 3)
    E.IMMEDIATE["242"](s, 0)
    assert s.players[0].appeal == 3


def test_play_hydrologist_counts_its_own_water_icon():
    s = new()
    play_sponsor(s, 0, "241")
    assert s.players[0].appeal == 1


def test_258_259_connected_spaces_appeal():
    s = new()
    zoo = s.players[0].zoo
    wet = [c for c in plain_cells(zoo) if near(zoo, c, "water")][:2]
    dry_rock = [c for c in plain_cells(zoo) if near(zoo, c, "rock")][:2]
    cover(zoo, list(dict.fromkeys(wet + dry_rock)))
    want_w, want_r = connected(zoo, "water")[0], connected(zoo, "rock")[0]
    assert want_w >= 2 and want_r >= 2
    own(s, 0, "258", "259")
    E.IMMEDIATE["258"](s, 0)
    assert s.players[0].appeal == want_w
    E.IMMEDIATE["259"](s, 0)
    assert s.players[0].appeal == want_w + want_r


def test_260_connected_empty_border_spaces():
    s = new()
    zoo = s.players[0].zoo
    border = next(c for c in plain_cells(zoo) if zoo.mapdef.is_border(c))
    cover(zoo, [border])
    assert mapinfo.connected_empty_border(zoo) >= 1
    own(s, 0, "260")
    E.IMMEDIATE["260"](s, 0)
    assert s.players[0].appeal == mapinfo.connected_empty_border(zoo)


def test_264_connected_bonus_spaces():
    s = new()
    zoo = s.players[0].zoo
    bonus = next(c for c, v in zoo.mapdef.cells.items() if v.bonus)
    neighbor = next(n for n in neighbors(bonus) if n in zoo.mapdef.cells and zoo.mapdef.cells[n].terrain == "plain"
                    and not zoo.mapdef.cells[n].bonus)
    cover(zoo, [neighbor])
    want = mapinfo.bonus_spaces(zoo)[0]
    assert want >= 1
    own(s, 0, "264")
    E.IMMEDIATE["264"](s, 0)
    assert s.players[0].appeal == want


# ---- income ----------------------------------------------------------------------------------

def test_simple_incomes():
    s = new()
    own(s, 0, "201", "206", "209", "220")
    for cid in ("206", "209", "220"):
        E.INCOME[cid](s, 0)
    p = s.players[0]
    assert (p.conservation, p.xtokens, p.money) == (1, 1, 23)
    E.INCOME["201"](s, 0)
    assert s.stack[-1].kind == "take_card"


@pytest.mark.parametrize("card_id,icon", [("231", "primate"), ("232", "reptile"), ("233", "bird"),
                                          ("234", "predator"), ("235", "herbivore")])
@pytest.mark.parametrize("icons,money", [(0, 0), (1, 3), (2, 3), (3, 6), (4, 6), (5, 9), (7, 9)])
def test_231_to_235_income_tiers(card_id, icon, icons, money):
    s = new()
    own(s, 0, card_id, *[animal_with(icon)] * icons)
    assert icon_count(s, 0, icon) == icons
    E.INCOME[card_id](s, 0)
    assert s.players[0].money == 20 + money


def test_income_through_a_real_break():
    s = new()
    for p in s.players:
        p.hand = []
    own(s, 0, "220", "231", animal_with("primate"))
    own(s, 1, "220")
    push(s, "break", 0, phase=0)
    engine._settle(s)
    assert s.stack[-1].kind == "turn"
    base = T.appeal_income(0)
    assert s.players[0].money == 20 + base + 3 + 3
    assert s.players[1].money == 20 + T.appeal_income(s.players[1].appeal) + 3


def test_real_break_conservation_income():
    s = new()
    for p in s.players:
        p.hand = []
    own(s, 0, "206")
    push(s, "break", 0, phase=0)
    engine._settle(s)
    assert s.players[0].conservation == 1


def _entrance_layout(zoo):
    """A 2-cell side entrance plus four distinct free neighbour cells."""
    plain = set(plain_cells(zoo))
    for a in sorted(plain):
        for b in neighbors(a):
            if b in plain:
                around = [n for c in (a, b) for n in neighbors(c) if n in plain and n not in (a, b)]
                around = sorted(set(around))
                if len(around) >= 6:
                    return (a, b), around
    raise AssertionError("no layout")


def test_257_side_entrance_income():
    s = new()
    zoo = s.players[0].zoo
    (a, b), around = _entrance_layout(zoo)
    zoo.place("unique", 2, {a, b}, name="257")
    own(s, 0, "257")
    empty = zoo.place("enclosure", 1, {around[0]})[0]
    full = zoo.place("enclosure", 1, {around[1]})[0]
    full.occupied = True
    zoo.place("kiosk", 1, {around[2]})
    zoo.place("pavilion", 1, {around[3]})
    far = next(c for c in plain_cells(zoo) if c not in zoo.cell_owner and c not in around
               and not any(n in (a, b) for n in neighbors(c)))
    zoo.place("pavilion", 1, {far})
    assert not empty.occupied
    E.INCOME["257"](s, 0)
    assert s.players[0].money == 20 + 2 * 3


def test_257_income_without_building_or_neighbours():
    s = new()
    own(s, 0, "257")
    E.INCOME["257"](s, 0)
    assert s.players[0].money == 20
    zoo = s.players[0].zoo
    (a, b), _ = _entrance_layout(zoo)
    zoo.place("unique", 2, {a, b}, name="257")
    E.INCOME["257"](s, 0)
    assert s.players[0].money == 20


# ---- build hooks --------------------------------------------------------------------------------

def _two_cells(zoo, terrain, wanted):
    """A pair of adjacent bonus-free plain cells next to (or not next to) the terrain."""
    plain = [c for c in plain_cells(zoo) if not zoo.mapdef.cells[c].bonus]
    for a in plain:
        for b in neighbors(a):
            if b in plain and b not in zoo.cell_owner and a not in zoo.cell_owner \
                    and near(zoo, a, terrain) == wanted and near(zoo, b, terrain) == wanted \
                    and not near(zoo, a, "rock" if terrain == "water" else "water") and \
                    not near(zoo, b, "rock" if terrain == "water" else "water"):
                return a, b
    raise AssertionError("no cells")


def test_241_hydrologist_build_hook():
    s = new()
    own(s, 0, "241")
    zoo = s.players[0].zoo
    a, b = _two_cells(zoo, "water", True)
    E.place_building(s, 0, "enclosure", 2, frozenset({a, b}))
    assert s.players[0].money == 22
    c, d = _two_cells(zoo, "water", False)
    E.place_building(s, 0, "enclosure", 2, frozenset({c, d}))
    assert s.players[0].money == 22


def test_241_hook_counts_cells_not_water_spaces_and_ignores_rock():
    s = new()
    own(s, 0, "241")
    zoo = s.players[0].zoo
    cell = next(c for c in plain_cells(zoo) if not zoo.mapdef.cells[c].bonus and near(zoo, c, "rock")
                and not near(zoo, c, "water"))
    E.place_building(s, 0, "kiosk", 1, frozenset({cell}))
    assert s.players[0].money == 20
    cell = next(c for c in plain_cells(zoo) if not zoo.mapdef.cells[c].bonus and c not in zoo.cell_owner
                and sum(n in zoo.mapdef.cells and zoo.mapdef.cells[n].terrain == "water" for n in neighbors(c)) >= 2)
    E.place_building(s, 0, "enclosure", 1, frozenset({cell}))
    assert s.players[0].money == 21  # one covered cell, however many water spaces touch it


def test_242_geologist_build_hook():
    s = new()
    own(s, 0, "242")
    zoo = s.players[0].zoo
    a, b = _two_cells(zoo, "rock", True)
    E.place_building(s, 0, "enclosure", 2, frozenset({a, b}))
    assert s.players[0].money == 22


def test_build_hook_only_for_the_owner():
    s = new()
    own(s, 0, "241", "242")
    z1 = s.players[1].zoo
    a, b = _two_cells(z1, "water", True)
    E.place_building(s, 1, "enclosure", 2, frozenset({a, b}))
    assert s.players[0].money == 20 and s.players[1].money == 20
    s = new()
    z0 = s.players[0].zoo
    a, b = _two_cells(z0, "water", True)
    E.place_building(s, 0, "enclosure", 2, frozenset({a, b}))
    assert s.players[0].money == 20


def test_build_hook_applies_to_free_build_frames_and_both_cards_stack():
    s = new()
    own(s, 0, "241", "242")
    zoo = s.players[0].zoo
    cell = next(c for c in plain_cells(zoo) if not zoo.mapdef.cells[c].bonus
                and near(zoo, c, "water") and near(zoo, c, "rock"))
    push(s, "free_build", 0, kinds=[("kiosk", 1)])
    engine.step(s, ("place", "kiosk", 1, (cell,)) if ("place", "kiosk", 1, (cell,)) in keys(s)
                else next(k for k in keys(s) if k[0] == "place"))
    placed = zoo.buildings[0].cells
    want = sum(near(zoo, c, "water") for c in placed) + sum(near(zoo, c, "rock") for c in placed)
    assert s.players[0].money == 20 + want


# ---- endgame --------------------------------------------------------------------------------------

def _score(s, card_id, p=0):
    before = (s.players[p].conservation, s.players[p].appeal)
    E.ENDGAME[card_id](s, p)
    return s.players[p].conservation - before[0], s.players[p].appeal - before[1]


@pytest.mark.parametrize("science,expected", [(0, 0), (2, 0), (3, 1), (5, 1), (6, 2), (8, 2)])
def test_201_endgame_tiers(science, expected):
    s = new()
    p = s.players[0]
    p.universities = []
    own(s, 0, "201")  # 1 science icon
    if science:
        own(s, 0, *["205"] * (science - 1))
    else:
        p.zoo_cards.clear()
    assert icon_count(s, 0, "science") == science
    assert _score(s, "201") == (expected, 0)


def _categories(s, n):
    cats = [c for c in T.ANIMAL_CATEGORIES][:n]
    for c in cats:
        own(s, 0, animal_with(c))


@pytest.mark.parametrize("card_id", ["208", "261"])
def test_five_animal_categories(card_id):
    s = new()
    _categories(s, 4)
    own(s, 0, animal_with("bird", 1))
    assert _score(s, card_id) == (0, 0)
    s = new()
    _categories(s, 5)
    assert _score(s, card_id) == (1, 0)
    _categories(s, 7)
    assert _score(s, card_id) == (1, 0)  # still just 1


@pytest.mark.parametrize("card_id", ["225", "226"])
def test_five_continents(card_id):
    s = new()
    s.players[0].partner_zoos = ["africa", "asia", "europe", "americas"]
    assert _score(s, card_id) == (0, 0)
    s.players[0].partner_zoos.append("australia")
    assert _score(s, card_id) == (1, 0)


def test_continents_from_animal_cards_count():
    s = new()
    for cont in T.CONTINENTS:
        own(s, 0, next(c for c in cards.ids_of("animal") if cards.card(c)["tags"].count(cont) == 1))
    assert _score(s, "225") == (1, 0)


def test_241_242_endgame_all_connected():
    s = new()
    zoo = s.players[0].zoo
    assert _score(s, "241") == (0, 0) and _score(s, "242") == (0, 0)
    water = [c for c, v in zoo.mapdef.cells.items() if v.terrain == "water"]
    rock = [c for c, v in zoo.mapdef.cells.items() if v.terrain == "rock"]
    for t in water + rock:
        for n in neighbors(t):
            if n in zoo.mapdef.cells and zoo.mapdef.cells[n].terrain == "plain" and n not in zoo.cell_owner:
                zoo.place("enclosure", 1, {n})
                break
    cover(zoo, [c for c in plain_cells(zoo) if c not in zoo.cell_owner and (near(zoo, c, "water") or near(zoo, c, "rock"))])
    assert connected(zoo, "water")[0] == connected(zoo, "water")[1]
    assert connected(zoo, "rock")[0] == connected(zoo, "rock")[1]
    assert _score(s, "241") == (1, 0) and _score(s, "242") == (1, 0)


def test_241_242_endgame_independent():
    s = new()
    zoo = s.players[0].zoo
    cover(zoo, [c for c in plain_cells(zoo) if near(zoo, c, "water")])
    assert connected(zoo, "water")[0] == connected(zoo, "water")[1]
    assert connected(zoo, "rock")[0] < connected(zoo, "rock")[1]
    assert _score(s, "241") == (1, 0) and _score(s, "242") == (0, 0)


@pytest.mark.parametrize("bears,expected", [(0, 0), (2, 0), (3, 1), (5, 1), (6, 2), (9, 2)])
def test_251_endgame_bear_tiers(bears, expected):
    s = new()
    own(s, 0, "251", *[animal_with("bear")] * max(0, bears - 1))  # 251 carries one bear icon itself
    if bears:
        assert icon_count(s, 0, "bear") == bears
    else:
        s.players[0].zoo_cards.remove("251")  # no bear icons at all
    assert _score(s, "251") == (expected, 0)


def test_251_endgame_counts_only_the_owners_zoo():
    s = new()
    own(s, 0, "251")
    own(s, 1, *[animal_with("bear")] * 6)
    assert _score(s, "251") == (0, 0)


def test_257_endgame_fully_covered():
    s = new()
    zoo = s.players[0].zoo
    cells = plain_cells(zoo)
    cover(zoo, cells[:-1])
    assert _score(s, "257") == (0, 0)
    cover(zoo, cells[-1:])
    assert zoo.is_fully_covered()
    assert _score(s, "257") == (0, 5)


def test_258_259_endgame_unconnected_floor_half():
    s = new()
    zoo = s.players[0].zoo
    cw, tw = connected(zoo, "water")
    cr, tr = connected(zoo, "rock")
    assert (cw, cr) == (0, 0)
    assert _score(s, "258") == (tw // 2, 0)
    assert _score(s, "259") == (tr // 2, 0)
    cover(zoo, [next(c for c in plain_cells(zoo) if near(zoo, c, "water") and c not in zoo.cell_owner)])
    cw, tw = connected(zoo, "water")
    assert cw >= 1
    assert _score(s, "258")[0] == (tw - cw) // 2


def test_260_endgame_per_six_empty_spaces():
    s = new()
    zoo = s.players[0].zoo
    plain = plain_cells(zoo)
    cover(zoo, plain[: len(plain) - 13])
    assert len(mapinfo.empty_spaces(zoo)) == 13
    assert _score(s, "260") == (2, 0)
    cover(zoo, plain[len(plain) - 13: len(plain) - 7])
    assert len(mapinfo.empty_spaces(zoo)) == 7
    assert _score(s, "260") == (1, 0)
    cover(zoo, plain[len(plain) - 7: len(plain) - 2])
    assert _score(s, "260") == (0, 0)


def test_264_endgame_per_two_unconnected_bonus_spaces():
    s = new()
    zoo = s.players[0].zoo
    connected_n, unconnected = mapinfo.bonus_spaces(zoo)
    assert connected_n == 0 and unconnected >= 4
    assert _score(s, "264") == (unconnected // 2, 0)


def test_endgame_uses_score_not_gain():
    """Final conservation never pushes frames (no track bonuses)."""
    s = new()
    own(s, 0, "201", *["205"] * 7)
    E.ENDGAME["201"](s, 0)
    assert s.players[0].conservation == 2 and kinds(s) == ["turn"]


# ---- registry overview -----------------------------------------------------------------------------

def test_registry_contents():
    mine = {str(i) for i in range(201, 265)} - {"203", "215", "217", "218", "219", "221", "224", "227", "228",
                                                 "229", "230", "253", "263"}
    nothing = {"205", "223", "255", "256"}

    def present(table):
        return sorted(c for c in table if c in mine)

    assert present(E.IMMEDIATE) == sorted(
        {"201", "254", "216", "207", "222", "208", "231", "232", "233", "234", "235", "241", "242",
         "258", "259", "260", "262", "264"})
    assert present(E.INCOME) == sorted(
        {"201", "206", "209", "220", "231", "232", "233", "234", "235", "257"})
    assert present(E.ICON_TRIGGERS) == sorted(
        {"202", "204", "208", "210", "211", "212", "213", "214", "236", "237", "238", "239", "240",
         "243", "244", "245", "246", "247", "248", "249", "250", "251", "252", "262"})
    assert present(E.ENDGAME) == sorted(
        {"201", "208", "261", "225", "226", "241", "242", "243", "244", "245", "246", "247", "251", "257",
         "258", "259", "260", "264"})
    for table in (E.IMMEDIATE, E.INCOME, E.ICON_TRIGGERS, E.ENDGAME):
        assert not nothing & set(table)
    assert len([h for h in E.AFTER_BUILD_HOOKS if h.__module__ == "arknova.sponsor_effects"]) == 1
    covered = set()
    for table in (E.IMMEDIATE, E.INCOME, E.ICON_TRIGGERS, E.ENDGAME):
        covered |= set(table) & mine
    # build-hook-only cards 241/242 are also covered above; everything else is either mine or "nothing"
    assert mine - covered - nothing == set()
