import copy

import pytest

import arknova.abilities_action  # noqa: F401  (registers the keywords)
from arknova import abilities, cards, effects as E, engine, tables as T

KEYWORDS = """CLEVER BOOST_ANIMAL BOOST_ASSOCIATION BOOST_BUILDING BOOST_CARD BOOST_SPONSORS
MULTIPLIER_ASSOCIATION MULTIPLIER_BUILDING MULTIPLIER_CARD MULTIPLIER_SPONSORS
ACTION_ASSOCIATION ACTION_BUILDING ACTION_CARDS ACTION_SPONSORS DETERMINATION POSTURING PEACOCKING
VENOM CONSTRICTION PILFERING_1 PILFERING_2 HYPNOSIS""".split()

# Cards used end to end (ids from data/cards.json).
CLEVER, BOOST_ANIMAL, BOOST_BUILDING, BOOST_SPONSORS = "405", "419", "502", "428"
ACTION_CARDS, DETERMINATION, MULTIPLIER_SPONSORS = "453", "505", "434"
VENOM_2, CONSTRICTION, HYPNOSIS_3 = "470", "474", "485"
PILFERING_1, PILFERING_2 = "456", "458"
POSTURING_2, PEACOCKING = "501", "514"

HAND = cards.ids_of("sponsor")[:3]  # any cards: they are only moved around
OTHER_ACTIONS = ["animals", "build", "cards", "association", "sponsors"]


@pytest.fixture(autouse=True)
def no_requirements(monkeypatch):
    """The test cards have play conditions (icons, partner zoos); these tests are about abilities."""
    monkeypatch.setattr(cards, "unmet_requirements", lambda player, card_id: 0)


# ---- helpers ----------------------------------------------------------------

def new(n=2, seed=3):
    s = engine.new_game(n, seed=seed)
    while s.stack[-1].kind == "setup_keep":
        engine.step(s, engine.legal_options(s)[0])
    for q in s.players:
        q.hand, q.money, q.appeal, q.conservation = [], 100, 0, 0
        q.slots = ["cards", "build", "animals", "association", "sponsors"]
    return s


def ctx(s):
    """The scratch a running animals action would have, for calling abilities directly."""
    s.turn = {"action": "animals", "after": [], "xtoken": False, "strength": 5}
    return s


def keys(s):
    return [o.key for o in engine.legal_options(s)]


def top(s):
    return s.stack[-1]


def enclosure_for(p, card_id):
    enc = cards.card(card_id)["enclosure"]
    size = enc["standard_size"]
    for cells in p.zoo.legal_placements("enclosure", size):
        if (p.zoo.adjacent_terrain(cells, "rock") >= enc["rock"]
                and p.zoo.adjacent_terrain(cells, "water") >= enc["water"]):
            return p.zoo.place("enclosure", size, cells)[0].id
    raise AssertionError("no placement")


def play(s, card_id):
    """Player 0 plays the animal through a real Animals action (animals on slot 3)."""
    p = s.players[0]
    assert top(s).kind == "turn" and top(s).player == 0
    p.hand = [card_id]
    building = enclosure_for(p, card_id)
    engine.step(s, ("act", "animals", 0))
    engine.step(s, ("play", card_id, building))
    return p


def drive(s, until="turn", pick=0):
    """Take the first option of every frame until the top one is `until`."""
    for _ in range(100):
        if top(s).kind == until:
            return s
        engine.step(s, engine.legal_options(s)[pick])
    raise AssertionError("did not settle")


def is_turn_of(s, q):
    return top(s).kind == "turn" and top(s).player == q


def make_leader(s, q, appeal=50, conservation=0):
    s.players[q].appeal, s.players[q].conservation = appeal, conservation


# ---- registry ----------------------------------------------------------------

def test_every_keyword_is_registered():
    for keyword in KEYWORDS:
        assert keyword in abilities.ABILITIES, keyword
    used = {a["keyword"] for c in cards.all_cards().values() for a in c.get("abilities", [])}
    assert set(KEYWORDS) <= used


