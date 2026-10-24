"""Sponsor cards that change core rules: 203, 215, 217, 218, 219, 221, 224, 227, 228, 229, 230, 253, 263."""
import pytest

import arknova  # noqa: F401
import arknova.sponsor_rules as SR
from arknova import abilities, cards, effects as E, engine, tables as T
from arknova.actions import animals, association, build, sponsors


def new(seed=1):
    state = engine.new_game(2, seed=seed)
    while state.stack[-1].kind == "setup_keep":
        engine.step(state, engine.legal_options(state)[0])
    for p in state.players:
        p.hand, p.money, p.appeal, p.xtokens, p.conservation, p.reputation = [], 100, 0, 0, 0, 4
        p.slots = ["animals", "build", "cards", "association", "sponsors"]
    state.display = [None] * T.DISPLAY_SIZE
    return state


@pytest.fixture(autouse=True)
def no_animal_abilities(monkeypatch):
    monkeypatch.setattr(abilities, "resolve", lambda state, p, card_id: None)


def keys(state):
    return [o.key for o in engine.legal_options(state)]


def own(state, p, *ids):
    state.players[p].zoo_cards.extend(ids)


def slot(p, action, n):
    p.slots.remove(action)
    p.slots.insert(n - 1, action)


def settle_to_turn(state):
    while state.stack[-1].kind not in ("turn",):
        engine.step(state, engine.legal_options(state)[0])


def enclosure(p, size):
    cells = p.zoo.legal_placements("enclosure", size)[0]
    return p.zoo.place("enclosure", size, cells)[0]


# animals without troublesome requirements (abilities are switched off above)
SMALL1, SMALL2, MID3, LARGE4, LARGE5_PZ = "445", "419", "443", "417", "441"  # 441 requires a Partner Zoo


# ---- 203 Veterinarian ------------------------------------------------------------------

def three_categories(state):
    own(state, 0, "445", "419", "511")  # herbivore, predator, bird
    state.base_projects = ["101"]  # Species Diversity: slot 3 needs 3 categories
    state.project_tokens = {"101": {}}


def project_keys(state, strength, side2=False):
    return [o.key for o in association._task_options(state, 0, strength, [], side2) if o.key[0] == "support"]


def test_veterinarian_project_task_costs_four():
    state = new()
    three_categories(state)
    assert project_keys(state, 4) == []
    own(state, 0, "203")
    assert SR.task_value(state.players[0], "project") == 4
    assert SR.task_value(state.players[0], "university") == T.TASK_VALUE["university"]
    assert project_keys(state, 4)
    assert project_keys(state, 3) == []


def test_veterinarian_leaves_more_budget_on_side_two():
    state = new()
    p = state.players[0]
    three_categories(state)
    own(state, 0, "203")
    p.upgraded.add("association")
    p.workers = 4
    slot(p, "association", 5)
    p.xtokens = 1  # strength 6
    engine.step(state, ("act", "association", 1))
    frame = state.stack[-1]
    key = next(k for k in keys(state) if k[0] == "support" and k[2] == 3)
    engine.step(state, key)
    assert frame.data["remaining"] == 2  # 6 - 4
    while state.stack[-1] is not frame:  # conservation 2 offers an upgrade or a worker
        engine.step(state, engine.legal_options(state)[0])
    assert ("reputation",) in keys(state)  # value 2 still fits


# ---- 215 / 218 Breeding Cooperation and Program --------------------------------------------

@pytest.mark.parametrize("card", ["215", "218"])
def test_breeding_cards_get_two_tokens_when_played(card):
    state = new()
    sponsors.play_sponsor(state, 0, card)
    assert state.players[0].card_tokens[card] == 2


@pytest.mark.parametrize("card", ["215", "218"])
def test_breeding_token_reaches_a_base_slot_one_icon_short(card):
    state = new()
    p = state.players[0]
    own(state, 0, "445", "419")  # two categories; slot 3 needs 3, slot 2 needs 4
    state.base_projects = ["101"]
    state.project_tokens = {"101": {}}
    assert project_keys(state, 5) == []
    own(state, 0, card)
    p.card_tokens[card] = 2
    ks = project_keys(state, 5)
    assert ks and {k[2] for k in ks} == {3} and all(k[4] == f"token:{card}" for k in ks)
    slot(p, "association", 5)
    engine.step(state, ("act", "association", 0))
    engine.step(state, ("support", "101", 3, 3, f"token:{card}"))
    assert p.card_tokens[card] == 1
    assert state.project_tokens["101"] == {3: 0}


