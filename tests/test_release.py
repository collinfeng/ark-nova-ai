"""Release into the Wild conservation projects (association action)."""
import pytest

import arknova  # noqa: F401
import arknova.sponsor_rules  # noqa: F401
from arknova import cards, engine, tables as T

ACT = "act_association"
EUROPE = "113"      # Bavarian Forest: europe icon; slot 1 size 4+ (5 cons), 2 size 3 (4), 3 size <= 2 (3)
BIRD = "119"        # Low Mountain Range: bird icon
SIZE1, SIZE2, SIZE3, SIZE4, SIZE5 = "445", "419", "443", "417", "441"  # europe animals, standard enclosures
CONS_TOKEN = 3      # left-edge token worth exactly +1 conservation (no follow-up choice)
MONEY_TOKEN = 2     # left-edge token worth 5 money


def new(seed=0):
    state = engine.new_game(2, seed=seed)
    while state.stack[-1].kind == "setup_keep":
        engine.step(state, engine.legal_options(state)[0])
    p = state.players[0]
    p.hand, p.workers, p.money, p.reputation, p.conservation, p.appeal = [], 4, 100, 4, 0, 0
    p.slots = ["animals", "build", "cards", "sponsors", "association"]  # strength 5
    state.base_projects, state.projects, state.project_tokens = [], [], {}
    return state


def put_animal(state, p, card_id):
    """Put an animal into the player's zoo, in its own standard enclosure."""
    player = state.players[p]
    c = cards.card(card_id)
    size = c["enclosure"]["standard_size"]
    cells = player.zoo.legal_placements("enclosure", size)[0]
    building, _ = player.zoo.place("enclosure", size, cells)
    building.occupied = True
    player.housing[card_id] = (building.id, 0)
    player.zoo_cards.append(card_id)
    player.appeal += c["appeal"]
    return building


def start(state, strength=5, side2=False):
    p = state.players[0]
    if side2:
        p.upgraded.add("association")
        p.universities = ["science2"]
    engine.step(state, ("act", "association", 0))
    assert state.stack[-1].kind == ACT


def keys(state):
    return [o.key for o in engine.legal_options(state)]


def release_keys(state, kind="release"):
    return [k for k in keys(state) if k[0] == kind]


def settle(state):
    while state.stack[-1].kind not in (ACT, "turn"):
        engine.step(state, engine.legal_options(state)[0])


def in_play(state, pid):
    state.projects.insert(0, pid)
    state.project_tokens[pid] = {}


def test_size_limits_pick_the_slot_and_the_animal():
    state = new()
    for a in (SIZE1, SIZE3, SIZE5):
        put_animal(state, 0, a)
    in_play(state, EUROPE)
    start(state)
    ks = release_keys(state)
    by_slot = {}
    for _, pid, position, token, animal in ks:
        assert pid == EUROPE
        by_slot.setdefault(position, set()).add(animal)
    assert by_slot == {1: {SIZE5}, 2: {SIZE3}, 3: {SIZE1}}
    # one option per (position, token, animal)
    assert len(ks) == 3 * 7


def test_size_two_counts_as_small_and_size_four_as_large():
    state = new()
    for a in (SIZE2, SIZE4):
        put_animal(state, 0, a)
    in_play(state, EUROPE)
    start(state)
    by_slot = {}
    for _, _, position, _, animal in release_keys(state):
        by_slot.setdefault(position, set()).add(animal)
    assert by_slot == {1: {SIZE4}, 3: {SIZE2}}


def test_icon_must_match():
    state = new()
    put_animal(state, 0, SIZE3)  # europe, herbivore
    in_play(state, BIRD)
    in_play(state, EUROPE)
    start(state)
    assert {k[1] for k in release_keys(state)} == {EUROPE}


def test_no_matching_animal_means_no_release_options():
    from arknova.actions import association
    state = new()
    in_play(state, EUROPE)
    assert not [o for o in association._task_options(state, 0, 5, [], True) if o.key[0] == "release"]


def test_release_removes_animal_loses_appeal_and_frees_the_enclosure():
    state = new()
    p = state.players[0]
    building = put_animal(state, 0, SIZE5)
    appeal = p.appeal
    gain = cards.card(SIZE5)["appeal"]
    in_play(state, EUROPE)
    start(state)
    engine.step(state, ("release", EUROPE, 1, CONS_TOKEN, SIZE5))
    assert SIZE5 not in p.zoo_cards and SIZE5 in state.discard and SIZE5 not in p.housing
    assert not building.occupied
    assert p.appeal == appeal - gain
    settle(state)
    assert p.conservation == 6
    assert state.project_tokens[EUROPE] == {1: 0}
    assert p.tokens[CONS_TOKEN] is False