# ---- Clever and Boost ----------------------------------------------------------

def test_clever_queues_the_existing_frame():
    s = ctx(new())
    abilities.ABILITIES["CLEVER"](s, 0, CLEVER, None)
    assert s.turn["after"] == [("clever", 0, {})]
    assert not [f for f in s.stack if f.kind == "clever"]


def test_clever_end_to_end():
    s = new()
    p = play(s, CLEVER)
    assert p.slots == ["animals", "cards", "build", "association", "sponsors"]
    assert top(s).kind == "clever" and top(s).player == 0
    assert set(keys(s)) == {("clever", a) for a in p.slots[1:]} | {("skip",)}
    engine.step(s, ("clever", "sponsors"))
    assert p.slots == ["sponsors", "animals", "cards", "build", "association"]
    assert is_turn_of(s, 1)


def test_clever_can_be_skipped():
    s = new()
    p = play(s, CLEVER)
    engine.step(s, ("skip",))
    assert p.slots[0] == "animals" and is_turn_of(s, 1)


@pytest.mark.parametrize("keyword,action", [
    ("BOOST_ANIMAL", "animals"), ("BOOST_ASSOCIATION", "association"), ("BOOST_BUILDING", "build"),
    ("BOOST_CARD", "cards"), ("BOOST_SPONSORS", "sponsors")])
def test_boost_queues_a_frame_for_its_action(keyword, action):
    s = ctx(new())
    abilities.ABILITIES[keyword](s, 0, "x", None)
    assert s.turn["after"] == [("ab_boost", 0, {"action": action})]


def test_boost_end_to_end_slot_5_and_slot_1():
    s = new()
    p = play(s, BOOST_BUILDING)
    assert top(s).kind == "ab_boost"
    assert keys(s) == [("boost", 1), ("boost", 5), ("skip",)]
    other = copy.deepcopy(s)
    engine.step(s, ("boost", 5))
    assert s.players[0].slots == ["animals", "cards", "association", "sponsors", "build"]
    assert is_turn_of(s, 1)
    engine.step(other, ("boost", 1))
    assert other.players[0].slots == ["build", "animals", "cards", "association", "sponsors"]
    assert p.slots[0] == "animals"  # the original state was not touched


def test_boost_animal_can_sink_the_animals_card_and_sponsors_can_rise():
    s = new()
    p = play(s, BOOST_ANIMAL)
    engine.step(s, ("boost", 5))
    assert p.slots[-1] == "animals"
    s = new()
    p = play(s, BOOST_SPONSORS)
    engine.step(s, ("boost", 1))
    assert p.slots[0] == "sponsors"


def test_boost_skip_changes_nothing():
    s = new()
    p = play(s, BOOST_BUILDING)
    engine.step(s, ("skip",))
    assert p.slots == ["animals", "cards", "build", "association", "sponsors"]


# ---- Multiplier -----------------------------------------------------------------

@pytest.mark.parametrize("keyword,action", [
    ("MULTIPLIER_ASSOCIATION", "association"), ("MULTIPLIER_BUILDING", "build"),
    ("MULTIPLIER_CARD", "cards"), ("MULTIPLIER_SPONSORS", "sponsors")])
def test_multiplier_places_a_token_immediately(keyword, action):
    s = ctx(new())
    abilities.ABILITIES[keyword](s, 0, "x", None)
    assert E.tokens_on(s, 0, action) == ["multiplier"]
    assert s.turn["after"] == []
    abilities.ABILITIES[keyword](s, 0, "x", None)
    assert E.tokens_on(s, 0, action) == ["multiplier", "multiplier"]