def test_breeding_token_not_offered_when_the_slot_is_reachable_or_too_far():
    state = new()
    p = state.players[0]
    own(state, 0, "215", "218")
    p.card_tokens.update({"215": 2, "218": 2})
    state.base_projects = ["101"]
    state.project_tokens = {"101": {}}
    own(state, 0, "445")  # one category: slot 3 (needs 3) is two short
    assert project_keys(state, 5) == []
    own(state, 0, "419", "511")  # three categories: slot 3 is reachable, slot 2 (needs 4) one short
    ks = project_keys(state, 5)
    assert {k[2] for k in ks if len(k) == 4} == {3}  # slot 3: no token option
    assert {k[2] for k in ks if len(k) == 5} == {2}  # slot 2 only through a token


def test_breeding_tokens_from_both_cards_and_exhaustion():
    state = new()
    p = state.players[0]
    own(state, 0, "445", "419", "215", "218")
    p.card_tokens.update({"215": 1, "218": 0})
    state.base_projects = ["101"]
    state.project_tokens = {"101": {}}
    flags = {k[4] for k in project_keys(state, 5)}
    assert flags == {"token:215"}
    p.card_tokens["215"] = 0
    assert project_keys(state, 5) == []


def test_breeding_token_only_for_base_projects():
    state = new()
    p = state.players[0]
    own(state, 0, "215")
    p.card_tokens["215"] = 2
    own(state, 0, "445", "419", "417")  # 2 predators + 1 herbivore
    normal = next(c for c in cards.ids_of("project", category="normal"))
    state.base_projects = []
    state.projects = [normal]
    state.project_tokens = {normal: {}}
    assert not [k for k in project_keys(state, 5) if len(k) == 5]


@pytest.mark.parametrize("card", ["215", "218"])
def test_breeding_endgame(card):
    state = new()
    p = state.players[0]
    own(state, 0, card)
    p.tokens = [False] * 4 + [True] * 3
    E.ENDGAME[card](state, 0)
    assert p.conservation == 0
    p.tokens = [False] * 5 + [True] * 2
    E.ENDGAME[card](state, 0)
    assert p.conservation == 1


# ---- 217 Engineer ----------------------------------------------------------------------

def start_build(state, strength, side2=False):
    p = state.players[0]
    if side2:
        p.upgraded.add("build")
    slot(p, "build", strength)
    engine.step(state, ("act", "build", 0))


def bonus_free(state, key):
    mapdef = state.players[0].zoo.mapdef
    return not any(mapdef.cells[c].bonus for c in key[-1])


def build_keys(state, kind, size=None):
    return [k for k in keys(state) if k[0] == "build" and k[1] == kind and size in (None, k[2])
            and bonus_free(state, k)]


def test_engineer_builds_one_more_identical_building():
    state = new()
    p = state.players[0]
    own(state, 0, "217")
    start_build(state, 1)
    first = build_keys(state, "pavilion")[0]
    engine.step(state, first)
    assert state.stack[-1].kind == "act_build"
    ks = keys(state)
    extra = [k for k in ks if k[0] == "engineer" and bonus_free(state, k)]
    assert extra and all(k[1:3] == ("pavilion", 1) for k in extra) and ("done",) in ks
    assert not [k for k in ks if k[0] == "build"]  # side I: one regular building only
    engine.step(state, extra[0])
    assert state.stack[-1].kind != "act_build"
    assert [b.kind for b in p.zoo.buildings] == ["pavilion", "pavilion"]
    assert p.money == 100 - 4 and p.appeal == 2


def test_engineer_is_optional():
    state = new()
    own(state, 0, "217")
    start_build(state, 1)
    engine.step(state, build_keys(state, "pavilion")[0])
    engine.step(state, ("done",))
    assert state.stack[-1].kind != "act_build"
    assert len(state.players[0].zoo.buildings) == 1


