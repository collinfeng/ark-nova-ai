import copy

import pytest

import arknova  # noqa: F401  (registers the actions)
from arknova import effects as E
from arknova import engine as G
from arknova import tables as T
from arknova.state import EngineError


def started(n=2, seed=0):
    """A game past the opening hand selection, at player 0's first turn."""
    state = G.new_game(n, seed=seed)
    while state.stack[-1].kind == "setup_keep":
        G.step(state, G.legal_options(state)[0])
    return state


def resolve(state, pick=0):
    """Answer pending bonus choices until the game is back at a turn."""
    while state.stack[-1].kind != "turn":
        G.step(state, G.legal_options(state)[pick])


def keys(state):
    return [o.key for o in G.legal_options(state)]


# ---- tables -----------------------------------------------------------------

@pytest.mark.parametrize("appeal,income", [(0, 5), (5, 10), (6, 10), (7, 11), (16, 15), (17, 16), (19, 16),
                                           (25, 18), (35, 21), (55, 26), (101, 35), (113, 37)])
def test_appeal_income(appeal, income):
    assert T.appeal_income(appeal) == income


@pytest.mark.parametrize("conservation,target", [(0, 114), (7, 100), (10, 94), (11, 91), (16, 76), (18, 70), (20, 64)])
def test_target_appeal_matches_board_and_rulebook_examples(conservation, target):
    assert T.target_appeal(conservation) == target


def test_victory_points_rulebook_example():
    assert T.victory_points(72, 16) == -4
    assert T.victory_points(79, 18) == 9


@pytest.mark.parametrize("reputation,folders", [(1, 1), (2, 2), (3, 2), (4, 3), (6, 3), (7, 4), (9, 4), (10, 5), (13, 6), (15, 6)])
def test_reputation_folders(reputation, folders):
    assert T.reputation_folders(reputation) == folders


# ---- setup ------------------------------------------------------------------

def test_setup():
    state = G.new_game(3, seed=1)
    assert [p.appeal for p in state.players] == [0, 1, 2]
    assert all(p.slots[0] == "animals" and sorted(p.slots) == sorted(T.ACTIONS) for p in state.players)
    assert all(len(p.hand) == 8 and len(p.final_cards) == 2 and p.money == 25 for p in state.players)
    assert len(G.legal_options(state)) == 70
    assert len(state.display) == 6 and len(state.base_projects) == 3
    state = started(3, seed=1)
    assert all(len(p.hand) == 4 for p in state.players)
    assert len(state.discard) == 12 and G.to_move(state) == 0


def test_two_player_setup_blocks_project_levels():
    state = G.new_game(2, seed=0)
    assert [list(state.project_tokens[c].items()) for c in state.base_projects] == [
        [(1, "blocked")], [(2, "blocked")], [(3, "blocked")]]


def test_same_seed_same_game():
    a, b = G.new_game(2, seed=5), G.new_game(2, seed=5)
    assert a.display == b.display and a.players[0].hand == b.players[0].hand


# ---- turns ------------------------------------------------------------------

def test_action_card_rotates_to_slot_one():
    state = started()
    player = state.players[0]
    player.slots = ["animals", "build", "association", "cards", "sponsors"]
    G.step(state, ("act", "cards", 0))  # strength 4, side I: draw 2
    G.step(state, ("deck",))
    assert G.to_move(state) == 1
    assert player.slots == ["cards", "animals", "build", "association", "sponsors"]
    assert len(player.hand) == 6


def test_xtoken_action_and_spending():
    state = started()
    player = state.players[0]
    player.slots = ["cards", "animals", "build", "association", "sponsors"]
    G.step(state, ("xtoken", "sponsors"))
    assert player.xtokens == 1 and player.slots[0] == "sponsors"
    G.step(state, ("xtoken", "cards"))  # player 1
    assert ("act", "cards", 1) in keys(state)
    G.step(state, ("act", "cards", 1))  # slot 2 + 1 token = strength 3: draw 2, discard 1
    G.step(state, ("deck",))
    assert player.xtokens == 0
    assert state.stack[-1].kind == "discard_hand"
    G.step(state, G.legal_options(state)[0])
    assert len(player.hand) == 5 and G.to_move(state) == 1


def test_no_xtoken_action_at_five_tokens():
    state = started()
    state.players[0].xtokens = 5
    assert not any(k[0] == "xtoken" for k in keys(state))


def test_illegal_option_rejected():
    state = started()
    with pytest.raises(EngineError):
        G.step(state, ("act", "cards", 3))