def test_multiplier_lets_the_action_run_twice_later():
    s = new()
    s.players[0].slots = ["cards", "sponsors", "animals", "build", "association"]
    p = play(s, MULTIPLIER_SPONSORS)
    assert E.tokens_on(s, 0, "sponsors") == ["multiplier"]
    assert is_turn_of(s, 1)
    engine.step(s, ("xtoken", s.players[1].slots[0]))
    assert is_turn_of(s, 0)
    strength = p.strength("sponsors")
    assert strength == 3
    money = p.money
    engine.step(s, ("act", "sponsors", 0))
    engine.step(s, ("break",))
    assert top(s).kind == "multiplier_repeat"
    assert E.tokens_on(s, 0, "sponsors") == []
    engine.step(s, ("repeat",))
    engine.step(s, ("break",))
    assert p.money == money + 2 * strength
    assert is_turn_of(s, 1)
    assert p.slots[0] == "sponsors"


def test_multiplier_repeat_can_be_declined():
    s = new()
    s.players[0].slots = ["cards", "sponsors", "animals", "build", "association"]
    p = play(s, MULTIPLIER_SPONSORS)
    engine.step(s, ("xtoken", s.players[1].slots[0]))
    strength, money = p.strength("sponsors"), p.money
    engine.step(s, ("act", "sponsors", 0))
    engine.step(s, ("break",))
    engine.step(s, ("skip",))
    assert p.money == money + strength
    assert E.tokens_on(s, 0, "sponsors") == []
    assert is_turn_of(s, 1)


# ---- Action: X and Determination --------------------------------------------------

@pytest.mark.parametrize("keyword,action", [
    ("ACTION_ASSOCIATION", "association"), ("ACTION_BUILDING", "build"),
    ("ACTION_CARDS", "cards"), ("ACTION_SPONSORS", "sponsors")])
def test_action_x_offers_an_extra_action(keyword, action):
    s = ctx(new())
    abilities.ABILITIES[keyword](s, 0, "x", None)
    assert s.turn["after"] == [("extra_action", 0, {"actions": [action], "owner": 0, "optional": True})]


def test_action_cards_end_to_end():
    s = new()
    p = play(s, ACTION_CARDS)
    assert top(s).kind == "extra_action" and top(s).player == 0
    assert keys(s) == [("act", "cards", 0), ("skip",)]
    engine.step(s, ("act", "cards", 0))
    assert top(s).kind == "act_cards"
    assert top(s).data["draw"] == 1  # cards sits on slot 2 after the animals card moved up
    drive(s)
    assert len(p.hand) == 1
    assert p.slots == ["cards", "animals", "build", "association", "sponsors"]
    assert is_turn_of(s, 1)


def test_action_x_can_be_skipped():
    s = new()
    p = play(s, ACTION_CARDS)
    engine.step(s, ("skip",))
    assert p.slots[0] == "animals" and is_turn_of(s, 1)


def test_determination_direct():
    s = ctx(new())
    abilities.ABILITIES["DETERMINATION"](s, 0, "x", None)
    assert s.turn["after"] == [("extra_action", 0, {"actions": OTHER_ACTIONS, "owner": 0, "optional": False})]


def test_determination_end_to_end():
    s = new()
    s.players[0].upgraded.add("animals")
    p = play(s, DETERMINATION)
    assert top(s).kind == "extra_action"
    options = keys(s)
    assert ("skip",) not in options
    assert {k[1] for k in options} >= {"cards", "sponsors"}
    engine.step(s, ("act", "sponsors", 0))
    engine.step(s, ("break",))
    assert p.slots[0] == "sponsors" and p.slots[1] == "animals"
    assert is_turn_of(s, 1)


# ---- Posturing and Peacocking -------------------------------------------------------

def test_posturing_pushes_n_skippable_frames():
    s = ctx(new())
    before = len(s.stack)
    abilities.ABILITIES["POSTURING"](s, 0, "x", 3)
    frames = s.stack[before:]
    assert [f.kind for f in frames] == ["free_build"] * 3
    assert all(f.data["kinds"] == [("kiosk", 1), ("pavilion", 1)] for f in frames)
    assert ("skip",) in keys(s)