def test_no_engineer_no_extra_building():
    state = new()
    start_build(state, 1)
    engine.step(state, build_keys(state, "pavilion")[0])
    assert state.stack[-1].kind != "act_build"
    assert len(state.players[0].zoo.buildings) == 1


def test_engineer_ignores_budget_and_identical_rule_on_side_two_but_only_once():
    state = new()
    p = state.players[0]
    own(state, 0, "217")
    start_build(state, 3, side2=True)
    engine.step(state, build_keys(state, "enclosure", 2)[0])
    engine.step(state, build_keys(state, "enclosure", 1)[0])
    ks = keys(state)
    assert not [k for k in ks if k[0] == "build"]  # budget used up
    extra = [k for k in ks if k[0] == "engineer"]
    assert {k[1:3] for k in extra} == {("enclosure", 2), ("enclosure", 1)}
    money = p.money
    engine.step(state, next(k for k in extra if k[2] == 2 and bonus_free(state, k)))
    assert p.money == money - 4
    assert state.stack[-1].kind != "act_build"  # once per action
    assert sorted(b.size for b in p.zoo.buildings) == [1, 2, 2]


def test_engineer_cannot_copy_a_special_enclosure():
    state = new()
    own(state, 0, "217")
    start_build(state, 3)
    key = build_keys(state, "petting_zoo")[0]
    engine.step(state, key)
    assert state.stack[-1].kind != "act_build"
    assert len(state.players[0].zoo.buildings) == 1


def test_engineer_needs_the_money():
    state = new()
    p = state.players[0]
    own(state, 0, "217")
    p.money = 2
    start_build(state, 1)
    engine.step(state, build_keys(state, "pavilion")[0])
    assert p.money == 0 and state.stack[-1].kind != "act_build"


# ---- 219 Diversity Researcher ------------------------------------------------------------

def test_diversity_researcher_may_build_on_water_and_rock():
    state = new()
    p = state.players[0]
    zoo = p.zoo
    water_corner = frozenset({(0, 0)})
    assert water_corner not in zoo.legal_placements("pavilion", 1)
    assert water_corner in zoo.legal_placements("pavilion", 1, any_terrain=True)
    # rock / water requirements of unique buildings are dropped too
    plain = zoo.legal_placements("pavilion", 1, need_rock=2)
    assert plain == []
    assert zoo.legal_placements("pavilion", 1, need_rock=2, any_terrain=True)
    # the build action offers it only to the owner
    start_build(state, 1)
    assert ("build", "pavilion", 1, ((0, 0),)) not in keys(state)
    state = new()
    own(state, 0, "219")
    start_build(state, 1)
    assert ("build", "pavilion", 1, ((0, 0),)) in keys(state)
    engine.step(state, ("build", "pavilion", 1, ((0, 0),)))
    assert not state.players[0].zoo.is_fully_covered()


def test_diversity_researcher_ignores_enclosure_terrain_requirements():
    state = new()
    p = state.players[0]
    water_animal = "511"  # size 3, needs 1 water
    cells = next(c for c in p.zoo.legal_placements("enclosure", 3) if p.zoo.adjacent_terrain(c, "water") == 0)
    p.zoo.place("enclosure", 3, cells)
    assert animals.housings(p, water_animal) == []
    own(state, 0, "219")
    assert animals.housings(p, water_animal) == [(0, 0)]


def test_diversity_researcher_immediate_money_per_water_and_rock_icon():
    state = new()
    p = state.players[0]
    own(state, 0, "241", "242", "511")  # water, rock, an animal needing 1 water -> 3 icons
    money = p.money
    sponsors.play_sponsor(state, 0, "219")
    icons = cards.icons(p)
    assert icons.get("water", 0) + icons.get("rock", 0) == 3
    assert p.money == money + 6


def test_ignores_terrain_helper():
    state = new()
    p = state.players[0]
    assert not SR.ignores_terrain(p)
    own(state, 0, "219")
    assert SR.ignores_terrain(p)


# ---- 221 Archaeologist -------------------------------------------------------------------

def place(state, cell, kind="pavilion"):
    E.place_building(state, 0, kind, 1, frozenset({cell}))


