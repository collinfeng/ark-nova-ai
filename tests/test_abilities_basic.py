import pytest

import arknova.abilities_basic  # noqa: F401  (registers the keywords)
from arknova import abilities, cards, engine

AB = abilities.ABILITIES


def new(seed=1):
    s = engine.new_game(2, seed=seed)
    while s.stack[-1].kind == "setup_keep":
        engine.step(s, engine.legal_options(s)[0])
    assert s.stack[-1].kind == "turn"
    p = s.players[0]
    p.hand, p.money, p.appeal, p.xtokens = [], 20, 0, 0
    return s, p


def sponsors(n):
    return cards.ids_of("sponsor")[:n]


def animals(n, tag=None):
    return [c for c in cards.ids_of("animal") if tag is None or tag in cards.card(c)["tags"]][:n]


def keys(s):
    return [o.key for o in engine.legal_options(s)]


def go(s, key):
    engine.step(s, key)


def test_sprint_draws_and_handles_empty_deck():
    s, p = new()
    deck = list(s.deck)
    AB["SPRINT"](s, 0, "x", 3)
    assert p.hand == deck[-1:-4:-1] and len(s.deck) == len(deck) - 3
    s, p = new()
    s.deck, s.discard = [], []
    AB["SPRINT"](s, 0, "x", 2)
    assert p.hand == []
    s, p = new()
    s.deck, s.discard = ["a"], ["b"]
    AB["SPRINT"](s, 0, "x", 2)
    assert sorted(p.hand) == ["a", "b"]


def test_jumping_advances_break_and_pays():
    s, p = new()
    AB["JUMPING"](s, 0, "x", 3)
    assert s.break_pos == 3 and p.money == 23


def test_jumping_triggering_break_gives_xtoken():
    s, p = new()
    s.break_pos = 8
    AB["JUMPING"](s, 0, "x", 4)
    assert s.break_by == 0 and p.xtokens == 1 and p.money == 24


def test_inventive():
    s, p = new()
    AB["INVENTIVE"](s, 0, "x", None)
    assert p.xtokens == 1


def test_inventive_bear_counts_all_zoos_max_3():
    s, p = new()
    bears = animals(10, "bear")
    p.zoo_cards = bears[:1]
    s.players[1].zoo_cards = bears[1:2]
    AB["INVENTIVE_BEAR"](s, 0, "x", None)
    assert p.xtokens == 2
    p.zoo_cards = bears[:3]
    s.players[1].zoo_cards = bears[3:6]
    p.xtokens = 0
    AB["INVENTIVE_BEAR"](s, 0, "x", None)
    assert p.xtokens == 3


@pytest.mark.parametrize("n,expected", [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3)])
def test_inventive_primary_thresholds(n, expected):
    s, p = new()
    single = [c for c in animals(200, "primate") if cards.card(c)["tags"].count("primate") == 1]
    p.zoo_cards = single[:n]
    assert cards.icons(p).get("primate", 0) == n
    AB["INVENTIVE_PRIMARY"](s, 0, "x", None)
    assert p.xtokens == expected


def test_pack_counts_own_predators_only():
    s, p = new()
    pred = [c for c in animals(200, "predator") if cards.card(c)["tags"].count("predator") == 1]
    p.zoo_cards = pred[:3]
    s.players[1].zoo_cards = pred[3:5]
    AB["PACK"](s, 0, "x", None)
    assert p.appeal == 3


def test_petting_zoo_animal():
    s, p = new()
    p.zoo_cards = animals(2, "pet")
    AB["PETTING_ZOO_ANIMAL"](s, 0, "x", None)
    assert p.appeal == 6


@pytest.mark.parametrize("name", ["Africa", "africa", "AFRICA"])
def test_iconic_animal_case_insensitive_all_zoos(name):
    s, p = new()
    p.zoo_cards = animals(3, "africa")
    s.players[1].zoo_cards = animals(5, "africa")[3:]
    n = sum(cards.icons(q).get("africa", 0) for q in s.players)
    assert 0 < n <= 8
    AB["ICONIC_ANIMAL"](s, 0, "x", name)
    assert p.appeal == n


def test_iconic_animal_max_8():
    s, p = new()
    p.zoo_cards = animals(12, "asia")
    s.players[1].zoo_cards = animals(24, "asia")[12:]
    assert sum(cards.icons(q).get("asia", 0) for q in s.players) > 8
    AB["ICONIC_ANIMAL"](s, 0, "x", "Asia")
    assert p.appeal == 8


def test_full_throated():
    s, p = new()
    AB["FULL_THROATED"](s, 0, "x", None)
    assert p.workers == 2