def test_cards_snap_at_strength_five():
    state = started()
    player = state.players[0]
    player.slots = ["animals", "build", "association", "sponsors", "cards"]
    wanted = state.display[5]
    G.step(state, ("act", "cards", 0))
    assert ("snap", 5) in keys(state)
    G.step(state, ("snap", 5))
    assert wanted in player.hand and None not in state.display


def test_cards_two_draws_from_display_in_range():
    state = started()
    player = state.players[0]
    player.upgraded.add("cards")
    player.reputation = 4  # folders 1-3
    player.slots = ["animals", "cards", "build", "association", "sponsors"]  # strength 2: draw 2, discard 1
    first = state.display[2]
    G.step(state, ("act", "cards", 0))
    assert ("display", 2) in keys(state) and ("display", 3) not in keys(state)
    G.step(state, ("display", 2))
    assert ("display", 2) not in keys(state)
    G.step(state, ("deck",))
    assert state.stack[-1].kind == "discard_hand" and first in player.hand


def test_sponsors_break_option_pays_and_advances():
    state = started()
    player = state.players[0]
    player.slots = ["animals", "build", "sponsors", "association", "cards"]
    G.step(state, ("act", "sponsors", 0))
    G.step(state, ("break",))
    assert player.money == 28 and state.break_pos == 3
    upgraded = state.players[1]
    upgraded.upgraded.add("sponsors")
    upgraded.slots = ["animals", "build", "sponsors", "association", "cards"]
    G.step(state, ("act", "sponsors", 0))
    G.step(state, ("break",))
    assert upgraded.money == 31 and state.break_pos == 6


# ---- break ------------------------------------------------------------------

def test_break_sequence():
    state = started()
    p0, p1 = state.players
    p0.slots = ["animals", "build", "association", "sponsors", "cards"]
    p0.appeal, p1.appeal = 7, 0
    p1.workers_out = {"reputation": 1}
    state.partner_zoos_available.discard("asia")
    state.break_pos = T.BREAK_TRACK[2] - 1
    old_folders = state.display[:2]
    third = state.display[2]
    G.step(state, ("act", "cards", 0))  # draws 3, discards 1, triggers the break
    G.step(state, ("deck",))
    assert state.stack[-1].kind == "discard_hand" and state.break_by == 0
    G.step(state, G.legal_options(state)[0])
    # hand limit: player 0 holds 6 and must go down to 3
    assert state.stack[-1].kind == "discard_hand" and state.stack[-1].data["limit"] == 3
    money = (p0.money, p1.money)
    resolve(state)
    assert len(p0.hand) == 3 and len(p1.hand) == 3  # both over the hand limit of 3
    assert p0.xtokens == 1  # for triggering the break
    assert (p0.money, p1.money) == (money[0] + 11, money[1] + 5)
    assert p1.workers_out == {} and "asia" in state.partner_zoos_available
    assert state.display[0] == third and all(c in state.discard for c in old_folders)
    assert state.break_pos == 0 and state.break_by is None
    assert G.to_move(state) == 1


def test_break_token_income_and_kiosk_income():
    state = started()
    p0 = state.players[0]
    cells = p0.zoo.legal_placements("kiosk", 1)[0]
    p0.zoo.place("kiosk", 1, cells)
    pavilion = p0.zoo.legal_placements("pavilion", 1)[0]
    p0.zoo.place("pavilion", 1, pavilion)
    E.take_map_token(state, 0, 2)  # 5 money now and every break
    assert p0.money == 30
    p0.slots = ["animals", "build", "association", "sponsors", "cards"]
    state.break_pos = T.BREAK_TRACK[2] - 1
    G.step(state, ("act", "cards", 0))
    resolve(state)
    # 30 + appeal income 5 + kiosk 1 + token 5
    assert p0.money == 41


# ---- effects ----------------------------------------------------------------

def test_conservation_thresholds():
    state = started()
    p0 = state.players[0]
    E.gain(state, 0, "conservation", 2)
    assert state.stack[-1].kind == "upgrade_or_worker"
    G.step(state, ("worker",))
    assert p0.workers == 2
    E.gain(state, 0, "conservation", 3)
    assert state.stack[-1].kind == "conservation_tile" and len(keys(state)) == 3
    G.step(state, ("money",))
    assert p0.money == 30 and len(state.bonus_tiles[5]) == 2
    E.gain(state, 0, "conservation", 5)  # passes 8 and reaches 10
    assert state.stack[-1].kind == "conservation_tile"
    G.step(state, ("money",))
    assert [f.kind for f in state.stack[-2:]] == ["discard_final", "discard_final"]
    resolve(state)
    assert all(len(p.final_cards) == 1 for p in state.players) and state.final_card_discarded