def test_archaeologist_doubles_a_border_placement_bonus():
    state = new()
    p = state.players[0]
    place(state, (8, -1))  # border, money 5
    assert p.money == 105
    state = new()
    own(state, 0, "221")
    place(state, (8, -1))
    assert state.players[0].money == 110


def test_archaeologist_ignores_non_border_bonuses():
    state = new()
    own(state, 0, "221")
    place(state, (7, -3))  # money 5, not a border space
    assert state.players[0].money == 105


def test_archaeologist_repeats_other_bonus_kinds():
    state = new()
    own(state, 0, "221")
    place(state, (4, -2))  # border space with an X-token
    assert state.players[0].xtokens == 2


def test_archaeologist_only_for_its_owner():
    state = new()
    own(state, 1, "221")
    place(state, (8, -1))
    assert state.players[0].money == 105


# ---- 224 Migration Recording (the full flow is in test_release.py) ------------------------

def test_migration_recording_bonus_helper():
    state = new()
    SR.release_bonus(state, 0)
    assert state.players[0].conservation == 0
    own(state, 0, "224")
    SR.release_bonus(state, 0)
    assert state.players[0].conservation == 1


# ---- 227 Waza Special Assignment --------------------------------------------------------

def play_waza(state, kind):
    sponsors.play_sponsor(state, 0, "227")
    assert state.stack[-1].kind == "waza_kind"
    assert {k[1] for k in keys(state)} == {"small", "large"}
    engine.step(state, ("kind", kind))


def test_waza_special_assignment_takes_the_first_small_animal():
    state = new()
    state.deck = ["204", "203", SMALL1, MID3, LARGE4]  # popped from the right
    play_waza(state, "small")
    p = state.players[0]
    assert p.card_tokens["227"] == "small"
    assert p.hand == [SMALL1]  # LARGE4 and MID3 are not small
    assert state.discard[-2:] == [LARGE4, MID3]
    assert state.deck == ["204", "203"]


def test_waza_special_assignment_large():
    state = new()
    state.deck = ["204", LARGE5_PZ, SMALL1, "203"]
    play_waza(state, "large")
    assert state.players[0].hand == [LARGE5_PZ]
    assert set(state.discard[-2:]) == {"203", SMALL1}


def test_waza_special_assignment_reshuffles_once_then_stops():
    state = new()
    state.deck, state.discard = [], ["203", SMALL1, "204"]
    play_waza(state, "small")
    assert state.players[0].hand == [SMALL1]
    assert sorted(state.discard + state.deck) == sorted(["203", "204"])
    state = new()
    state.deck, state.discard = ["203"], ["204", LARGE4]
    play_waza(state, "small")  # no small animal anywhere: everything is revealed once
    assert state.players[0].hand == []
    assert state.deck == [] and sorted(state.discard) == sorted(["203", "204", LARGE4])
    state = new()
    state.deck, state.discard = [], []
    play_waza(state, "large")
    assert state.players[0].hand == []


def animals_turn(state, hand, size_for_enclosures):
    p = state.players[0]
    p.hand = list(hand)
    for size in size_for_enclosures:
        enclosure(p, size)
    slot(p, "animals", 2)
    return p


def test_waza_special_assignment_forbids_the_other_kind_and_pays_appeal():
    state = new()
    p = animals_turn(state, [SMALL1, MID3, LARGE4], [1, 3, 4])
    own(state, 0, "227")
    p.card_tokens["227"] = "large"
    engine.step(state, ("act", "animals", 0))
    ks = keys(state)
    assert [k for k in ks if k[:2] == ("play", LARGE4)]
    assert [k for k in ks if k[:2] == ("play", MID3)]  # size 3 is neither small nor large
    assert not [k for k in ks if k[:2] == ("play", SMALL1)]
    appeal = p.appeal
    engine.step(state, next(k for k in ks if k[:2] == ("play", LARGE4)))
    assert p.appeal == appeal + cards.card(LARGE4)["appeal"] + 4


def test_waza_special_assignment_small_pays_two_appeal():
    state = new()
    p = animals_turn(state, [SMALL1, LARGE4], [1, 4])
    own(state, 0, "227")
    p.card_tokens["227"] = "small"
    engine.step(state, ("act", "animals", 0))
    ks = keys(state)
    assert not [k for k in ks if k[:2] == ("play", LARGE4)]
    engine.step(state, next(k for k in ks if k[:2] == ("play", SMALL1)))
    assert p.appeal == cards.card(SMALL1)["appeal"] + 2