def test_perception_keep_two():
    s, p = new()
    s.deck = animals(5)
    s.discard = []
    top4 = s.deck[-4:]
    AB["PERCEPTION_4"](s, 0, "x", None)
    assert s.stack[-1].kind == "ab_pick"
    assert keys(s) == [("pick", c) for c in reversed(top4)]  # drawn from the end
    go(s, ("pick", top4[3]))
    assert s.stack[-1].kind == "ab_pick" and p.hand == [top4[3]]
    go(s, ("pick", top4[0]))
    assert s.stack[-1].kind == "turn"
    assert sorted(p.hand) == sorted([top4[3], top4[0]])
    assert sorted(s.discard) == sorted(top4[1:3])


def test_perception_short_deck():
    s, p = new()
    s.deck, s.discard = animals(1), []
    AB["PERCEPTION_4"](s, 0, "x", None)
    assert s.stack[-1].kind == "turn" and p.hand == animals(1)
    s, p = new()
    s.deck, s.discard = [], []
    AB["PERCEPTION_4"](s, 0, "x", None)
    assert s.stack[-1].kind == "turn" and p.hand == []
    s, p = new()
    s.deck, s.discard = animals(3), []
    AB["PERCEPTION_4"](s, 0, "x", None)
    go(s, keys(s)[0])
    go(s, keys(s)[0])
    assert len(p.hand) == 2 and len(s.discard) == 1 and s.stack[-1].kind == "turn"


def test_hunter_takes_animal_and_discards_rest():
    s, p = new()
    sp, an = sponsors(2), animals(2)
    s.deck, s.discard = [sp[0], an[0], sp[1], an[1]], []
    AB["HUNTER"](s, 0, "x", 3)  # reveals an[1], sp[1], an[0]
    assert sorted(keys(s)) == sorted([("take", an[1]), ("take", an[0]), ("skip",)])
    go(s, ("take", an[0]))
    assert p.hand == [an[0]]
    assert sorted(s.discard) == sorted([an[1], sp[1]])
    assert s.deck == [sp[0]] and s.stack[-1].kind == "turn"


def test_hunter_skip_and_no_animals():
    s, p = new()
    an, sp = animals(2), sponsors(2)
    s.deck, s.discard = list(an), []
    AB["HUNTER"](s, 0, "x", 2)
    go(s, ("skip",))
    assert p.hand == [] and sorted(s.discard) == sorted(an)
    s, p = new()
    s.deck, s.discard = list(sp), []
    AB["HUNTER"](s, 0, "x", 2)
    assert s.stack[-1].kind == "turn" and sorted(s.discard) == sorted(sp)
    s, p = new()
    s.deck, s.discard = [], []
    AB["HUNTER"](s, 0, "x", 2)
    assert s.stack[-1].kind == "turn"


def test_scavenging():
    s, p = new()
    an = animals(5)
    s.discard = list(an)
    AB["SCAVENGING"](s, 0, "x", 3)
    frame = s.stack[-1]
    assert frame.kind == "ab_pick" and len(frame.data["cards"]) == 3 and len(s.discard) == 2
    shown = list(frame.data["cards"])
    go(s, ("pick", shown[1]))
    assert p.hand == [shown[1]] and s.stack[-1].kind == "turn"
    assert sorted(s.discard) == sorted(set(an) - {shown[1]})


def test_scavenging_empty_and_single():
    s, p = new()
    s.discard = []
    AB["SCAVENGING"](s, 0, "x", 3)
    assert s.stack[-1].kind == "turn" and p.hand == []
    s, p = new()
    s.discard = animals(1)
    AB["SCAVENGING"](s, 0, "x", 3)
    assert s.stack[-1].kind == "turn" and p.hand == animals(1) and s.discard == []


def test_snapping_1():
    s, p = new()
    first = s.display[2]
    AB["SNAPPING_1"](s, 0, "x", None)
    assert keys(s) == [("take", i) for i in range(6)] + [("skip",)]
    go(s, ("take", 2))
    assert p.hand == [first] and s.display[2] is None and s.stack[-1].kind == "turn"


def test_snapping_skip_and_none_entries():
    s, p = new()
    s.display[0] = None
    AB["SNAPPING_1"](s, 0, "x", None)
    assert ("take", 0) not in keys(s)
    go(s, ("skip",))
    assert p.hand == [] and s.stack[-1].kind == "turn"
    s, p = new()
    s.display = [None] * 6
    AB["SNAPPING_1"](s, 0, "x", None)
    assert keys(s) == [("skip",)]