def test_posturing_end_to_end_place_one_and_skip_the_rest():
    s = new()
    p = play(s, POSTURING_2)
    assert [f.kind for f in s.stack[-2:]] == ["free_build", "free_build"]
    placements = [k for k in keys(s) if k[0] == "place"]
    kiosk = next(k for k in placements if k[1] == "kiosk")
    engine.step(s, kiosk)
    assert p.zoo.count("kiosk") == 1
    assert top(s).kind == "free_build"
    engine.step(s, ("skip",))
    assert is_turn_of(s, 1)
    assert p.zoo.count("pavilion") == 0


def test_posturing_pavilion_gives_appeal():
    s = new()
    p = play(s, POSTURING_2)
    appeal = p.appeal
    engine.step(s, next(k for k in keys(s) if k[0] == "place" and k[1] == "pavilion"))
    assert p.appeal == appeal + 1


def test_peacocking_offers_a_free_aviary():
    s = new()
    p = play(s, PEACOCKING)
    assert top(s).kind == "free_build" and top(s).data["kinds"] == [("aviary", 5)]
    place = next(k for k in keys(s) if k[0] == "place")
    money = p.money
    engine.step(s, place)
    assert p.zoo.count("aviary") == 1 and p.money == money
    drive(s)  # the aviary may sit on a placement bonus
    assert is_turn_of(s, 1)


def test_peacocking_can_be_skipped():
    s = new()
    p = play(s, PEACOCKING)
    engine.step(s, ("skip",))
    assert p.zoo.count("aviary") == 0


# ---- Venom ------------------------------------------------------------------------

def test_venom_goes_on_slots_from_the_top_and_skips_held_tokens():
    s = ctx(new())
    make_leader(s, 1)
    v = s.players[1]
    abilities.ABILITIES["VENOM"](s, 0, "x", 2)
    assert v.action_tokens == {v.slots[0]: ["venom"], v.slots[1]: ["venom"]}
    abilities.ABILITIES["VENOM"](s, 0, "x", 2)  # skips the two that hold one
    assert set(v.action_tokens) == set(v.slots[:4])
    assert all(t == ["venom"] for t in v.action_tokens.values())


def test_venom_ignores_players_not_ahead_unprotected_and_the_user():
    s = ctx(new(3))
    s.players[0].appeal = 10
    s.players[1].appeal = 10  # equal: not ahead
    s.players[2].appeal = 11
    s.players[2].zoo_cards = ["225"]  # Quarantine Lab
    abilities.ABILITIES["VENOM"](s, 0, "x", 1)
    assert all(not q.action_tokens for q in s.players)
    s.players[2].zoo_cards = []
    abilities.ABILITIES["VENOM"](s, 0, "x", 1)
    assert s.players[2].action_tokens and not s.players[0].action_tokens and not s.players[1].action_tokens


def test_venom_appeal_threshold_is_five():
    s = ctx(new())
    make_leader(s, 1, appeal=4)
    abilities.ABILITIES["VENOM"](s, 0, "x", 1)
    assert not s.players[1].action_tokens
    make_leader(s, 1, appeal=5)
    abilities.ABILITIES["VENOM"](s, 0, "x", 1)
    assert s.players[1].action_tokens


def test_venom_hits_every_player_ahead():
    s = ctx(new(3))
    make_leader(s, 1, 20)
    make_leader(s, 2, 30)
    abilities.ABILITIES["VENOM"](s, 0, "x", 1)
    assert s.players[1].action_tokens and s.players[2].action_tokens