def test_release_appeal_never_below_zero():
    state = new()
    p = state.players[0]
    put_animal(state, 0, SIZE1)
    p.appeal = 0
    in_play(state, EUROPE)
    start(state)
    engine.step(state, ("release", EUROPE, 3, MONEY_TOKEN, SIZE1))
    assert p.appeal == 0 and p.conservation == 3 and p.money == 105


def test_same_player_cannot_support_a_release_project_twice():
    state = new()
    p = state.players[0]
    p.upgraded.add("association")
    put_animal(state, 0, SIZE1)
    put_animal(state, 0, SIZE3)
    in_play(state, EUROPE)
    start(state, side2=True)
    engine.step(state, ("release", EUROPE, 3, MONEY_TOKEN, SIZE1))
    assert not release_keys(state)  # task type "project" is used up anyway
    # the project itself also refuses the player again
    from arknova.actions import association
    assert association._support_choices(state, 0, EUROPE) == []


def test_other_player_can_fill_another_slot():
    state = new()
    q = state.players[1]
    put_animal(state, 1, SIZE3)
    in_play(state, EUROPE)
    state.project_tokens[EUROPE] = {3: 0}
    from arknova.actions import association
    choices = association._support_choices(state, 1, EUROPE)
    assert {c[0] for c in choices} == {2} and {c[2] for c in choices} == {SIZE3}
    assert q.tokens.count(True) == 7


def test_taken_slot_is_not_offered():
    state = new()
    put_animal(state, 0, SIZE5)
    in_play(state, EUROPE)
    state.project_tokens[EUROPE] = {1: 1}
    start(state)
    assert not release_keys(state)


# ---- play bonus ----------------------------------------------------------------

def test_play_from_hand_gains_reputation_for_the_player_who_plays_it():
    state = new()
    p = state.players[0]
    put_animal(state, 0, SIZE3)
    p.hand = [EUROPE]
    start(state)
    ks = release_keys(state, "play_release")
    assert ks and all(k[1] == EUROPE and k[4] == SIZE3 and k[2] == 2 for k in ks)
    engine.step(state, ("play_release", EUROPE, 2, CONS_TOKEN, SIZE3))
    settle(state)
    assert p.reputation == 5  # +1 reputation
    assert state.projects == [EUROPE] and EUROPE not in p.hand
    assert state.project_tokens[EUROPE] == {2: 0}
    assert p.conservation == 4 + 1


def test_supporting_a_project_already_in_play_gives_no_reputation():
    state = new()
    p = state.players[0]
    p.reputation = 2
    put_animal(state, 0, SIZE3)
    in_play(state, EUROPE)
    start(state)
    engine.step(state, ("release", EUROPE, 2, CONS_TOKEN, SIZE3))
    settle(state)
    assert p.reputation == 2 and p.conservation == 5


def test_play_bonus_is_not_given_to_the_later_supporter():
    state = new()
    p, q = state.players
    put_animal(state, 0, SIZE3)
    put_animal(state, 1, SIZE5)
    p.reputation = q.reputation = 2
    p.hand = [EUROPE]
    start(state)
    engine.step(state, ("play_release", EUROPE, 2, CONS_TOKEN, SIZE3))
    settle(state)
    assert p.reputation == 3 and q.reputation == 2
    # player 1 supports the card later: no reputation for them
    q.workers = 4
    q.slots = ["animals", "build", "cards", "sponsors", "association"]
    state.current = 1
    while state.stack[-1].kind != "turn" or state.stack[-1].player != 1:
        engine.step(state, engine.legal_options(state)[0])
    engine.step(state, ("act", "association", 0))
    engine.step(state, ("release", EUROPE, 1, CONS_TOKEN, SIZE5))
    settle(state)
    assert q.reputation == 2 and q.conservation == 5 + 1