def test_snapping_2_with_replenish_between():
    s, p = new()
    a, b = s.display[0], s.display[1]
    AB["SNAPPING_2"](s, 0, "x", None)
    assert ("replenish",) not in keys(s)  # only between the picks
    go(s, ("take", 0))
    assert ("replenish",) in keys(s)
    go(s, ("replenish",))
    assert None not in s.display and s.display[0] == b  # compacted, then refilled
    assert ("replenish",) not in keys(s)
    new_first = s.display[0]
    go(s, ("take", 0))
    assert p.hand == [a, new_first] and s.stack[-1].kind == "turn"
    assert s.display[0] is None


def test_snapping_2_skip_second_pick():
    s, p = new()
    AB["SNAPPING_2"](s, 0, "x", None)
    go(s, ("take", 1))
    go(s, ("skip",))
    assert len(p.hand) == 1 and s.stack[-1].kind == "turn"


def test_sponsor_magnet():
    s, p = new()
    sp, an = sponsors(2), animals(3)
    s.display = [an[0], sp[0], None, an[1], sp[1], an[2]]
    AB["SPONSOR_MAGNET"](s, 0, "x", None)
    assert p.hand == [sp[0], sp[1]]
    assert s.display == [an[0], None, None, an[1], None, an[2]]
    AB["SPONSOR_MAGNET"](s, 0, "x", None)  # nothing left
    assert len(p.hand) == 2


def test_sun_bathing_sell_up_to_n():
    s, p = new()
    p.hand = animals(4)
    hand = list(p.hand)
    AB["SUN_BATHING"](s, 0, "x", 2)
    assert keys(s) == [("sell", c) for c in hand] + [("done",)]
    go(s, ("sell", hand[0]))
    go(s, ("sell", hand[3]))
    assert s.stack[-1].kind == "turn" and p.money == 28
    assert p.hand == hand[1:3] and s.discard[-2:] == [hand[0], hand[3]]


def test_sun_bathing_done_and_empty_hand_and_small_hand():
    s, p = new()
    p.hand = animals(3)
    AB["SUN_BATHING"](s, 0, "x", 3)
    go(s, ("done",))
    assert p.money == 20 and len(p.hand) == 3 and s.stack[-1].kind == "turn"
    s, p = new()
    AB["SUN_BATHING"](s, 0, "x", 3)
    assert s.stack[-1].kind == "turn"
    s, p = new()
    p.hand = animals(2)
    AB["SUN_BATHING"](s, 0, "x", 4)
    go(s, ("sell", p.hand[0]))
    go(s, ("sell", p.hand[0]))
    assert p.hand == [] and p.money == 28 and s.stack[-1].kind == "turn"


def test_digging_display_and_hand():
    s, p = new()
    p.hand = animals(2)
    h0 = p.hand[0]
    old = s.display[1]
    top = s.deck[-1]
    AB["DIGGING"](s, 0, "x", 3)
    assert keys(s) == [("discard_display", i) for i in range(6)] + [("discard_hand", c) for c in p.hand] + [("done",)]
    go(s, ("discard_display", 1))
    assert old in s.discard and None not in s.display and old not in s.display
    assert s.display[-1] == top
    deck_top = s.deck[-1]
    go(s, ("discard_hand", h0))
    assert h0 in s.discard and deck_top in p.hand and h0 not in p.hand and len(p.hand) == 2
    go(s, ("done",))
    assert s.stack[-1].kind == "turn"


def test_digging_limit_and_empty():
    s, p = new()
    AB["DIGGING"](s, 0, "x", 2)
    go(s, ("discard_display", 0))
    assert s.stack[-1].kind == "ab_dig"
    go(s, ("discard_display", 0))
    assert s.stack[-1].kind == "turn"
    s, p = new()
    s.display = [None] * 6
    s.deck, s.discard = [], []
    AB["DIGGING"](s, 0, "x", 1)
    assert keys(s) == [("done",)]
    go(s, ("done",))
    assert s.stack[-1].kind == "turn"


def test_digging_hand_with_empty_deck():
    s, p = new()
    p.hand = animals(1)
    s.deck, s.discard = [], []
    AB["DIGGING"](s, 0, "x", 1)
    go(s, ("discard_hand", p.hand[0]))
    assert p.hand == [] and len(s.discard) == 1 and s.stack[-1].kind == "turn"


def test_pouch():
    s, p = new()
    p.hand = animals(3)
    h = list(p.hand)
    AB["POUCH"](s, 0, "x", 2)
    go(s, ("tuck", h[1]))
    assert p.tucked == [h[1]] and p.appeal == 2 and h[1] not in s.discard
    assert s.stack[-1].kind == "ab_pouch"
    go(s, ("tuck", h[0]))
    assert p.tucked == [h[1], h[0]] and p.appeal == 4 and p.hand == [h[2]]
    assert s.stack[-1].kind == "turn"