def test_venom_end_to_end_costs_money_until_the_token_card_is_used():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    v.slots = ["build", "association", "cards", "sponsors", "animals"]
    play(s, VENOM_2)
    assert v.action_tokens == {"build": ["venom"], "association": ["venom"]}
    assert is_turn_of(s, 1)
    paid = copy.deepcopy(s)
    free = copy.deepcopy(s)
    # A card without a token costs 2 money.
    engine.step(paid, ("act", "cards", 0))
    assert paid.players[1].money == 100 - E.VENOM_COST
    assert paid.players[1].action_tokens == {"build": ["venom"], "association": ["venom"]}
    # A card with a token is free and loses the token (here via the X-token action, so it always works).
    engine.step(free, ("xtoken", "build"))
    assert free.players[1].money == 100
    assert free.players[1].action_tokens == {"association": ["venom"]}


def test_venom_free_once_every_token_is_gone():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    play(s, VENOM_2)  # tokens on v's slots 1 and 2: cards, build
    assert set(v.action_tokens) == {"cards", "build"}
    engine.step(s, ("xtoken", "cards"))
    engine.step(s, ("xtoken", "animals"))  # player 0 takes an X-token; nothing to do with Venom
    assert is_turn_of(s, 1) and set(v.action_tokens) == {"build"} and v.money == 100
    engine.step(s, ("xtoken", "build"))
    assert v.action_tokens == {} and v.money == 100 and not E.has_venom(s, 1)
    engine.step(s, ("xtoken", "animals"))
    engine.step(s, ("act", "cards", 0))
    assert v.money == 100  # no tokens left: using a card is free again


# ---- Constriction ---------------------------------------------------------------------

def test_constriction_counts_tracks_and_places_from_slot_5_up():
    s = ctx(new(3))
    make_leader(s, 1, appeal=50, conservation=4)
    make_leader(s, 2, appeal=50, conservation=0)
    s.players[0].appeal, s.players[0].conservation = 10, 2
    abilities.ABILITIES["CONSTRICTION"](s, 0, "x", None)
    a, b = s.players[1], s.players[2]
    assert a.action_tokens == {a.slots[4]: ["constriction"], a.slots[3]: ["constriction"]}
    assert b.action_tokens == {b.slots[4]: ["constriction"]}
    abilities.ABILITIES["CONSTRICTION"](s, 0, "x", None)  # skips cards that already hold one
    assert set(b.action_tokens) == {b.slots[4], b.slots[3]}
    assert set(a.action_tokens) == set(a.slots[1:])


def test_constriction_conservation_only_and_protection():
    s = ctx(new())
    s.players[0].appeal = 60
    make_leader(s, 1, appeal=10, conservation=3)
    abilities.ABILITIES["CONSTRICTION"](s, 0, "x", None)
    assert s.players[1].action_tokens == {s.players[1].slots[4]: ["constriction"]}
    s2 = ctx(new())
    make_leader(s2, 1, appeal=50)
    s2.players[1].zoo_cards = ["225"]
    abilities.ABILITIES["CONSTRICTION"](s2, 0, "x", None)
    assert not s2.players[1].action_tokens
    s3 = ctx(new())
    make_leader(s3, 1, appeal=4, conservation=9)  # below the appeal threshold
    abilities.ABILITIES["CONSTRICTION"](s3, 0, "x", None)
    assert not s3.players[1].action_tokens


def test_constriction_end_to_end_lowers_strength_by_two_and_is_removed():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    v.slots = ["build", "association", "sponsors", "animals", "cards"]
    play(s, CONSTRICTION)
    assert v.action_tokens == {"cards": ["constriction"]}
    assert is_turn_of(s, 1)
    assert engine._card_strength(s, 1, "cards") == 3
    engine.step(s, ("act", "cards", 0))
    assert top(s).kind == "act_cards" and top(s).data["draw"] == T.CARDS_TABLE[False][2][0]  # strength 3, not 5
    assert v.action_tokens == {}
    drive(s)
    assert v.slots[0] == "cards"


def test_constriction_with_x_tokens():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    v.slots = ["build", "association", "sponsors", "animals", "cards"]
    v.xtokens = 2
    play(s, CONSTRICTION)
    labels = {o.key: o.label for o in engine.legal_options(s)}
    assert "strength 3" in labels[("act", "cards", 0)]
    assert "strength 5" in labels[("act", "cards", 2)]