def test_waza_no_restriction_before_the_choice_is_made():
    state = new()
    p = animals_turn(state, [SMALL1, LARGE4], [1, 4])
    own(state, 0, "227")
    assert SR.animal_allowed(p, SMALL1) and SR.animal_allowed(p, LARGE4)


# ---- 228 Waza Small Animals Program ------------------------------------------------------

def small_program(state, hand, enclosures, display=()):
    p = animals_turn(state, hand, enclosures)
    own(state, 0, "228")
    for i, c in enumerate(display):
        state.display[i] = c
    p.reputation = 4  # folders 1-3
    return p


def test_waza_small_program_extra_small_animal_then_display_take():
    state = new()
    p = small_program(state, [SMALL1, SMALL2, MID3], [1, 2, 3], display=[LARGE4, "203", SMALL1.replace("445", "420")])
    engine.step(state, ("act", "animals", 0))
    engine.step(state, ("play", SMALL1, next(k for k in keys(state) if k[:2] == ("play", SMALL1))[2]))
    # the action's single play is done; the program offers one further small animal
    assert state.stack[-1].kind == "act_animals" and state.stack[-1].data["phase"] == "bonus"
    ks = keys(state)
    assert {k[1] for k in ks if k[0] == "play"} == {SMALL2}  # not the size-3 animal
    assert ("done",) in ks
    money = p.money
    engine.step(state, next(k for k in ks if k[0] == "play"))
    assert p.money == money - cards.card(SMALL2)["cost"]
    assert state.stack[-1].data["phase"] == "take"
    takes = keys(state)
    assert takes == [("take_small", 2)]  # only the small animal in the display, within reputation range
    engine.step(state, ("take_small", 2))
    assert state.stack[-1].kind != "act_animals"
    assert "420" in p.hand


def test_waza_small_program_display_choice_and_declined_play():
    state = new()
    p = small_program(state, [SMALL1], [1], display=["420", "403", "412"])
    state.display[1] = SMALL2
    engine.step(state, ("act", "animals", 0))
    engine.step(state, next(k for k in keys(state) if k[:2] == ("play", SMALL1)))
    # no second small animal in hand: straight to the display take, with a choice
    assert state.stack[-1].data["phase"] == "take"
    assert {k[1] for k in keys(state)} == {0, 1}
    engine.step(state, ("take_small", 1))
    assert SMALL2 in p.hand and state.stack[-1].kind != "act_animals"


def test_waza_small_program_decline_the_extra_play_still_takes():
    state = new()
    p = small_program(state, [SMALL1, SMALL2], [1, 2], display=["420"])
    engine.step(state, ("act", "animals", 0))
    engine.step(state, next(k for k in keys(state) if k[:2] == ("play", SMALL1)))
    assert state.stack[-1].data["phase"] == "bonus"
    engine.step(state, ("done",))
    assert state.stack[-1].data["phase"] == "take"
    engine.step(state, ("take_small", 0))
    assert state.stack[-1].kind != "act_animals" and p.hand == [SMALL2, "420"]


def test_waza_small_program_needs_only_small_animals():
    state = new()
    p = small_program(state, [MID3, SMALL2], [3, 2], display=["420"])
    engine.step(state, ("act", "animals", 0))
    engine.step(state, next(k for k in keys(state) if k[:2] == ("play", MID3)))
    assert state.stack[-1].kind != "act_animals"  # a size-3 animal ends it: no bonus, no take
    assert state.display[0] == "420"


def test_waza_small_program_requires_having_played():
    state = new()
    small_program(state, [SMALL2], [1], display=["420"])  # enclosure too small: nothing playable
    assert ("act", "animals", 0) not in keys(state)


def test_waza_small_program_without_the_card_nothing_extra():
    state = new()
    p = animals_turn(state, [SMALL1, SMALL2], [1, 2])
    state.display[0] = "420"
    p.reputation = 4
    engine.step(state, ("act", "animals", 0))
    engine.step(state, next(k for k in keys(state) if k[:2] == ("play", SMALL1)))
    assert state.stack[-1].kind != "act_animals"