def test_play_from_display_costs_the_folder_and_needs_side_two():
    state = new()
    p = state.players[0]
    put_animal(state, 0, SIZE3)
    p.reputation = 4
    state.display[2] = EUROPE
    p.money = 10
    start(state)  # side I
    assert not release_keys(state, "play_release_display")
    state = new()
    p = state.players[0]
    put_animal(state, 0, SIZE3)
    p.reputation = 2
    state.display[0] = EUROPE
    p.money = 10
    start(state, side2=True)
    ks = release_keys(state, "play_release_display")
    assert ks and all(k[1] == 0 and k[4] == SIZE3 for k in ks)
    engine.step(state, ("play_release_display", 0, 2, MONEY_TOKEN, SIZE3))
    settle(state)
    assert state.display[0] is None and state.projects == [EUROPE]
    assert p.money == 10 - 1 + 5 and p.reputation == 3


def test_display_play_needs_money_for_the_folder():
    state = new()
    p = state.players[0]
    put_animal(state, 0, SIZE3)
    p.reputation, p.money = 4, 2
    state.display[2] = EUROPE  # folder 3 costs 3
    start(state, side2=True)
    assert not release_keys(state, "play_release_display")


# ---- Migration Recording -------------------------------------------------------

def test_migration_recording_adds_conservation():
    state = new()
    p = state.players[0]
    p.zoo_cards.append("224")
    put_animal(state, 0, SIZE5)
    in_play(state, EUROPE)
    start(state)
    engine.step(state, ("release", EUROPE, 1, CONS_TOKEN, SIZE5))
    settle(state)
    assert p.conservation == 5 + 1 + 1


def test_migration_recording_does_not_apply_to_base_projects():
    state = new()
    p = state.players[0]
    p.zoo_cards.append("224")
    base = "101"  # Species Diversity
    state.base_projects = [base]
    state.project_tokens = {base: {}}
    p.hand = []
    from arknova.actions import association
    # reach slot 3 of the base project: three different animal categories
    for c in ("445", "419", "417"):  # herbivore, predator, predator
        p.zoo_cards.append(c)
    p.zoo_cards.append("511")  # bird
    start(state)
    ks = [k for k in keys(state) if k[0] == "support" and k[2] == 3 and k[3] == CONS_TOKEN]
    assert ks
    engine.step(state, ks[0])
    settle(state)
    assert p.conservation == 2 + 1  # slot reward 2 + token 1, no Migration bonus


def test_migration_recording_allows_supporting_the_same_release_project_again():
    state = new()
    p = state.players[0]
    p.zoo_cards.append("224")
    p.upgraded.add("association")
    p.universities = ["science2"]
    for a in (SIZE5, SIZE3):
        put_animal(state, 0, a)
    in_play(state, EUROPE)
    from arknova.actions import association
    choices = association._support_choices(state, 0, EUROPE)
    assert {(c[0], c[2]) for c in choices} == {(1, SIZE5), (2, SIZE3)}
    state.project_tokens[EUROPE] = {1: 0}  # player 0 already holds slot 1
    choices = association._support_choices(state, 0, EUROPE)
    assert {(c[0], c[2]) for c in choices} == {(2, SIZE3)}  # needs a free slot
    state.project_tokens[EUROPE] = {1: 0, 2: 0}
    assert association._support_choices(state, 0, EUROPE) == []
    # without Migration Recording the second support is refused
    p.zoo_cards.remove("224")
    state.project_tokens[EUROPE] = {1: 0}
    assert association._support_choices(state, 0, EUROPE) == []


def test_migration_recording_second_support_in_one_action():
    state = new()
    p = state.players[0]
    p.zoo_cards.append("224")
    for a in (SIZE5, SIZE3):
        put_animal(state, 0, a)
    in_play(state, EUROPE)
    p.xtokens = 0
    p.slots = ["animals", "build", "cards", "sponsors", "association"]  # strength 5
    engine.step(state, ("act", "association", 0))
    engine.step(state, ("release", EUROPE, 1, CONS_TOKEN, SIZE5))
    settle(state)  # side I: the action ended
    assert p.conservation == 5 + 1 + 1
    # next turn, same project again in the free slot
    state.current = 0
    while not (state.stack[-1].kind == "turn" and state.stack[-1].player == 0):
        engine.step(state, engine.legal_options(state)[0])
    p.slots = ["animals", "build", "cards", "sponsors", "association"]
    p.workers_out = {}
    engine.step(state, ("act", "association", 0))
    assert ("release", EUROPE, 2, MONEY_TOKEN, SIZE3) in keys(state)
    engine.step(state, ("release", EUROPE, 2, MONEY_TOKEN, SIZE3))
    settle(state)
    assert state.project_tokens[EUROPE] == {1: 0, 2: 0}
    assert p.conservation == 7 + 4 + 1