# ---- Pilfering --------------------------------------------------------------------------

def test_pilfering_target_chooses_a_card_or_money():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    v.hand = HAND[:]
    p = play(s, PILFERING_1)
    assert top(s).kind == "ab_pilfer" and top(s).player == 1  # resolves right away, decided by the target
    assert engine.to_move(s) == 1
    assert keys(s) == [("card",), ("money",)]
    other = copy.deepcopy(s)
    engine.step(s, ("card",))
    assert len(p.hand) == 1 and p.hand[0] in HAND
    assert sorted(v.hand + p.hand) == sorted(HAND)
    assert is_turn_of(s, 1)
    money = other.players[0].money
    engine.step(other, ("money",))
    assert other.players[0].money == money + 5 and other.players[1].money == 95
    assert other.players[0].hand == [] and len(other.players[1].hand) == 3


def test_pilfering_empty_hand_and_poor_victim():
    s = new()
    make_leader(s, 1)
    s.players[1].money = 3
    p = play(s, PILFERING_1)
    assert keys(s) == [("money",)]
    money = p.money
    engine.step(s, ("money",))
    assert p.money == money + 3 and s.players[1].money == 0


def test_pilfering_card_is_random_but_seeded():
    picks = set()
    for seed in range(12):
        s = new(seed=seed)
        make_leader(s, 1)
        s.players[1].hand = HAND[:]
        p = play(s, PILFERING_1)
        engine.step(s, ("card",))
        picks.add(p.hand[0])
    assert len(picks) > 1


@pytest.mark.parametrize("keyword", ["PILFERING_1", "PILFERING_2"])
@pytest.mark.parametrize("lead,zoo_cards,hit", [(4, [], False), (5, [], True), (50, ["225"], False)])
def test_pilfering_threshold_and_quarantine_lab(keyword, lead, zoo_cards, hit):
    s = ctx(new())
    s.players[1].appeal = lead
    s.players[1].zoo_cards = zoo_cards
    n = len(s.stack)
    abilities.ABILITIES[keyword](s, 0, "x", None)
    assert (len(s.stack) > n) == hit
    if hit:
        assert top(s).kind == "ab_pilfer" and top(s).player == 1


def test_pilfering_nothing_when_the_user_leads():
    s = new()
    s.players[1].appeal = 5
    play(s, PILFERING_1)  # 0 + 6 appeal from the card
    assert is_turn_of(s, 1)


def test_pilfering_when_tied_for_the_lead_the_other_is_the_target():
    s = new()
    s.players[1].appeal = 6  # exactly the user's appeal once the card is played
    play(s, PILFERING_1)
    assert top(s).kind == "ab_pilfer" and top(s).player == 1


def test_pilfering_tie_between_others_asks_the_user_first():
    s = new(3)
    make_leader(s, 1)
    make_leader(s, 2)
    s.players[2].hand = [HAND[0]]
    p = play(s, PILFERING_1)
    assert top(s).kind == "ab_pilfer_pick" and top(s).player == 0
    assert keys(s) == [("target", 1), ("target", 2)]
    engine.step(s, ("target", 2))
    assert top(s).kind == "ab_pilfer" and top(s).player == 2 and top(s).data["thief"] == 0
    engine.step(s, ("card",))
    assert p.hand == [HAND[0]]
    assert is_turn_of(s, 1)


def test_pilfering_tie_with_a_protected_player_needs_no_choice():
    s = new(3)
    make_leader(s, 1)
    make_leader(s, 2)
    s.players[1].zoo_cards = ["225"]
    play(s, PILFERING_1)
    assert top(s).kind == "ab_pilfer" and top(s).player == 2