def test_waza_small_program_no_small_in_display_ends_after_the_extra_play():
    state = new()
    small_program(state, [SMALL1, SMALL2], [1, 2], display=[LARGE4])
    engine.step(state, ("act", "animals", 0))
    engine.step(state, next(k for k in keys(state) if k[:2] == ("play", SMALL1)))
    engine.step(state, next(k for k in keys(state) if k[:2] == ("play", SMALL2)))
    assert state.stack[-1].kind != "act_animals"


# ---- 229 / 230 Experts ---------------------------------------------------------------------

def cost_of(state, card_id):
    p = state.players[0]
    return animals._cost(p, card_id)


def test_expert_in_small_animals():
    state = new()
    base = cost_of(state, SMALL1)
    own(state, 0, "229")
    assert cost_of(state, SMALL1) == max(0, base - 3)
    assert cost_of(state, SMALL2) == max(0, cards.card(SMALL2)["cost"] - 3)
    assert cost_of(state, LARGE4) == cards.card(LARGE4)["cost"]
    assert cost_of(state, MID3) == cards.card(MID3)["cost"]


def test_expert_in_large_animals():
    state = new()
    own(state, 0, "230")
    assert cost_of(state, LARGE4) == cards.card(LARGE4)["cost"] - 4
    assert cost_of(state, SMALL1) == cards.card(SMALL1)["cost"]
    assert cost_of(state, MID3) == cards.card(MID3)["cost"]


def test_expert_cost_never_below_zero_and_stacks_with_partner_zoo():
    state = new()
    p = state.players[0]
    own(state, 0, "229")
    p.partner_zoos = ["europe"]
    assert cards.card("420")["cost"] == 4  # Stoat: 4 - 3 (partner zoo) - 3 (expert) clamps at 0
    assert cost_of(state, "420") == 0
    p.partner_zoos = []
    cid = next(c["id"] for c in cards.all_cards().values() if c["type"] == "animal" and c["size"] <= 2
               and c["cost"] >= 10 and cards.animal_continents(c["id"]))
    base = cost_of(state, cid)
    p.partner_zoos = [cards.animal_continents(cid)[0]]
    assert cost_of(state, cid) == max(0, base - 3)


def test_expert_discount_is_paid_in_play():
    state = new()
    p = animals_turn(state, [LARGE4], [4])
    own(state, 0, "230")
    engine.step(state, ("act", "animals", 0))
    money = p.money
    engine.step(state, next(k for k in keys(state) if k[0] == "play"))
    assert p.money == money - (cards.card(LARGE4)["cost"] - 4)


def test_expert_discount_applies_on_top_of_the_display_folder_cost():
    state = new()
    p = state.players[0]
    p.upgraded.add("animals")
    enclosure(p, 4)
    own(state, 0, "230")
    state.display[1] = LARGE4
    slot(p, "animals", 2)
    engine.step(state, ("act", "animals", 0))
    money = p.money
    engine.step(state, next(k for k in keys(state) if k[0] == "play_display"))
    assert p.money == money - (cards.card(LARGE4)["cost"] - 4) - 2


# ---- 253 Okapi Stable ----------------------------------------------------------------------

def okapi_game():
    state = new()
    state.players[0].hand = ["203"]  # Veterinarian: level 4, no conditions, no immediate effect
    return state


def play_okapi(state):
    sponsors.play_sponsor(state, 0, "253")
    # the unique building comes first (it was pushed last), then the Okapi offer
    assert state.stack[-1].kind == "sponsor_building"
    mapdef = state.players[0].zoo.mapdef
    engine.step(state, next(k for k in keys(state) if not any(mapdef.cells[c].bonus for c in k[1])))


def test_okapi_stable_tokens_and_offer_on_its_own_herbivore_icon():
    state = okapi_game()
    p = state.players[0]
    play_okapi(state)
    assert p.card_tokens["253"] == 3
    assert state.stack[-1].kind == "okapi_stable"
    assert ("yes",) in keys(state) and ("no",) in keys(state)
    money = p.money
    engine.step(state, ("yes",))
    assert p.card_tokens["253"] == 2
    assert state.stack[-1].kind == "paid_sponsor"
    engine.step(state, ("play", "203"))
    assert p.money == money - 4 and "203" in p.zoo_cards and "203" not in p.hand