def test_reputation_cap_bonuses_and_overflow():
    state = started()
    p0 = state.players[0]
    E.gain(state, 0, "reputation", 20)
    assert p0.reputation == 9 and p0.workers == 2  # worker bonus at 8, capped without Cards II
    assert state.stack[-1].kind == "upgrade"  # bonus at 5
    G.step(state, ("upgrade", "cards"))
    E.gain(state, 0, "reputation", 8)  # 10..15 then 2 appeal
    resolve(state)
    assert p0.reputation == 15 and p0.appeal == 2
    assert p0.conservation == 2 and p0.xtokens == 2


def test_last_worker_gives_conservation_on_map0():
    state = started()
    E.gain(state, 0, "worker", 3)
    resolve(state)
    assert state.players[0].workers == 4 and state.players[0].conservation == 2
    E.gain(state, 0, "worker", 1)
    assert state.players[0].workers == 4


def test_partner_zoo_and_university_slots():
    state = started()
    p0 = state.players[0]
    E.take_partner_zoo(state, 0, "asia")
    assert "asia" not in state.partner_zoos_available
    assert not E.can_take_partner_zoo(state, 0, "asia")
    E.take_partner_zoo(state, 0, "africa")
    assert state.stack[-1].kind == "upgrade"
    resolve(state)
    assert not E.can_take_partner_zoo(state, 0, "europe")  # third needs Association II
    p0.upgraded.add("association")
    assert E.can_take_partner_zoo(state, 0, "europe")
    E.take_university(state, 0, "science_rep")
    assert p0.reputation == 3
    E.take_university(state, 0, "hand")
    resolve(state)
    assert p0.hand_limit == 5 and p0.reputation == 4


def test_placement_bonus_and_free_enclosure():
    state = started()
    p0 = state.players[0]
    money5 = next(c for c, cell in p0.zoo.mapdef.cells.items() if cell.bonus == "money5" and p0.zoo.mapdef.is_border(c))
    E.place_building(state, 0, "pavilion", 1, frozenset([money5]))
    assert p0.money == 30 and p0.appeal == 1
    E.gain(state, 0, "enclosure", 2)
    assert state.stack[-1].kind == "free_build"
    G.step(state, G.legal_options(state)[0])
    assert p0.zoo.count("enclosure") == 1 and p0.money == 30


def test_clever_moves_a_card_to_slot_one():
    state = started()
    p0 = state.players[0]
    last = p0.slots[4]
    E.gain(state, 0, "clever", 1)
    G.step(state, ("clever", last))
    assert p0.slots[0] == last and p0.slots[1] == "animals"


# ---- end of game ------------------------------------------------------------

def test_end_triggered_at_end_of_turn_gives_others_one_turn():
    state = started(3)
    for player in state.players:
        player.final_cards = []  # keep final scoring cards out of this test
    state.players[0].appeal = 120
    G.step(state, ("xtoken", "cards"))
    assert state.end_by == 0 and state.final_turns == 1  # two more turns, one just started
    G.step(state, ("xtoken", "cards"))
    G.step(state, ("xtoken", "cards"))
    assert state.over  # no final scoring cards left to discard
    assert state.scores[0] == 120 - 114 and G.winners(state) == [0]
    assert G.legal_options(state) == []


def test_only_the_current_player_is_checked_at_the_end_of_a_turn():
    state = started(3)
    state.players[1].appeal = 120  # crossed during someone else's turn
    G.step(state, ("xtoken", "cards"))
    assert state.end_by is None
    G.step(state, ("xtoken", "cards"))  # now at the end of their own turn
    assert state.end_by == 1 and state.final_turns == 1


def test_deepcopy_is_independent():
    state = started()
    clone = copy.deepcopy(state)
    G.step(clone, ("xtoken", "cards"))
    assert state.players[0].xtokens == 0 and G.to_move(state) == 0


def test_cached_options_give_the_same_game():
    import random
    for seed in (3, 11):
        plain, cached = G.new_game(2, seed=seed), G.new_game(2, seed=seed)
        cached.cache_options = True
        rng = random.Random(seed)
        for _ in range(1500):
            if plain.over:
                break
            keys = [o.key for o in G.legal_options(plain)]
            assert keys == [o.key for o in G.legal_options(cached)]
            key = rng.choice(keys)
            G.step(plain, key)
            G.step(cached, key)
        assert cached.over == plain.over
        assert [(p.money, p.appeal, p.conservation, p.hand) for p in plain.players] == \
               [(p.money, p.appeal, p.conservation, p.hand) for p in cached.players]