def test_pilfering_two_others_below_the_user_does_nothing():
    s = new(3)
    s.players[1].appeal = s.players[2].appeal = 5
    play(s, PILFERING_1)
    assert is_turn_of(s, 1)


def test_pilfering_2_hits_appeal_and_conservation_leaders():
    s = new(3)
    make_leader(s, 1, appeal=50, conservation=1)
    make_leader(s, 2, appeal=20, conservation=6)
    s.players[1].money = s.players[2].money = 40
    p = play(s, PILFERING_2)
    assert top(s).player == 1 and top(s).kind == "ab_pilfer"  # appeal first
    engine.step(s, ("money",))
    assert top(s).player == 2 and top(s).kind == "ab_pilfer"
    engine.step(s, ("money",))
    assert p.money == 100 - 18 + 10
    assert (s.players[1].money, s.players[2].money) == (35, 35)
    assert is_turn_of(s, 1)


def test_pilfering_2_can_hit_the_same_player_twice():
    s = new()
    make_leader(s, 1, appeal=50, conservation=2)
    s.players[1].money = 40
    p = play(s, PILFERING_2)
    engine.step(s, ("money",))
    assert top(s).kind == "ab_pilfer" and top(s).player == 1
    engine.step(s, ("money",))
    assert s.players[1].money == 30 and p.money == 100 - 18 + 10


def test_pilfering_2_needs_a_conservation_point_and_protection():
    s = new()
    make_leader(s, 1, appeal=50, conservation=0)
    s.players[1].money = 40
    play(s, PILFERING_2)
    engine.step(s, ("money",))
    assert is_turn_of(s, 1)  # only the appeal hit
    assert s.players[1].money == 35
    # Conservation leader is protected, appeal leader is not.
    s = new(3)
    make_leader(s, 1, appeal=50, conservation=0)
    make_leader(s, 2, appeal=20, conservation=6)
    s.players[2].zoo_cards = ["225"]
    play(s, PILFERING_2)
    engine.step(s, ("money",))
    assert is_turn_of(s, 1)


def test_pilfering_2_tie_picks_resolve_in_order():
    s = new(3)
    make_leader(s, 1, appeal=50, conservation=3)
    make_leader(s, 2, appeal=50, conservation=3)
    play(s, PILFERING_2)
    assert top(s).kind == "ab_pilfer_pick"
    engine.step(s, ("target", 1))
    engine.step(s, ("money",))
    assert top(s).kind == "ab_pilfer_pick"  # the conservation tie
    engine.step(s, ("target", 2))
    assert top(s).player == 2
    engine.step(s, ("money",))
    assert is_turn_of(s, 1)


# ---- Hypnosis -----------------------------------------------------------------------------

def test_hypnosis_direct_offer_lists_the_leaders_top_slots():
    s = ctx(new())
    make_leader(s, 1)
    abilities.ABILITIES["HYPNOSIS"](s, 0, "x", 3)
    assert s.turn["after"] == [("extra_action", 0, {"actions": s.players[1].slots[:3], "owner": 1,
                                                    "optional": True})]
    assert s.stack[-1].kind == "turn"  # nothing pushed directly


def test_hypnosis_does_nothing_without_a_vulnerable_leader():
    for setup in (lambda s: None,                                   # the user leads
                  lambda s: make_leader(s, 1, appeal=4),            # under the threshold
                  lambda s: (make_leader(s, 1), s.players[1].zoo_cards.append("225"))):
        s = ctx(new())
        setup(s)
        abilities.ABILITIES["HYPNOSIS"](s, 0, "x", 3)
        assert s.turn["after"] == []