def test_okapi_stable_no_keeps_the_token():
    state = okapi_game()
    play_okapi(state)
    engine.step(state, ("no",))
    assert state.players[0].card_tokens["253"] == 3
    assert state.stack[-1].kind == "turn" or not any(f.kind in ("okapi_stable", "paid_sponsor") for f in state.stack)


def test_okapi_stable_triggers_on_later_herbivore_icons_only_for_the_owner():
    state = new()
    p = state.players[0]
    own(state, 0, "253")
    p.card_tokens["253"] = 3
    p.hand = ["203"]
    E.icons_played(state, 1, {"herbivore": 1}, {})
    assert state.stack[-1].kind == "turn"
    E.icons_played(state, 0, {"predator": 1}, {})
    assert state.stack[-1].kind == "turn"
    E.icons_played(state, 0, {"herbivore": 1}, {"herbivore": 1})  # a repeated icon still counts
    assert state.stack[-1].kind == "okapi_stable"


def test_okapi_stable_no_offer_without_tokens_or_a_playable_sponsor():
    state = new()
    p = state.players[0]
    own(state, 0, "253")
    p.card_tokens["253"] = 0
    p.hand = ["203"]
    E.icons_played(state, 0, {"herbivore": 1}, {})
    assert state.stack[-1].kind == "turn"
    p.card_tokens["253"] = 1
    p.hand = []
    E.icons_played(state, 0, {"herbivore": 1}, {})
    assert state.stack[-1].kind == "turn"
    p.hand = ["203"]
    p.money = 3  # cannot pay the level
    E.icons_played(state, 0, {"herbivore": 1}, {})
    assert state.stack[-1].kind == "turn"


def test_okapi_stable_offered_when_an_herbivore_animal_is_played():
    state = new()
    p = animals_turn(state, [SMALL1], [1])  # herbivore, europe
    own(state, 0, "253")
    p.card_tokens["253"] = 3
    p.hand.append("203")
    engine.step(state, ("act", "animals", 0))
    engine.step(state, next(k for k in keys(state) if k[:2] == ("play", SMALL1)))
    assert state.stack[-1].kind == "okapi_stable"


# ---- 263 Waza Large Animal Program -----------------------------------------------------------

def test_waza_large_program_ignores_one_condition_for_large_animals():
    state = new()
    p = animals_turn(state, [LARGE5_PZ], [5])  # needs a Partner Zoo
    assert cards.unmet_requirements(p, LARGE5_PZ) == 1
    assert animals._plays(state, 0) == []
    own(state, 0, "263")
    assert [m[1] for m in animals._plays(state, 0)] == [LARGE5_PZ]


def test_waza_large_program_not_for_small_animals_or_two_missing_conditions():
    state = new()
    p = animals_turn(state, [], [])
    own(state, 0, "263")
    small_with_condition = next(c["id"] for c in cards.all_cards().values()
                                if c["type"] == "animal" and c["size"] <= 2 and cards.unmet_requirements(p, c["id"]) == 1)
    large_two_conditions = next(c["id"] for c in cards.all_cards().values()
                                if c["type"] == "animal" and c["size"] >= 4 and cards.unmet_requirements(p, c["id"]) == 2)
    assert not SR.requirements_ok(p, small_with_condition)
    assert not SR.requirements_ok(p, large_two_conditions)
    mid = next(c["id"] for c in cards.all_cards().values()
               if c["type"] == "animal" and c["size"] == 3 and cards.unmet_requirements(p, c["id"]) == 1)
    assert not SR.requirements_ok(p, mid)


def test_waza_large_program_immediate_free_five_space_enclosure():
    state = new()
    p = state.players[0]
    money = p.money
    sponsors.play_sponsor(state, 0, "263")
    assert state.stack[-1].kind == "free_build"
    ks = keys(state)
    assert ("skip",) in ks
    place = next(k for k in ks if k[0] == "place")
    assert place[1:3] == ("enclosure", 5)
    engine.step(state, place)
    assert [b.size for b in p.zoo.buildings] == [5] and p.money == money