def test_pouch_done_and_empty_hand():
    s, p = new()
    p.hand = animals(2)
    AB["POUCH"](s, 0, "x", 2)
    go(s, ("done",))
    assert p.appeal == 0 and p.tucked == [] and s.stack[-1].kind == "turn"
    s, p = new()
    AB["POUCH"](s, 0, "x", 2)
    assert s.stack[-1].kind == "turn"
    s, p = new()
    p.hand = animals(1)
    AB["POUCH"](s, 0, "x", 3)
    go(s, ("tuck", p.hand[0]))
    assert s.stack[-1].kind == "turn" and p.appeal == 2


def test_resistance():
    s, p = new()
    before = list(s.final_deck)
    mine = list(p.final_cards)
    AB["RESISTANCE"](s, 0, "x", None)
    a, b = before[-1], before[-2]
    assert keys(s) == [("keep", a), ("keep", b)]
    go(s, ("keep", b))
    assert p.final_cards == mine + [b]
    assert s.final_deck == [a] + before[:-2]
    assert s.stack[-1].kind == "turn"


def test_resistance_short_deck():
    s, p = new()
    s.final_deck = ["z"]
    n = len(p.final_cards)
    AB["RESISTANCE"](s, 0, "x", None)
    assert p.final_cards[-1] == "z" and len(p.final_cards) == n + 1 and s.final_deck == []
    AB["RESISTANCE"](s, 0, "x", None)
    assert s.stack[-1].kind == "turn" and len(p.final_cards) == n + 1


def test_assertion():
    s, p = new()
    deck = list(s.base_project_deck)
    assert deck
    AB["ASSERTION"](s, 0, "x", None)
    assert keys(s) == [("take", c) for c in deck] + [("skip",)]
    go(s, ("take", deck[-1]))
    assert p.hand == [deck[-1]] and deck[-1] not in s.base_project_deck
    assert s.stack[-1].kind == "turn"


def test_assertion_skip_and_empty():
    s, p = new()
    AB["ASSERTION"](s, 0, "x", None)
    go(s, ("skip",))
    assert p.hand == []
    s, p = new()
    s.base_project_deck = []
    AB["ASSERTION"](s, 0, "x", None)
    assert s.stack[-1].kind == "turn"


def test_dominance():
    s, p = new()
    s.base_project_deck = ["108", "109"]
    AB["DOMINANCE"](s, 0, "x", None)
    assert keys(s) == [("take", "108"), ("skip",)]
    go(s, ("take", "108"))
    assert p.hand == ["108"] and s.base_project_deck == ["109"]
    s, p = new()
    s.base_project_deck = ["109"]
    AB["DOMINANCE"](s, 0, "x", None)
    assert s.stack[-1].kind == "turn" and p.hand == []
    s, p = new()
    s.base_project_deck = ["108"]
    AB["DOMINANCE"](s, 0, "x", None)
    go(s, ("skip",))
    assert s.base_project_deck == ["108"] and p.hand == []


# ---- end to end through the Animals action ---------------------------------

def _prepare_play(s, p, cid, rock=0):
    p.hand = [cid]
    p.money = 100
    p.slots = ["animals", "cards", "build", "association", "sponsors"]
    size = cards.card(cid)["enclosure"]["standard_size"]
    options = p.zoo.legal_placements("enclosure", size)
    if rock:
        options = [c for c in options if p.zoo.adjacent_terrain(c, "rock") >= rock]
    p.zoo.place("enclosure", size, options[0])
    p.xtokens = 1


def test_end_to_end_sprint():
    s, p = new()
    cid = "507"  # Sprint 1, no requirements
    _prepare_play(s, p, cid)
    top = s.deck[-1]
    go(s, ("act", "animals", 1))
    go(s, keys(s)[0])
    assert cid in p.zoo_cards and p.hand == [top]
    assert p.appeal == cards.card(cid)["appeal"]


def test_end_to_end_jumping():
    s, p = new()
    cid = "413"  # Jumping 3, needs a rock
    _prepare_play(s, p, cid, rock=1)
    go(s, ("act", "animals", 1))
    go(s, keys(s)[0])
    assert cid in p.zoo_cards
    assert s.break_pos == 3
    assert p.money == 100 - cards.card(cid)["cost"] + 3


def test_every_keyword_registered():
    for kw in ["SPRINT", "JUMPING", "INVENTIVE", "INVENTIVE_BEAR", "INVENTIVE_PRIMARY", "PACK",
               "PETTING_ZOO_ANIMAL", "ICONIC_ANIMAL", "FULL_THROATED", "PERCEPTION_4", "HUNTER",
               "SCAVENGING", "SNAPPING_1", "SNAPPING_2", "SPONSOR_MAGNET", "SUN_BATHING", "DIGGING",
               "POUCH", "RESISTANCE", "ASSERTION", "DOMINANCE"]:
        assert kw in abilities.ABILITIES, kw