def test_hypnosis_end_to_end_uses_the_victims_card_strength_and_side():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    v.slots = ["build", "cards", "association", "sponsors", "animals"]
    v.upgraded.add("cards")  # the victim's side II, not mine
    p = play(s, HYPNOSIS_3)
    assert top(s).kind == "extra_action" and top(s).player == 0
    options = keys(s)
    assert ("act", "cards", 0) in options and ("skip",) in options
    assert not any(k[1] == "animals" for k in options if k[0] == "act")  # slot 5 is out of reach
    engine.step(s, ("act", "cards", 0))
    assert top(s).kind == "act_cards" and top(s).player == 0
    assert top(s).data["upgraded"] is True
    assert top(s).data["draw"] == T.CARDS_TABLE[True][1][0]  # slot 2 of the victim
    drive(s)
    assert len(p.hand) == 1  # drew 2, discarded 1
    assert v.slots == ["cards", "build", "association", "sponsors", "animals"]  # victim's card moved to slot 1
    assert p.slots[0] == "animals"
    assert s.borrowed is None
    assert is_turn_of(s, 1)


def test_hypnosis_discards_tokens_on_the_borrowed_card():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    v.slots = ["build", "association", "cards", "sponsors", "animals"]
    E.add_action_token(s, 1, "cards", "venom")
    E.add_action_token(s, 1, "cards", "constriction")  # slot 3 - 2 = strength 1
    p = play(s, HYPNOSIS_3)
    assert ("act", "cards", 0) in keys(s)
    engine.step(s, ("act", "cards", 0))
    assert top(s).data["draw"] == T.CARDS_TABLE[False][0][0]
    assert v.action_tokens == {}
    assert p.money == 100 - 10  # the Venom token was not mine to pay for
    drive(s)
    assert v.slots[0] == "cards"


def test_hypnosis_tie_is_resolved_immediately_then_offered():
    s = new(3)
    make_leader(s, 1)
    make_leader(s, 2)
    s.players[2].slots = ["sponsors", "cards", "build", "association", "animals"]
    play(s, HYPNOSIS_3)
    assert top(s).kind == "ab_hypnosis_pick" and top(s).player == 0
    assert keys(s) == [("target", 1), ("target", 2)]
    engine.step(s, ("target", 2))
    assert top(s).kind == "extra_action"
    assert top(s).data["owner"] == 2 and top(s).data["actions"] == ["sponsors", "cards", "build"]
    engine.step(s, ("act", "sponsors", 0))
    assert top(s).kind == "act_sponsors" and top(s).data["strength"] == 1
    engine.step(s, ("break",))
    assert s.players[2].slots[0] == "sponsors"
    assert is_turn_of(s, 1)


def test_hypnosis_tied_with_the_user_targets_the_other():
    s = new()
    s.players[1].appeal = 7
    s.players[1].slots = ["cards", "build", "association", "sponsors", "animals"]
    s.players[0].appeal = 5  # plus 2 from the adder
    play(s, HYPNOSIS_3)
    assert s.players[0].appeal == 7
    assert top(s).kind == "extra_action" and top(s).data["owner"] == 1


def test_two_hypnosis_abilities_queue_two_offers():
    s = ctx(new())
    make_leader(s, 1)
    abilities.ABILITIES["HYPNOSIS"](s, 0, "x", 3)
    abilities.ABILITIES["HYPNOSIS"](s, 0, "x", 3)
    assert len(s.turn["after"]) == 2


def test_venom_cost_is_counted_before_offering_an_action():
    s = new()
    make_leader(s, 1)
    v = s.players[1]
    v.slots = ["cards", "association", "build", "sponsors", "animals"]
    play(s, VENOM_2)  # tokens on cards and association; build has none, so it costs 2 money to use
    assert is_turn_of(s, 1)

    def build_offered(money):
        v.money = money
        return any(o.key[:2] == ("act", "build") for o in engine.legal_options(s))

    cheapest = T.BUILD_COST_PER_SPACE  # a size-1 building
    assert build_offered(E.VENOM_COST + cheapest)
    assert not build_offered(E.VENOM_COST + cheapest - 1)
    # every action offered can really be carried out after paying
    v.money = E.VENOM_COST + cheapest
    for option in engine.legal_options(s):
        engine.step(copy.deepcopy(s), option)
